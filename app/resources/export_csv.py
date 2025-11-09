"""CSV export resource for data export operations."""

import csv
import io
import json
from typing import Any, Dict, List, Optional

import requests
from flask import Response, request
from flask_restful import Resource

from app.logger import logger
from app.utils.auth import require_jwt_auth
from app.utils.reference_resolver import enrich_record


class ExportCsvResource(Resource):
    """Resource for exporting data in CSV format."""

    def _parse_parameters(self) -> tuple[Optional[str], bool]:
        """Parse and validate query parameters.

        Returns:
            Tuple of (target_url, enrich_mode)
        """
        target_url = request.args.get("url")
        enrich_mode = request.args.get("enrich", "true").lower() == "true"
        return target_url, enrich_mode

    def _fetch_data(self, target_url: str) -> Optional[List[Dict[str, Any]]]:
        """Fetch data from target URL.

        Args:
            target_url: The URL to fetch from

        Returns:
            List of records or None if error
        """
        cookies = {"access_token": request.cookies.get("access_token")}
        response = requests.get(target_url, cookies=cookies, timeout=30)
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list):
            logger.error("Target URL did not return a JSON array")
            return None

        return data

    def _flatten_record(self, record: Dict[str, Any]) -> Dict[str, str]:
        """Flatten a record for CSV export.

        Converts nested objects and arrays to JSON strings.
        Preserves _original_id and simple fields as-is.

        Args:
            record: Record to flatten

        Returns:
            Flattened record with all values as strings
        """
        flattened = {}
        for key, value in record.items():
            if value is None:
                flattened[key] = ""
            elif isinstance(value, (dict, list)):
                # Convert complex types to JSON strings
                flattened[key] = json.dumps(value)
            else:
                # Convert simple types to strings
                flattened[key] = str(value)

        return flattened

    def _prepare_data(
        self, data: List[Dict[str, Any]], enrich_mode: bool
    ) -> List[Dict[str, str]]:
        """Prepare data for CSV export.

        Args:
            data: Raw data from target service
            enrich_mode: Whether to enrich with references

        Returns:
            List of flattened records ready for CSV
        """
        prepared = []
        for record in data:
            # Add _original_id for import tracking
            if "id" in record:
                record["_original_id"] = record["id"]

            # Enrich with FK references if requested
            if enrich_mode:
                target_url = request.args.get("url")
                cookies = {"access_token": request.cookies.get("access_token")}
                record = enrich_record(record, target_url, cookies)

            # Flatten for CSV
            flattened = self._flatten_record(record)
            prepared.append(flattened)

        return prepared

    def _get_all_fieldnames(self, records: List[Dict[str, str]]) -> List[str]:
        """Get all unique field names from records.

        Args:
            records: List of flattened records

        Returns:
            Sorted list of unique field names
        """
        fieldnames = set()
        for record in records:
            fieldnames.update(record.keys())

        # Put _original_id and id first if present
        ordered = []
        for priority_field in ["_original_id", "id"]:
            if priority_field in fieldnames:
                ordered.append(priority_field)
                fieldnames.remove(priority_field)

        # Add remaining fields in sorted order
        ordered.extend(sorted(fieldnames))
        return ordered

    @require_jwt_auth()
    def get(self):
        """Export data to CSV format.

        Query Parameters:
            url (str): Target service URL to export from
            enrich (bool): Whether to enrich FK references (default: true)

        Returns:
            CSV file as response with text/csv content type

        Example:
            GET /export-csv?url=http://service/api/users&enrich=false
        """
        try:
            # Parse parameters
            target_url, enrich_mode = self._parse_parameters()

            if not target_url:
                return {"error": "Missing 'url' parameter"}, 400

            # Fetch data
            logger.info(f"Fetching data from {target_url}")
            data = self._fetch_data(target_url)

            if data is None:
                return {"error": "Failed to fetch data from target URL"}, 500

            if not data:
                return {"error": "No data to export"}, 404

            # Prepare data
            prepared_data = self._prepare_data(data, enrich_mode)

            # Get all fieldnames
            fieldnames = self._get_all_fieldnames(prepared_data)

            # Generate CSV
            output = io.StringIO()
            writer = csv.DictWriter(
                output, fieldnames=fieldnames, extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(prepared_data)

            csv_content = output.getvalue()
            output.close()

            logger.info(f"Exported {len(prepared_data)} records to CSV")

            # Return CSV response
            return Response(
                csv_content,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=export.csv"},
            )

        except requests.exceptions.Timeout:
            logger.error("Timeout fetching data from target URL")
            return {"error": "Request timeout"}, 504

        except requests.exceptions.ConnectionError:
            logger.error("Connection error to target URL")
            return {"error": "Connection error"}, 502

        except requests.exceptions.HTTPError as exc:
            logger.error(f"HTTP error from target: {exc}")
            return {"error": f"Target service error: {exc.response.status_code}"}, 502

        except Exception as exc:  # pylint: disable=broad-except
            logger.error(f"Unexpected error during export: {exc}")
            return {"error": "Internal server error"}, 500
