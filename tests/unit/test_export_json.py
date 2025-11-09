"""Unit tests for JSON export resource."""

import json
from unittest.mock import patch, Mock

import pytest


class TestExportJsonResource:
    """Tests for ExportJsonResource using HTTP client."""

    def test_missing_url_parameter(self, client, auth_headers):
        """Test error when URL parameter is missing."""
        auth_headers["set_cookie"](client)
        response = client.get("/export?tree=true")
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "url" in data["message"]

    def test_invalid_lookup_config(self, client, auth_headers):
        """Test error when lookup_config is invalid JSON."""
        auth_headers["set_cookie"](client)
        response = client.get(
            "/export?type=json&url=http://localhost:5001/api/test&lookup_config=invalid-json"
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "lookup_config" in data["message"].lower()

    @patch("app.resources.export_json.requests.get")
    def test_successful_export_simple(self, mock_get, client, auth_headers):
        """Test successful simple export."""
        # Mock response from target service
        mock_response = Mock()
        mock_response.json.return_value = [
            {"id": "uuid-1", "name": "Record 1"},
            {"id": "uuid-2", "name": "Record 2"},
        ]
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get("/export?type=json&url=http://localhost:5001/api/users")

        assert response.status_code == 200
        assert response.content_type == "application/json"
        assert "users_export.json" in response.headers["Content-Disposition"]

        # Parse response data
        data = json.loads(response.data)
        assert len(data) == 2
        assert data[0]["_original_id"] == "uuid-1"

    @patch("app.resources.export_json.requests.get")
    def test_export_with_enrichment(self, mock_get, client, auth_headers):
        """Test export with enrichment enabled."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "id": "task-1",
                "name": "Task 1",
                "project_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
            }
        ]
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get(
            "/export?type=json&url=http://localhost:5001/api/tasks&enrich=true"
        )

        data = json.loads(response.data)
        # Should have _references for project_id
        assert "_references" in data[0]
        assert "project_id" in data[0]["_references"]

    @patch("app.resources.export_json.requests.get")
    def test_export_tree_structure(self, mock_get, client, auth_headers):
        """Test export with tree conversion."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {"id": "cat-1", "name": "Parent", "parent_id": None},
            {"id": "cat-2", "name": "Child", "parent_id": "cat-1"},
        ]
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get(
            "/export?type=json&url=http://localhost:5001/api/categories&tree=true&enrich=false"
        )

        data = json.loads(response.data)
        # Should be nested tree
        assert len(data) == 1  # One root
        assert data[0]["name"] == "Parent"
        assert len(data[0]["children"]) == 1
        assert data[0]["children"][0]["name"] == "Child"

    @patch("app.resources.export_json.requests.get")
    def test_export_with_custom_lookup_config(
        self, mock_get, client, auth_headers
    ):
        """Test export with custom lookup configuration."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {"id": "proj-1", "name": "Project A"}
        ]
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        lookup_config = json.dumps({"projects": ["code"]})

        auth_headers["set_cookie"](client)
        response = client.get(
            f"/export?type=json&url=http://localhost:5001/api/projects&lookup_config={lookup_config}"
        )
        assert response.status_code == 200

    @patch("app.resources.export_json.requests.get")
    def test_target_not_array(self, mock_get, client, auth_headers):
        """Test error when target returns non-array."""
        mock_response = Mock()
        mock_response.json.return_value = {"error": "Not an array"}
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get("/export?type=json&url=http://localhost:5001/api/users")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "array" in data["message"].lower()

    @patch("app.resources.export_json.requests.get")
    def test_timeout_error(self, mock_get, client, auth_headers):
        """Test timeout handling."""
        from requests.exceptions import Timeout

        mock_get.side_effect = Timeout("Connection timeout")

        auth_headers["set_cookie"](client)
        response = client.get("/export?type=json&url=http://localhost:5001/api/users")

        assert response.status_code == 504
        data = json.loads(response.data)
        assert "timeout" in data["message"].lower()

    @patch("app.resources.export_json.requests.get")
    def test_connection_error(self, mock_get, client, auth_headers):
        """Test connection error handling."""
        from requests.exceptions import ConnectionError

        mock_get.side_effect = ConnectionError("Cannot connect")

        auth_headers["set_cookie"](client)
        response = client.get("/export?type=json&url=http://localhost:5001/api/users")

        assert response.status_code == 502
        data = json.loads(response.data)
        assert "connect" in data["message"].lower()

    @patch("app.resources.export_json.requests.get")
    def test_http_error(self, mock_get, client, auth_headers):
        """Test HTTP error handling."""
        from requests.exceptions import HTTPError

        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.side_effect = HTTPError(response=mock_response)

        auth_headers["set_cookie"](client)
        response = client.get("/export?type=json&url=http://localhost:5001/api/users")

        assert response.status_code == 502
        data = json.loads(response.data)
        assert "404" in data["message"]

    @patch("app.resources.export_json.requests.get")
    def test_invalid_json_response(self, mock_get, client, auth_headers):
        """Test invalid JSON response handling."""
        mock_response = Mock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get("/export?type=json&url=http://localhost:5001/api/users")

        assert response.status_code == 502
        data = json.loads(response.data)
        assert "json" in data["message"].lower()

    @patch("app.resources.export_json.requests.get")
    def test_unexpected_error(self, mock_get, client, auth_headers):
        """Test unexpected error handling."""
        mock_get.side_effect = RuntimeError("Unexpected error")

        auth_headers["set_cookie"](client)
        response = client.get("/export?type=json&url=http://localhost:5001/api/users")

        assert response.status_code == 500
        data = json.loads(response.data)
        assert "internal server error" in data["message"].lower()

    @patch("app.resources.export_json.requests.get")
    def test_forwards_jwt_cookie(self, mock_get, client, auth_headers):
        """Test that JWT cookie is forwarded to target service."""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        client.get("/export?type=json&url=http://localhost:5001/api/users")

        # Verify JWT cookie was forwarded
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        assert "access_token" in call_kwargs["cookies"]

    def test_unauthorized_without_jwt(self, client):
        """Test that request without JWT returns 401."""
        response = client.get("/export?type=json&url=http://localhost:5001/api/users")
        assert response.status_code == 401
