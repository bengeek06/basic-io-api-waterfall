"""CSV import resource for data import operations."""

# pylint: disable=duplicate-code

import csv
import io
import json
from typing import Any, Dict, List, Optional, Tuple

import requests
from flask import request

from app.logger import logger
from app.utils.reference_resolver import (
    detect_tree_structure,
    flatten_tree,
    resolve_reference,
    topological_sort,
)


# Functions for CSV import


def _parse_csv_file(
    file,
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Parse and validate uploaded CSV file.

    Args:
        file: FileStorage object from request

    Returns:
        Tuple of (data, error_message)
    """
    if not file:
        logger.error("No file provided in request")
        return None, "No file provided"

    if file.filename == "":
        logger.error("Empty filename provided")
        return None, "Empty filename"

    if not file.filename.endswith(".csv"):
        logger.error(f"Invalid file type: {file.filename}")
        return None, "File must be a CSV file (.csv)"

    try:
        logger.info(f"Reading CSV file: {file.filename}")
        content = file.read().decode("utf-8")
        csv_reader = csv.DictReader(io.StringIO(content))
        data = list(csv_reader)

        if not data:
            logger.error("CSV file is empty")
            return None, "CSV file is empty"

        logger.info(f"CSV contains {len(data)} rows")

        # Convert CSV strings back to appropriate types
        parsed_data = []
        for row in data:
            parsed_row = _parse_csv_row(row)
            parsed_data.append(parsed_row)

        logger.info(f"Successfully parsed {len(parsed_data)} records")
        return parsed_data, None

    except UnicodeDecodeError:
        logger.error("File encoding error - not UTF-8")
        return None, "File encoding must be UTF-8"
    except csv.Error as exc:
        logger.error(f"CSV parsing error: {exc}")
        return None, f"Invalid CSV format: {exc}"


def _parse_csv_row(row: Dict[str, str]) -> Dict[str, Any]:
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
        # Handle None or empty string
        if value is None or value == "":
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
    data: List[Dict[str, Any]],
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


def _import_records(  # pylint: disable=too-many-locals
    data: List[Dict[str, Any]],
    target_url: str,
    cookies: Dict[str, str],
    resolve_fks: bool,
    parent_field: Optional[str],
    on_ambiguous: str = "skip",
    on_missing: str = "skip",
) -> Dict[str, Any]:
    """Import records to target service.

    Args:
        data: Prepared data to import
        target_url: Target service URL
        cookies: Authentication cookies
        resolve_fks: Whether to resolve foreign key references
        parent_field: Parent field name if tree structure
        on_ambiguous: How to handle ambiguous references ("skip" or "fail")
        on_missing: How to handle missing references ("skip" or "fail")

    Returns:
        Import result dictionary with statistics
    """
    logger.info(f"Starting import of {len(data)} records to {target_url}")
    id_mapping = {}
    import_report = {"success": 0, "failed": 0, "errors": []}
    resolution_report = {
        "resolved": 0,
        "ambiguous": 0,
        "missing": 0,
        "details": [],
    }

    for record in data:
        try:
            # Extract _original_id
            original_id = record.get("_original_id")
            logger.debug(f"Processing record with _original_id={original_id}")

            # Remove metadata and read-only fields before import
            readonly_fields = {
                "id",
                "created_at",
                "updated_at",
                "children",
            }
            clean_record = {
                k: v
                for k, v in record.items()
                if not k.startswith("_")
                and k not in readonly_fields
                and v is not None
            }
            logger.debug(f"Cleaned record: {list(clean_record.keys())}")

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
                logger.debug(
                    f"Resolving FKs: {list(record['_references'].keys())}"
                )
                _resolve_references(
                    clean_record,
                    record["_references"],
                    target_url,
                    cookies,
                    id_mapping,
                    resolution_report,
                    on_ambiguous,
                    on_missing,
                )

            # POST to target service
            logger.debug(f"POSTing to {target_url}: {clean_record}")
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
            error_detail = ""
            try:
                error_detail = exc.response.json()
            except Exception:  # pylint: disable=broad-except
                error_detail = exc.response.text

            error_msg = (
                f"Failed to import record (original_id={original_id}): "
                f"HTTP {exc.response.status_code} - {error_detail}"
            )
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
    record: Dict[str, Any],
    references: Dict[str, Any],
    target_url: str,
    cookies: Dict[str, str],
    id_mapping: Dict[str, str],
    resolution_report: Dict[str, Any],
    on_ambiguous: str = "skip",
    on_missing: str = "skip",
) -> None:
    """Resolve foreign key references in a record.

    Args:
        record: Record to update with resolved FKs
        references: Reference metadata
        target_url: Target service base URL
        cookies: Auth cookies
        id_mapping: Existing ID mappings
        resolution_report: Report to update
        on_ambiguous: How to handle ambiguous references ("skip" or "fail")
        on_missing: How to handle missing references ("skip" or "fail")
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
        status, resolved_id, candidates, error = resolve_reference(
            ref_metadata, target_url, cookies
        )

        if status == "resolved" and resolved_id:
            record[field_name] = resolved_id
            resolution_report["resolved"] += 1
            logger.info(f"Resolved {field_name} via lookup: {resolved_id}")
        elif status == "ambiguous":
            resolution_report["ambiguous"] += 1
            resolution_report["details"].append(
                {
                    "field": field_name,
                    "value": field_value,
                    "status": "ambiguous",
                    "candidates": len(candidates),
                }
            )
            # Handle ambiguous based on mode
            if on_ambiguous == "skip":
                record[field_name] = None
                logger.warning(
                    f"Ambiguous reference for {field_name}, setting to None (skip mode)"
                )
            else:  # fail mode
                logger.warning(
                    f"Ambiguous reference for {field_name} (fail mode will reject import)"
                )
        else:  # missing
            resolution_report["missing"] += 1
            resolution_report["details"].append(
                {
                    "field": field_name,
                    "value": field_value,
                    "status": "missing",
                    "error": error,
                }
            )
            # Handle missing based on mode
            if on_missing == "skip":
                record[field_name] = None
                logger.warning(
                    f"Missing reference for {field_name}, setting to None (skip mode)"
                )
            else:  # fail mode
                logger.warning(
                    f"Missing reference for {field_name} (fail mode will reject import)"
                )


#
def import_csv():
    """Import data from CSV file.

    Form Parameters:
        file: CSV file to import
        url: Target service URL
        resolve_foreign_keys: Whether to resolve FK references (default: true)
        lookup_fields: Comma-separated fields for FK lookup (default: name)
        on_ambiguous: How to handle ambiguous references - "skip" or "fail" (default: "skip")
        on_missing: How to handle missing references - "skip" or "fail" (default: "skip")

    Returns:
        JSON response with import statistics

    Example:
        POST /import-csv
        Content-Type: multipart/form-data
        file: data.csv
        url: http://service/api/users
        resolve_foreign_keys: true
        lookup_fields: name,code
        on_ambiguous: skip
        on_missing: skip
    """
    try:
        # Parse parameters
        file = request.files.get("file")
        target_url = request.form.get("url")
        resolve_fks = (
            request.form.get("resolve_foreign_keys", "true").lower() == "true"
        )
        on_ambiguous = request.form.get("on_ambiguous", "skip").lower()
        on_missing = request.form.get("on_missing", "skip").lower()

        # Validate mode parameters
        if on_ambiguous not in ["skip", "fail"]:
            return {
                "error": f"Invalid on_ambiguous mode: {on_ambiguous}. Must be 'skip' or 'fail'"
            }, 400
        if on_missing not in ["skip", "fail"]:
            return {
                "error": f"Invalid on_missing mode: {on_missing}. Must be 'skip' or 'fail'"
            }, 400

        logger.info(
            f"CSV import request - url={target_url}, "
            f"resolve_fks={resolve_fks}, "
            f"on_ambiguous={on_ambiguous}, "
            f"on_missing={on_missing}, "
            f"file={file.filename if file else None}"
        )

        if not target_url:
            logger.error("Missing 'url' parameter")
            return {"error": "Missing 'url' parameter"}, 400

        # Parse CSV file
        data, error = _parse_csv_file(file)
        if error:
            logger.error(f"CSV parsing failed: {error}")
            return {"error": error}, 400

        logger.info(f"Parsed {len(data)} records from CSV")

        # Prepare data
        try:
            prepared_data, parent_field = _prepare_data(data)
        except (ValueError, KeyError, AttributeError) as exc:
            logger.error(f"Data preparation failed: {exc}")
            return {"error": f"Invalid CSV data structure: {str(exc)}"}, 400

        # Import to target service
        cookies = {"access_token": request.cookies.get("access_token")}
        result = _import_records(
            prepared_data,
            target_url,
            cookies,
            resolve_fks,
            parent_field,
            on_ambiguous,
            on_missing,
        )

        # Check for resolution issues based on fail modes
        if resolve_fks and result["resolution_report"]:
            resolution_report = result["resolution_report"]

            if on_ambiguous == "fail" and resolution_report["ambiguous"] > 0:
                logger.error(
                    f"Import aborted: {resolution_report['ambiguous']} ambiguous reference(s) "
                    f"with on_ambiguous=fail mode"
                )
                return {
                    "error": "Import failed due to ambiguous references",
                    "resolution_report": resolution_report,
                }, 400

            if on_missing == "fail" and resolution_report["missing"] > 0:
                logger.error(
                    f"Import aborted: {resolution_report['missing']} missing reference(s) "
                    f"with on_missing=fail mode"
                )
                return {
                    "error": "Import failed due to missing references",
                    "resolution_report": resolution_report,
                }, 400

        logger.info(
            f"Import completed: {result['import_report']['success']} success, "
            f"{result['import_report']['failed']} failed"
        )

        return result, 200

    except ValueError as exc:
        # Data validation errors (malformed data, invalid structure)
        logger.error(f"Data validation error: {exc}")
        return {"error": f"Invalid data: {str(exc)}"}, 400

    except Exception as exc:  # pylint: disable=broad-except
        # Truly unexpected errors
        logger.error(f"Unexpected error during import: {exc}", exc_info=True)
        return {
            "error": "Internal server error",
            "detail": str(exc),
        }, 500
