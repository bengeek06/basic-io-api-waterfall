"""JSON export resource for data export operations."""

import json
from typing import Any, Dict, List, Optional

import requests
from flask import Response, request
from flask_restful import Resource

from app.logger import logger
from app.utils.auth import require_jwt_auth
from app.utils.reference_resolver import (
    build_tree,
    detect_tree_structure,
    enrich_record,
)


class ExportJsonResource(Resource):
    """Resource for exporting data in JSON format."""

    def _parse_parameters(
        self,
    ) -> tuple[Optional[str], bool, bool, Optional[Dict[str, Any]]]:
        """Parse and validate query parameters.

        Returns:
            Tuple of (target_url, tree_mode, enrich_mode, lookup_config)
            Returns (..., ..., ..., "INVALID") if lookup_config JSON is invalid
        """
        target_url = request.args.get("url")
        tree_mode = request.args.get("tree", "false").lower() == "true"
        enrich_mode = request.args.get("enrich", "true").lower() == "true"
        lookup_config_str = request.args.get("lookup_config")

        lookup_config = None
        if lookup_config_str:
            try:
                lookup_config = json.loads(lookup_config_str)
            except json.JSONDecodeError as exc:
                logger.error(f"Invalid lookup_config JSON: {exc}")
                return target_url, tree_mode, enrich_mode, "INVALID"

        return target_url, tree_mode, enrich_mode, lookup_config

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

    def _prepare_data(
        self,
        data: List[Dict[str, Any]],
        enrich_mode: bool,
        tree_mode: bool,
        lookup_config: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Prepare data for export (add IDs, enrich, convert to tree).

        Args:
            data: Raw data from target service
            enrich_mode: Whether to enrich with references
            tree_mode: Whether to convert to tree structure
            lookup_config: Custom lookup configuration

        Returns:
            Prepared data ready for export
        """
        # Add _original_id to preserve UUIDs
        for record in data:
            if "id" in record and "_original_id" not in record:
                record["_original_id"] = record["id"]

        # Detect tree structure
        parent_field = detect_tree_structure(data)

        # Enrich records with reference metadata
        if enrich_mode:
            logger.info("Enriching records with reference metadata")
            data = [
                enrich_record(
                    record,
                    lookup_config=lookup_config,
                    parent_field=parent_field,
                )
                for record in data
            ]

        # Convert to tree structure if requested and applicable
        if tree_mode and parent_field:
            logger.info(f"Converting to tree structure using {parent_field}")
            data = build_tree(data, parent_field)

        return data

    @require_jwt_auth()
    def get(self) -> Response:
        """Export data from a Waterfall service endpoint as JSON.

        Query Parameters:
            url (str): Target service URL to export from
            tree (bool): Convert to nested tree structure (default: False)
            enrich (bool): Add reference metadata (default: True)
            lookup_config (str): JSON string with custom lookup config

        Returns:
            Response: JSON file download with exported data
        """
        # Parse parameters
        target_url, tree_mode, enrich_mode, lookup_config = (
            self._parse_parameters()
        )

        # Check for invalid lookup_config first
        if lookup_config == "INVALID":
            return {"message": "Invalid lookup_config JSON"}, 400

        if not target_url:
            return {"message": "Missing required parameter: url"}, 400

        try:
            # Fetch data from target URL
            logger.info(f"Fetching data from {target_url}")
            data = self._fetch_data(target_url)

            if data is None:
                return {"message": "Target URL must return a JSON array"}, 400

            # Prepare data
            data = self._prepare_data(
                data, enrich_mode, tree_mode, lookup_config
            )

            # Generate filename from URL
            resource_name = target_url.rstrip("/").split("/")[-1]
            filename = f"{resource_name}_export.json"

            # Return JSON file
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            response = Response(
                json_str,
                mimetype="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                },
            )

            logger.info(
                f"Successfully exported {len(data)} records from {target_url}"
            )
            return response

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching data from {target_url}")
            return {"message": f"Timeout connecting to {target_url}"}, 504

        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error to {target_url}")
            return {"message": f"Failed to connect to {target_url}"}, 502

        except requests.exceptions.HTTPError as exc:
            logger.error(
                f"HTTP error from {target_url}: {exc.response.status_code}"
            )
            return {
                "message": (
                    f"Target service returned error: "
                    f"{exc.response.status_code}"
                )
            }, 502

        except json.JSONDecodeError as exc:
            logger.error(f"Invalid JSON response from {target_url}: {exc}")
            return {"message": "Target service returned invalid JSON"}, 502

        except Exception as exc:  # pylint: disable=broad-except
            logger.error(f"Unexpected error during export: {exc}")
            return {"message": "Internal server error"}, 500
