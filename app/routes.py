"""
routes.py
-----------
Routes for the Flask application.
# This module is responsible for registering the routes of the REST API
# and linking them to the corresponding resources.
"""

from flask_restful import Api
from app.logger import logger
from app.resources.version import VersionResource
from app.resources.config import ConfigResource
from app.resources.health import HealthResource
from app.resources.export_json import ExportJsonResource
from app.resources.import_json import ImportJsonResource
from app.resources.export_csv import ExportCsvResource
from app.resources.import_csv import ImportCsvResource


def register_routes(app):
    """
    Register the REST API routes on the Flask application.

    Args:
        app (Flask): The Flask application instance.

    This function creates a Flask-RESTful Api instance and adds the resource
    endpoints for managing configuration, health, version, and import/export.
    """
    api = Api(app)

    api.add_resource(VersionResource, "/version")
    api.add_resource(ConfigResource, "/config")
    api.add_resource(HealthResource, "/health")

    # Import/Export endpoints
    api.add_resource(ExportJsonResource, "/export")
    api.add_resource(ImportJsonResource, "/import")
    api.add_resource(ExportCsvResource, "/export-csv")
    api.add_resource(ImportCsvResource, "/import-csv")

    logger.info("Routes registered successfully.")
