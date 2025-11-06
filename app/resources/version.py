"""
version.py
----------

This module defines the VersionResource for exposing the current API version
through a REST endpoint.
"""

import os
from flask_restful import Resource
from app.utils import require_jwt_auth, check_access_required


def _read_version():
    """Read version from VERSION file."""
    version_file_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "VERSION"
    )
    try:
        with open(version_file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "unknown"
    except (OSError, UnicodeDecodeError):
        return "unknown"


API_VERSION = _read_version()


class VersionResource(Resource):
    """
    Resource for providing the API version.

    Methods:
        get():
            Retrieve the current API version.
    """

    @check_access_required("list")
    @require_jwt_auth()
    def get(self):
        """
        Retrieve the current API version.

        Returns:
            dict: A dictionary containing the API version and HTTP status
            code 200.
        """
        return {"version": API_VERSION}, 200
