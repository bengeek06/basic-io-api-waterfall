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
from app.resources.export import ExportResource
from app.resources.importer import ImportResource


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

    # Unified Import/Export endpoints
    api.add_resource(ExportResource, "/export")
    api.add_resource(ImportResource, "/import")

    logger.info("Routes registered successfully.")
