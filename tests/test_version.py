"""
test_version.py
---------------
This module contains tests for the /version endpoint to ensure it returns the
correct version information.
"""

import json
import uuid
from tests.conftest import create_jwt_token


def test_version_endpoint(client):
    """
    Test the /version endpoint to ensure it returns the correct version
    information.
    """
    company_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    token = create_jwt_token(company_id, user_id)
    client.set_cookie("access_token", token, domain="localhost")

    response = client.get("/version")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert isinstance(data, dict)
    assert "version" in data
