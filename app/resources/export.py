"""Unified export resource - dispatches to JSON or CSV exporters."""

from flask import request
from flask_restful import Resource

from app.logger import logger
from app.utils.auth import require_jwt_auth
from app.resources.export_json import export_json
from app.resources.export_csv import export_csv
from app.resources.export_mermaid import export_mermaid


class ExportResource(Resource):
    """Unified export endpoint that dispatches to format-specific handlers."""

    @require_jwt_auth()
    def get(self):
        """Export data from a Waterfall service endpoint.

        Query Parameters:
            url (str): Target service URL to export from
            type (str): Export format - json, csv, mermaid (default: json)
            tree (bool): Convert to nested tree (JSON only, default: False)
            enrich (bool): Add reference metadata (default: True)
            lookup_config (str): JSON string with custom lookup config
            diagram_type (str): Mermaid diagram type (mermaid only)

        Returns:
            Response: File download with exported data
        """
        export_type = request.args.get("type", "json").lower()

        # Validate export type
        if export_type not in ["json", "csv", "mermaid"]:
            return {
                "message": f"Unsupported export type: {export_type}. "
                "Allowed values: json, csv, mermaid"
            }, 400

        # Dispatch to appropriate handler
        if export_type == "json":
            logger.info("Dispatching to JSON export handler")
            return export_json()

        if export_type == "csv":
            logger.info("Dispatching to CSV export handler")
            return export_csv()

        # export_type == "mermaid"
        logger.info("Dispatching to Mermaid export handler")
        return export_mermaid()
