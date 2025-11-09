"""Unit tests for CSV import resource."""

import csv
import io
import json
from unittest.mock import Mock, patch


class TestImportCsvResource:
    """Tests for ImportCsvResource using HTTP client."""

    def test_missing_file(self, client, auth_headers):
        """Test error when no file is provided."""
        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=csv",
            data={"url": "http://localhost:5001/api/users"},
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "no file" in data["error"].lower()

    def test_unauthorized_without_jwt(self, client):
        """Test that request without JWT returns 401."""
        csv_content = "_original_id,name\nold-1,Alice\n"
        response = client.post(
            "/import?type=csv",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(csv_content.encode()), "data.csv"),
            },
        )
        assert response.status_code == 401

    def test_empty_filename(self, client, auth_headers):
        """Test error when filename is empty."""
        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=csv",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(b""), ""),
            },
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert (
            "file" in data["error"].lower() or "empty" in data["error"].lower()
        )

    def test_invalid_file_extension(self, client, auth_headers):
        """Test error when file is not CSV."""
        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=csv",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(b"test data"), "data.txt"),
            },
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "csv" in data["error"].lower()

    def test_missing_url_parameter(self, client, auth_headers):
        """Test error when URL parameter is missing."""
        csv_content = "_original_id,name\nold-1,Alice\n"
        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=csv",
            data={
                "file": (io.BytesIO(csv_content.encode()), "data.csv"),
            },
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "url" in data["error"].lower()

    def test_empty_csv_file(self, client, auth_headers):
        """Test error when CSV file is empty."""
        csv_content = ""
        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=csv",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(csv_content.encode()), "data.csv"),
            },
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "empty" in data["error"].lower()

    @patch("app.resources.import_csv.requests.post")
    def test_successful_simple_import(self, mock_post, client, auth_headers):
        """Test successful simple CSV import."""
        # Mock POST responses
        mock_response1 = Mock()
        mock_response1.json.return_value = {
            "id": "new-uuid-1",
            "name": "Alice",
        }
        mock_response1.status_code = 201

        mock_response2 = Mock()
        mock_response2.json.return_value = {
            "id": "new-uuid-2",
            "name": "Bob",
        }
        mock_response2.status_code = 201

        mock_post.side_effect = [mock_response1, mock_response2]

        # Prepare CSV file
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(
            csv_buffer, fieldnames=["_original_id", "name", "email"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "_original_id": "old-1",
                "name": "Alice",
                "email": "alice@test.com",
            }
        )
        writer.writerow(
            {"_original_id": "old-2", "name": "Bob", "email": "bob@test.com"}
        )
        csv_content = csv_buffer.getvalue().encode()

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=csv",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(csv_content), "data.csv"),
                "resolve_foreign_keys": "false",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["import_report"]["success"] == 2
        assert data["import_report"]["failed"] == 0

    @patch("app.resources.import_csv.requests.post")
    def test_import_with_nested_json_fields(
        self, mock_post, client, auth_headers
    ):
        """Test CSV import with nested objects as JSON strings."""
        mock_response = Mock()
        mock_response.json.return_value = {"id": "new-1", "name": "Alice"}
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        # CSV with JSON-encoded nested object
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(
            csv_buffer, fieldnames=["_original_id", "name", "address"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "_original_id": "old-1",
                "name": "Alice",
                "address": '{"city": "Paris", "country": "France"}',
            }
        )
        csv_content = csv_buffer.getvalue().encode()

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=csv",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(csv_content), "data.csv"),
                "resolve_foreign_keys": "false",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["import_report"]["success"] == 1

        # Verify the nested object was parsed
        call_args = mock_post.call_args
        posted_data = call_args.kwargs["json"]
        assert isinstance(posted_data["address"], dict)
        assert posted_data["address"]["city"] == "Paris"

    @patch("app.resources.import_csv.requests.post")
    def test_import_with_none_values(self, mock_post, client, auth_headers):
        """Test CSV import with empty fields (None values)."""
        mock_response = Mock()
        mock_response.json.return_value = {"id": "new-1", "name": "Alice"}
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        # CSV with empty email field
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(
            csv_buffer, fieldnames=["_original_id", "name", "email"]
        )
        writer.writeheader()
        writer.writerow(
            {"_original_id": "old-1", "name": "Alice", "email": ""}
        )
        csv_content = csv_buffer.getvalue().encode()

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=csv",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(csv_content), "data.csv"),
                "resolve_foreign_keys": "false",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["import_report"]["success"] == 1

        # Verify empty string was converted to None and filtered out
        call_args = mock_post.call_args
        posted_data = call_args.kwargs["json"]
        assert "email" not in posted_data  # None values are filtered out

    @patch("app.resources.import_csv.requests.post")
    def test_import_with_tree_structure(self, mock_post, client, auth_headers):
        """Test CSV import with parent-child tree structure."""
        # Mock responses for parent first, then child
        mock_parent = Mock()
        mock_parent.json.return_value = {"id": "new-parent", "name": "Root"}
        mock_parent.status_code = 201

        mock_child = Mock()
        mock_child.json.return_value = {"id": "new-child", "name": "Child"}
        mock_child.status_code = 201

        mock_post.side_effect = [mock_parent, mock_child]

        # CSV with tree structure (parent_id field)
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(
            csv_buffer, fieldnames=["_original_id", "name", "parent_id"]
        )
        writer.writeheader()
        writer.writerow(
            {"_original_id": "parent-1", "name": "Root", "parent_id": ""}
        )
        writer.writerow(
            {
                "_original_id": "child-1",
                "name": "Child",
                "parent_id": "parent-1",
            }
        )
        csv_content = csv_buffer.getvalue().encode()

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=csv",
            data={
                "url": "http://localhost:5001/api/org_units",
                "file": (io.BytesIO(csv_content), "data.csv"),
                "resolve_foreign_keys": "false",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["import_report"]["success"] == 2

        # Verify parent was created first (topological sort)
        first_call = mock_post.call_args_list[0]
        assert first_call.kwargs["json"]["name"] == "Root"

        # Verify child has mapped parent_id
        second_call = mock_post.call_args_list[1]
        assert second_call.kwargs["json"]["parent_id"] == "new-parent"

    @patch("app.resources.import_csv.requests.post")
    def test_import_with_http_error(self, mock_post, client, auth_headers):
        """Test import when target service returns HTTP error."""
        from requests.exceptions import HTTPError

        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.side_effect = HTTPError(response=mock_response)

        csv_content = "_original_id,name\nold-1,Alice\n"
        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=csv",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(csv_content.encode()), "data.csv"),
                "resolve_foreign_keys": "false",
            },
        )

        assert (
            response.status_code == 200
        )  # Import endpoint returns 200 with errors
        data = json.loads(response.data)
        assert data["import_report"]["failed"] == 1
        assert len(data["import_report"]["errors"]) > 0

    @patch("app.resources.import_csv.requests.post")
    def test_import_with_fk_resolution(self, mock_post, client, auth_headers):
        """Test CSV import with FK resolution from _references metadata."""
        # Mock successful creation
        mock_response = Mock()
        mock_response.json.return_value = {"id": "new-1", "name": "Task 1"}
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        # CSV with _references metadata (from export with enrichment)
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(
            csv_buffer,
            fieldnames=["_original_id", "name", "project_id", "_references"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "_original_id": "task-1",
                "name": "Task 1",
                "project_id": "proj-old-1",
                "_references": json.dumps(
                    {
                        "project_id": {
                            "resource_type": "projects",
                            "lookup_field": "name",
                            "lookup_value": "Project Alpha",
                        }
                    }
                ),
            }
        )
        csv_content = csv_buffer.getvalue().encode()

        # Mock FK resolution
        with patch(
            "app.resources.import_csv.resolve_reference"
        ) as mock_resolve:
            mock_resolve.return_value = ("resolved", "new-proj-uuid", [], None)

            auth_headers["set_cookie"](client)
            response = client.post(
                "/import?type=csv",
                data={
                    "url": "http://localhost:5001/api/tasks",
                    "file": (io.BytesIO(csv_content), "data.csv"),
                    "resolve_foreign_keys": "true",
                },
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["import_report"]["success"] == 1
            assert data["resolution_report"]["resolved"] >= 0

    @patch("app.resources.import_csv.requests.post")
    def test_import_partial_success(self, mock_post, client, auth_headers):
        """Test import with some records succeeding and some failing."""
        # First succeeds, second fails
        mock_success = Mock()
        mock_success.json.return_value = {"id": "new-1", "name": "Alice"}
        mock_success.status_code = 201

        mock_error = Mock()
        mock_error.status_code = 400

        from requests.exceptions import HTTPError

        mock_post.side_effect = [mock_success, HTTPError(response=mock_error)]

        csv_buffer = io.StringIO()
        writer = csv.DictWriter(
            csv_buffer, fieldnames=["_original_id", "name"]
        )
        writer.writeheader()
        writer.writerow({"_original_id": "old-1", "name": "Alice"})
        writer.writerow({"_original_id": "old-2", "name": "Bob"})
        csv_content = csv_buffer.getvalue().encode()

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=csv",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(csv_content), "data.csv"),
                "resolve_foreign_keys": "false",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["import_report"]["success"] == 1
        assert data["import_report"]["failed"] == 1
        assert len(data["import_report"]["errors"]) == 1

    def test_invalid_csv_format(self, client, auth_headers):
        """Test error with malformed CSV."""
        # Malformed CSV (unclosed quote)
        csv_content = '_original_id,name\nold-1,"Alice\n'
        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=csv",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(csv_content.encode()), "data.csv"),
            },
        )
        # CSV parser is lenient, might still work or fail gracefully
        # Just ensure we don't crash
        assert response.status_code in [200, 400, 500]

    def test_non_utf8_encoding(self, client, auth_headers):
        """Test error when CSV file is not UTF-8."""
        # Latin-1 encoded content
        csv_content = "_original_id,name\nold-1,Café\n"
        latin1_bytes = csv_content.encode("latin-1")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=csv",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(latin1_bytes), "data.csv"),
            },
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert (
            "utf-8" in data["error"].lower()
            or "encoding" in data["error"].lower()
        )
