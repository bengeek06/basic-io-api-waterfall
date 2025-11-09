"""Unit tests for CSV export resource."""

import csv
import io
import json
from unittest.mock import Mock, patch


class TestExportCsvResource:
    """Test cases for CSV export functionality using HTTP client."""

    def test_missing_url_parameter(self, client, auth_headers):
        """Test error when URL parameter is missing."""
        auth_headers["set_cookie"](client)
        response = client.get("/export?type=csv")
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "url" in data["error"].lower()

    @patch("app.resources.export_csv.requests.get")
    def test_successful_export(self, mock_get, client, auth_headers):
        """Test successful CSV export."""
        source_data = [
            {"id": "user-1", "name": "Alice", "email": "alice@test.com"},
            {"id": "user-2", "name": "Bob", "email": "bob@test.com"},
        ]

        mock_response = Mock()
        mock_response.json.return_value = source_data
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get(
            "/export?type=csv&url=http://test.com/api/users&enrich=false"
        )

        assert response.status_code == 200
        assert "text/csv" in response.content_type
        assert "attachment" in response.headers["Content-Disposition"]
        assert "export.csv" in response.headers["Content-Disposition"]

        # Parse CSV content
        csv_content = response.get_data(as_text=True)
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[0]["_original_id"] == "user-1"
        assert rows[1]["name"] == "Bob"

    @patch("app.resources.export_csv.requests.get")
    def test_export_with_enrichment(self, mock_get, client, auth_headers):
        """Test CSV export with FK enrichment."""
        source_data = [{"id": "1", "name": "Alice", "company_id": "comp-1"}]

        mock_response = Mock()
        mock_response.json.return_value = source_data
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get(
            "/export?type=csv&url=http://test.com/api/users&enrich=true"
        )

        assert response.status_code == 200
        assert "text/csv" in response.content_type

    @patch("app.resources.export_csv.requests.get")
    def test_export_empty_data(self, mock_get, client, auth_headers):
        """Test export with empty data."""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get("/export?type=csv&url=http://test.com/api/users")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert "error" in data

    @patch("app.resources.export_csv.requests.get")
    def test_export_non_array_response(self, mock_get, client, auth_headers):
        """Test export when target returns non-array."""
        mock_response = Mock()
        mock_response.json.return_value = {"error": "not an array"}
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get("/export?type=csv&url=http://test.com/api/users")

        assert response.status_code == 500
        data = json.loads(response.data)
        assert "error" in data

    @patch("app.resources.export_csv.requests.get")
    def test_export_with_complex_data(self, mock_get, client, auth_headers):
        """Test CSV export with nested objects and arrays."""
        source_data = [
            {
                "id": "1",
                "name": "Alice",
                "address": {"city": "Paris", "country": "France"},
                "tags": ["python", "flask"],
                "active": True,
                "score": 42,
            }
        ]

        mock_response = Mock()
        mock_response.json.return_value = source_data
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get(
            "/export?type=csv&url=http://test.com/api/users&enrich=false"
        )

        assert response.status_code == 200
        csv_content = response.get_data(as_text=True)
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)

        assert len(rows) == 1
        # Nested objects and arrays should be JSON strings in CSV
        assert "Paris" in rows[0]["address"]
        assert "python" in rows[0]["tags"]
        assert rows[0]["active"] == "True"
        assert rows[0]["score"] == "42"

    @patch("app.resources.export_csv.requests.get")
    def test_export_with_none_values(self, mock_get, client, auth_headers):
        """Test CSV export with None values."""
        source_data = [{"id": "1", "name": "Alice", "email": None}]

        mock_response = Mock()
        mock_response.json.return_value = source_data
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get(
            "/export?type=csv&url=http://test.com/api/users&enrich=false"
        )

        assert response.status_code == 200
        csv_content = response.get_data(as_text=True)
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["email"] == ""

    @patch("app.resources.export_csv.requests.get")
    def test_export_field_ordering(self, mock_get, client, auth_headers):
        """Test that CSV fields are ordered with _original_id and id first."""
        source_data = [
            {"name": "Alice", "age": 30, "id": "user-1"},
            {"email": "bob@test.com", "name": "Bob", "id": "user-2"},
        ]

        mock_response = Mock()
        mock_response.json.return_value = source_data
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get(
            "/export?type=csv&url=http://test.com/api/users&enrich=false"
        )

        assert response.status_code == 200
        csv_content = response.get_data(as_text=True)
        lines = csv_content.split("\n")
        header = lines[0]

        # _original_id and id should be first
        assert header.startswith("_original_id,id")

    @patch("app.resources.export_csv.requests.get")
    def test_export_timeout_error(self, mock_get, client, auth_headers):
        """Test export with timeout error."""
        from requests.exceptions import Timeout

        mock_get.side_effect = Timeout()

        auth_headers["set_cookie"](client)
        response = client.get("/export?type=csv&url=http://test.com/api/users")

        assert response.status_code == 504
        data = json.loads(response.data)
        assert "timeout" in data["error"].lower()

    @patch("app.resources.export_csv.requests.get")
    def test_export_connection_error(self, mock_get, client, auth_headers):
        """Test export with connection error."""
        from requests.exceptions import ConnectionError

        mock_get.side_effect = ConnectionError()

        auth_headers["set_cookie"](client)
        response = client.get("/export?type=csv&url=http://test.com/api/users")

        assert response.status_code == 502
        data = json.loads(response.data)
        assert "connection" in data["error"].lower()

    @patch("app.resources.export_csv.requests.get")
    def test_export_http_error(self, mock_get, client, auth_headers):
        """Test export with HTTP error from target."""
        from requests.exceptions import HTTPError

        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.side_effect = HTTPError(response=mock_response)

        auth_headers["set_cookie"](client)
        response = client.get("/export?type=csv&url=http://test.com/api/users")

        assert response.status_code == 502
        data = json.loads(response.data)
        assert "error" in data
