"""Unified import resource - dispatches to JSON or CSV importers."""

from flask import request
from flask_restful import Resource

from app.logger import logger
from app.utils.auth import require_jwt_auth
from app.resources.import_json import import_json
from app.resources.import_csv import import_csv
from app.resources.import_mermaid import import_mermaid


class ImportResource(Resource):
    """Unified import endpoint that dispatches to format-specific handlers."""

    @require_jwt_auth()
    def post(self):
        """Import data to a Waterfall service endpoint.

        Query Parameters:
            url (str): Target service URL to import to
            type (str): Import format - json, csv, mermaid (default: json)
            resolve_foreign_keys (bool): Resolve FKs using metadata (default: true)
            skip_on_ambiguous (bool): Skip ambiguous FK records (default: true)
            skip_on_missing (bool): Skip missing FK records (default: true)

        Form Data:
            file: The file to import

        Returns:
            JSON: Import report with success/failure counts and ID mappings
        """
        import_type = request.args.get("type", "json").lower()

        # Validate import type
        if import_type not in ["json", "csv", "mermaid"]:
            return {
                "message": f"Unsupported import type: {import_type}. "
                "Allowed values: json, csv, mermaid"
            }, 400

        # Dispatch to appropriate handler
        if import_type == "json":
            logger.info("Dispatching to JSON import handler")
            return import_json()

        if import_type == "csv":
            logger.info("Dispatching to CSV import handler")
            return import_csv()

        # import_type == "mermaid"
        logger.info("Dispatching to Mermaid import handler")
        return import_mermaid()
