"""
test_config.py
--------------
This module contains tests for the /config endpoint to ensure it returns the
expected configuration values.
"""

import json
import uuid
from tests.conftest import create_jwt_token


def test_config_endpoit(client):
    """
    Test the /config endpoint to ensure it returns the correct configuration.
    """
    company_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    token = create_jwt_token(company_id, user_id)
    client.set_cookie("access_token", token, domain="localhost")

    response = client.get("/config")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert isinstance(data, dict)
    assert "FLASK_ENV" in data
    assert "LOG_LEVEL" in data
    assert "DATABASE_URI" in data
