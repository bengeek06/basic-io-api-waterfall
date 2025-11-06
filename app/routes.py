"""
routes.py
-----------
Routes for the Flask application.
# This module is responsible for registering the routes of the REST API
# and linking them to the corresponding resources.
"""

from flask_restful import Api
from app.logger import logger
from app.resources.dummy import DummyResource, DummyListResource
from app.resources.version import VersionResource
from app.resources.config import ConfigResource
from app.resources.health import HealthResource


def register_routes(app):
    """
    Register the REST API routes on the Flask application.

    Args:
        app (Flask): The Flask application instance.

    This function creates a Flask-RESTful Api instance, adds the resource
    endpoints for managing dummy items, and logs the successful registration
    of routes.
    """
    api = Api(app)

    api.add_resource(DummyListResource, "/dummies")
    api.add_resource(DummyResource, "/dummies/<int:dummy_id>")

    api.add_resource(VersionResource, "/version")
    api.add_resource(ConfigResource, "/config")
    api.add_resource(HealthResource, "/health")

    logger.info("Routes registered successfully.")
