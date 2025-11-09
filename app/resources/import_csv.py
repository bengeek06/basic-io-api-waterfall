"""CSV import resource for data import operations."""

import csv
import io
import json
from typing import Any, Dict, List, Optional, Tuple

import requests
from flask import request
from flask_restful import Resource

from app.logger import logger
from app.utils.auth import require_jwt_auth
from app.utils.reference_resolver import (
    detect_tree_structure,
    flatten_tree,
    resolve_reference,
    topological_sort,
)


class ImportCsvResource(Resource):
    """Resource for importing data in CSV format."""

    def _parse_csv_file(
        self, file
    ) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """Parse and validate uploaded CSV file.

        Args:
            file: FileStorage object from request

        Returns:
            Tuple of (data, error_message)
        """
        if not file:
            return None, "No file provided"

        if file.filename == "":
            return None, "Empty filename"

        if not file.filename.endswith(".csv"):
            return None, "File must be a CSV file (.csv)"

        try:
            content = file.read().decode("utf-8")
            csv_reader = csv.DictReader(io.StringIO(content))
            data = list(csv_reader)

            if not data:
                return None, "CSV file is empty"

            # Convert CSV strings back to appropriate types
            parsed_data = []
            for row in data:
                parsed_row = self._parse_csv_row(row)
                parsed_data.append(parsed_row)

            return parsed_data, None

        except UnicodeDecodeError:
            return None, "File encoding must be UTF-8"
        except csv.Error as exc:
            return None, f"Invalid CSV format: {exc}"

    def _parse_csv_row(self, row: Dict[str, str]) -> Dict[str, Any]:
        """Parse a CSV row and convert types.

        CSV stores everything as strings. This converts:
        - JSON strings back to dict/list
        - Empty strings to None
        - Numeric strings to int/float when appropriate

        Args:
            row: Dictionary from CSV reader (all values are strings)

        Returns:
            Dictionary with proper types
        """
        parsed = {}
        for key, value in row.items():
            if value == "":
                parsed[key] = None
            elif value.startswith("{") or value.startswith("["):
                # Try to parse as JSON
                try:
                    parsed[key] = json.loads(value)
                except json.JSONDecodeError:
                    parsed[key] = value
            else:
                # Keep as string (safer than trying to guess types)
                parsed[key] = value

        return parsed

    def _prepare_data(
        self, data: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Prepare data for import (flatten tree if needed, sort by dependencies).

        Args:
            data: Raw data from file

        Returns:
            Tuple of (prepared_data, parent_field)
        """
        # Check if data is in tree format (nested children)
        is_tree = any("children" in record for record in data)

        # Detect parent field
        parent_field = detect_tree_structure(data) if not is_tree else "parent_id"

        # Flatten tree structure if needed
        if is_tree:
            logger.info("Flattening tree structure")
            data = flatten_tree(data, parent_field)

        # Sort by dependencies if tree structure present
        if parent_field:
            logger.info(f"Sorting records by {parent_field} dependencies")
            data = topological_sort(data, parent_field)

        return data, parent_field

    def _import_records(
        self,
        data: List[Dict[str, Any]],
        target_url: str,
        cookies: Dict[str, str],
        resolve_fks: bool,
        parent_field: Optional[str],
    ) -> Dict[str, Any]:
        """Import records to target service.

        Args:
            data: Prepared data to import
            target_url: Target service URL
            cookies: Authentication cookies
            resolve_fks: Whether to resolve foreign key references
            parent_field: Parent field name if tree structure

        Returns:
            Import result dictionary with statistics
        """
        id_mapping = {}
        import_report = {"success": 0, "failed": 0, "errors": []}
        resolution_report = {"resolved": 0, "ambiguous": 0, "missing": 0, "details": []}

        for record in data:
            try:
                # Extract _original_id
                original_id = record.get("_original_id")

                # Remove metadata fields before import
                clean_record = {
                    k: v
                    for k, v in record.items()
                    if not k.startswith("_") and v is not None
                }

                # Resolve parent reference if tree structure
                if parent_field and parent_field in clean_record:
                    parent_original_id = record.get(parent_field)
                    if parent_original_id and parent_original_id in id_mapping:
                        clean_record[parent_field] = id_mapping[parent_original_id]
                        logger.info(
                            f"Mapped {parent_field}: {parent_original_id} → "
                            f"{clean_record[parent_field]}"
                        )

                # Resolve foreign key references if requested
                if resolve_fks and "_references" in record:
                    self._resolve_references(
                        clean_record,
                        record["_references"],
                        target_url,
                        cookies,
                        id_mapping,
                        resolution_report,
                    )

                # POST to target service
                response = requests.post(
                    target_url, json=clean_record, cookies=cookies, timeout=30
                )
                response.raise_for_status()
                created = response.json()

                # Store ID mapping
                new_id = created.get("id")
                if original_id and new_id:
                    id_mapping[original_id] = new_id
                    logger.info(f"Created record: {original_id} → {new_id}")

                import_report["success"] += 1

            except requests.exceptions.HTTPError as exc:
                error_msg = f"Failed to import record: {exc.response.status_code}"
                import_report["failed"] += 1
                import_report["errors"].append(error_msg)
                logger.error(error_msg)

            except Exception as exc:  # pylint: disable=broad-except
                error_msg = f"Unexpected error importing record: {exc}"
                import_report["failed"] += 1
                import_report["errors"].append(error_msg)
                logger.error(error_msg)

        return {
            "import_report": import_report,
            "resolution_report": resolution_report if resolve_fks else None,
            "id_mapping": id_mapping,
        }

    def _resolve_references(
        self,
        record: Dict[str, Any],
        references: Dict[str, Any],
        target_url: str,
        cookies: Dict[str, str],
        id_mapping: Dict[str, str],
        resolution_report: Dict[str, Any],
    ) -> None:
        """Resolve foreign key references in a record.

        Args:
            record: Record to update with resolved FKs
            references: Reference metadata
            target_url: Target service base URL
            cookies: Auth cookies
            id_mapping: Existing ID mappings
            resolution_report: Report to update
        """
        for field_name, ref_metadata in references.items():
            if field_name not in record:
                continue

            field_value = record[field_name]

            # Try ID mapping first
            if field_value in id_mapping:
                record[field_name] = id_mapping[field_value]
                resolution_report["resolved"] += 1
                logger.info(f"Resolved {field_name} via ID mapping: {field_value}")
                continue

            # Try reference resolution using metadata from export
            status, resolved_id, _candidates, _error = resolve_reference(
                ref_metadata, target_url, cookies
            )

            if status == "resolved" and resolved_id:
                record[field_name] = resolved_id
                resolution_report["resolved"] += 1
                logger.info(f"Resolved {field_name} via lookup: {resolved_id}")
            elif status == "ambiguous":
                resolution_report["ambiguous"] += 1
                resolution_report["details"].append(
                    {"field": field_name, "value": field_value, "status": "ambiguous"}
                )
            else:
                resolution_report["missing"] += 1
                resolution_report["details"].append(
                    {"field": field_name, "value": field_value, "status": "missing"}
                )

    @require_jwt_auth()
    def post(self):
        """Import data from CSV file.

        Form Parameters:
            file: CSV file to import
            url: Target service URL
            resolve_foreign_keys: Whether to resolve FK references (default: true)
            lookup_fields: Comma-separated fields for FK lookup (default: name)

        Returns:
            JSON response with import statistics

        Example:
            POST /import-csv
            Content-Type: multipart/form-data
            file: data.csv
            url: http://service/api/users
            resolve_foreign_keys: true
            lookup_fields: name,code
        """
        try:
            # Parse parameters
            file = request.files.get("file")
            target_url = request.form.get("url")
            resolve_fks = request.form.get("resolve_foreign_keys", "true").lower() == "true"

            if not target_url:
                return {"error": "Missing 'url' parameter"}, 400

            # Parse CSV file
            data, error = self._parse_csv_file(file)
            if error:
                return {"error": error}, 400

            logger.info(f"Parsed {len(data)} records from CSV")

            # Prepare data
            prepared_data, parent_field = self._prepare_data(data)

            # Import to target service
            cookies = {"access_token": request.cookies.get("access_token")}
            result = self._import_records(
                prepared_data, target_url, cookies, resolve_fks, parent_field
            )

            logger.info(
                f"Import completed: {result['import_report']['success']} success, "
                f"{result['import_report']['failed']} failed"
            )

            return result, 200

        except Exception as exc:  # pylint: disable=broad-except
            logger.error(f"Unexpected error during import: {exc}")
            return {"error": "Internal server error"}, 500
