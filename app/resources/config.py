"""
config.py
---------

This module defines the ConfigResource for exposing the current application
configuration through a REST endpoint.
"""

import os
from flask_restful import Resource
from app.utils import require_jwt_auth, check_access_required


class ConfigResource(Resource):
    """
    Resource for providing the application configuration.

    Methods:
        get():
            Retrieve the current application configuration.
    """

    @require_jwt_auth()
    @check_access_required("read")
    def get(self):
        """
        Retrieve the current application configuration.

        Returns:
            dict: A dictionary containing the application configuration and
            HTTP status code 200.
        """
        jwt_secret_is_set = os.getenv("JWT_SECRET_KEY") is not None
        internal_secret_is_set = os.getenv("INTERNAL_SECRET_KEY") is not None

        config = {
            "FLASK_ENV": os.getenv("FLASK_ENV"),
            "LOG_LEVEL": os.getenv("LOG_LEVEL"),
            "DATABASE_URI": os.getenv("DATABASE_URI"),
            "GUARDIAN_SERVICE_URL": os.getenv("GUARDIAN_SERVICE_URL"),
            "JWT_SECRET": jwt_secret_is_set,
            "INTERNAL_AUTH_TOKEN": internal_secret_is_set,
        }
        return config, 200
