"""
__init__.py
-----------

Main entry point for initializing the Flask application.

This module is responsible for:
    - Configuring Flask extensions (SQLAlchemy, Migrate, Marshmallow)
    - Registering custom error handlers
    - Registering REST API routes
    - Creating the Flask application via the `create_app` factory

Functions:
    - register_extensions(app): Initialize and register Flask extensions.
    - register_error_handlers(app): Register custom error handlers for the app.
    - create_app(config_class): Application factory that creates and configures
      the Flask app.
"""

import os
import sys
from sqlalchemy import inspect
from flask import Flask, request, g, abort
from flask_migrate import Migrate
from flask_marshmallow import Marshmallow
from flask_cors import CORS
from werkzeug.exceptions import InternalServerError

from app.models.db import db
from app.logger import logger
from app.routes import register_routes

# Initialisation des extensions Flask
migrate = Migrate()
ma = Marshmallow()


def should_sync():
    """
    Determine whether the permissions table should be synchronized at app startup.

    Returns:
        bool: True if the permissions table should be synchronized, False otherwise.

    Synchronization is skipped if:
        - The current command is a migration command (db, migrate, upgrade, init, revision).
        - The required table 'permissions' does not exist in the database.
    """
    # Ne synchronise pas si on est dans une commande de migration ou si les tables n'existent pas
    migration_cmds = {"db", "migrate", "upgrade", "init", "revision"}
    if any(cmd in sys.argv for cmd in migration_cmds):
        return False
    inspector = inspect(db.engine)
    return inspector.has_table("permissions")


def register_test_routes(app):
    """
    Register test-only routes that trigger error handlers directly.
    Args:
        app (Flask): The Flask application instance.
    """

    @app.route("/unauthorized")
    def trigger_unauthorized():
        abort(401)

    @app.route("/forbidden")
    def trigger_forbidden():
        abort(403)

    @app.route("/bad")
    def trigger_bad():
        abort(400)

    @app.route("/fail")
    def trigger_fail():
        raise InternalServerError("Test internal error")


def register_extensions(app):
    """
    Initialize and register Flask extensions on the application.

    Args:
        app (Flask): The Flask application instance.
    """
    db.init_app(app)
    migrate.init_app(app, db)
    ma.init_app(app)
    logger.info("Extensions registered successfully.")


def register_error_handlers(app):
    """
    Register custom error handlers for the Flask application.

    Args:
        app (Flask): The Flask application instance.
    """

    @app.errorhandler(401)
    def unauthorized(err):
        """Handler for 401 (unauthorized) errors."""
        logger.warning(
            "Unauthorized access attempt detected.",
            str(err),
            path=request.path,
            method=request.method,
            request_id=getattr(g, "request_id", None),
        )
        response = {
            "message": "Unauthorized",
            "path": request.path,
            "method": request.method,
            "request_id": getattr(g, "request_id", None),
        }
        return response, 401

    @app.errorhandler(403)
    def forbidden(err):
        """Handler for 403 (forbidden) errors."""
        logger.warning(
            "Forbidden access attempt detected.",
            str(err),
            path=request.path,
            method=request.method,
            request_id=getattr(g, "request_id", None),
        )
        response = {
            "message": "Forbidden",
            "path": request.path,
            "method": request.method,
            "request_id": getattr(g, "request_id", None),
        }
        return response, 403

    @app.errorhandler(404)
    def not_found(err):
        """Handler for 404 (resource not found) errors."""
        logger.warning(
            "Resource not found.",
            str(err),
            path=request.path,
            method=request.method,
            request_id=getattr(g, "request_id", None),
        )
        response = {
            "message": "Resource not found",
            "path": request.path,
            "method": request.method,
            "request_id": getattr(g, "request_id", None),
        }
        return response, 404

    @app.errorhandler(400)
    def bad_request(err):
        """Handler for 400 (bad request) errors."""
        logger.warning(
            "Bad request received.",
            str(err),
            path=request.path,
            method=request.method,
            request_id=getattr(g, "request_id", None),
        )
        response = {
            "message": "Bad request",
            "path": request.path,
            "method": request.method,
            "request_id": getattr(g, "request_id", None),
        }
        return response, 400

    @app.errorhandler(415)
    def unsupported_media_type(err):
        """Handler for 415 (unsupported media type) errors."""
        logger.warning(
            "Unsupported media type.",
            str(err),
            path=request.path,
            method=request.method,
            request_id=getattr(g, "request_id", None),
        )
        response = {
            "message": "Unsupported media type",
            "path": request.path,
            "method": request.method,
            "request_id": getattr(g, "request_id", None),
            "exception": str(err),
        }
        return response, 415

    @app.errorhandler(500)
    def internal_error(err):
        logger.error(
            "Internal server error",
            str(err),
            exc_info=True,
            path=request.path,
            method=request.method,
            request_id=getattr(g, "request_id", None),
        )
        response = {
            "message": "Internal server error",
            "path": request.path,
            "method": request.method,
            "request_id": getattr(g, "request_id", None),
        }

        if app.config.get("DEBUG"):
            response["exception"] = str(err)
        return response, 500

    logger.info("Error handlers registered successfully.")


def create_app(config_class):
    """
    Factory to create and configure the Flask application.

    Args:
        config_class: The configuration class or import path to use for Flask.

    Returns:
        Flask: The configured and ready-to-use Flask application instance.
    """
    app = Flask(__name__)

    app.config.from_object(config_class)

    env = os.getenv("FLASK_ENV")
    logger.info("Creating app in environment.", environment=env)
    if env in ("development", "staging"):
        CORS(
            app, supports_credentials=True, resources={r"/*": {"origins": "*"}}
        )

    register_extensions(app)
    register_error_handlers(app)
    register_routes(app)
    if app.config.get("TESTING"):
        register_test_routes(app)

    logger.info("App created successfully.")
    return app
