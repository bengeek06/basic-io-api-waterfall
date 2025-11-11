"""Unit tests for JSON import resource."""

import io
import json
from unittest.mock import Mock, patch

import requests
from requests.exceptions import (
    HTTPError,
    ConnectionError as RequestsConnectionError,
)


class TestImportJsonResource:
    """Tests for ImportJsonResource using HTTP client."""

    def test_missing_file(self, client, auth_headers):
        """Test error when no file is provided."""
        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={"url": "http://localhost:5001/api/users"},
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "no file" in data["message"].lower()

    def test_unauthorized_without_jwt(self, client):
        """Test that request without JWT returns 401."""
        file_content = json.dumps([]).encode("utf-8")
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(file_content), "data.json"),
            },
        )
        assert response.status_code == 401

    @patch("app.resources.import_json.requests.post")
    def test_successful_simple_import(self, mock_post, client, auth_headers):
        """Test successful simple import."""
        # Mock POST responses
        mock_response1 = Mock()
        mock_response1.json.return_value = {
            "id": "new-uuid-1",
            "name": "User 1",
        }
        mock_response1.status_code = 201

        mock_response2 = Mock()
        mock_response2.json.return_value = {
            "id": "new-uuid-2",
            "name": "User 2",
        }
        mock_response2.status_code = 201

        mock_post.side_effect = [mock_response1, mock_response2]

        # Prepare file
        file_data = [
            {"_original_id": "old-1", "name": "User 1"},
            {"_original_id": "old-2", "name": "User 2"},
        ]
        file_content = json.dumps(file_data).encode("utf-8")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(file_content), "data.json"),
                "resolve_refs": "false",
            },
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["import_report"]["success"] == 2
        assert data["import_report"]["failed"] == 0
        assert data["import_report"]["total"] == 2

    def test_empty_filename(self, client, auth_headers):
        """Test error when filename is empty."""
        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(b"[]"), ""),
            },
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        # Flask test client doesn't send file with empty filename
        assert "file" in data["message"].lower()

    def test_invalid_file_extension(self, client, auth_headers):
        """Test error when file is not JSON."""
        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(b"data"), "file.txt"),
            },
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "json" in data["message"].lower()

    def test_invalid_json_format(self, client, auth_headers):
        """Test error when file contains invalid JSON."""
        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(b"not json"), "data.json"),
            },
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "invalid json" in data["message"].lower()

    def test_json_not_array(self, client, auth_headers):
        """Test error when JSON is not an array."""
        auth_headers["set_cookie"](client)
        file_content = json.dumps({"key": "value"}).encode("utf-8")
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(file_content), "data.json"),
            },
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "array" in data["message"].lower()

    def test_missing_url_parameter(self, client, auth_headers):
        """Test error when URL parameter is missing."""
        auth_headers["set_cookie"](client)
        file_content = json.dumps([]).encode("utf-8")
        response = client.post(
            "/import?type=json",
            data={"file": (io.BytesIO(file_content), "data.json")},
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "url" in data["message"].lower()

    @patch("app.resources.import_json.requests.post")
    def test_import_tree_structure(self, mock_post, client, auth_headers):
        """Test importing tree structure with topological sort."""
        # Mock POST responses in order
        responses = [
            Mock(
                json=lambda: {"id": "new-parent", "name": "Parent"},
                status_code=201,
            ),
            Mock(
                json=lambda: {"id": "new-child", "name": "Child"},
                status_code=201,
            ),
        ]
        mock_post.side_effect = responses

        # Prepare file (child before parent to test sorting)
        file_data = [
            {
                "_original_id": "old-child",
                "name": "Child",
                "parent_id": "old-parent",
            },
            {
                "_original_id": "old-parent",
                "name": "Parent",
                "parent_id": None,
            },
        ]
        file_content = json.dumps(file_data).encode("utf-8")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/categories",
                "file": (io.BytesIO(file_content), "tree.json"),
                "resolve_refs": "false",
            },
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["import_report"]["success"] == 2

        # Verify parent was created before child
        first_call = mock_post.call_args_list[0]
        assert first_call[1]["json"]["name"] == "Parent"

        # Verify child has new parent_id
        second_call = mock_post.call_args_list[1]
        assert second_call[1]["json"]["parent_id"] == "new-parent"

    @patch("app.resources.import_json.requests.post")
    def test_import_nested_tree(self, mock_post, client, auth_headers):
        """Test importing nested tree structure."""
        responses = [
            Mock(
                json=lambda: {"id": "new-root", "name": "Root"},
                status_code=201,
            ),
            Mock(
                json=lambda: {"id": "new-child", "name": "Child"},
                status_code=201,
            ),
        ]
        mock_post.side_effect = responses

        # Nested tree structure
        file_data = [
            {
                "_original_id": "old-root",
                "name": "Root",
                "children": [
                    {
                        "_original_id": "old-child",
                        "name": "Child",
                        "children": [],
                    }
                ],
            }
        ]
        file_content = json.dumps(file_data).encode("utf-8")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/categories",
                "file": (io.BytesIO(file_content), "nested.json"),
                "resolve_refs": "false",
            },
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["import_report"]["success"] == 2

    @patch("app.resources.import_json.requests.get")
    @patch("app.resources.import_json.requests.post")
    def test_import_with_reference_resolution(
        self, mock_post, mock_get, client, auth_headers
    ):
        """Test import with foreign key resolution."""
        # Mock GET for reference resolution
        mock_get_response = Mock()
        mock_get_response.json.return_value = [
            {"id": "resolved-project-id", "name": "Project A"}
        ]
        mock_get_response.status_code = 200
        mock_get.return_value = mock_get_response

        # Mock POST for import
        mock_post_response = Mock()
        mock_post_response.json.return_value = {
            "id": "new-task-id",
            "name": "Task 1",
        }
        mock_post_response.status_code = 201
        mock_post.return_value = mock_post_response

        # File with references
        file_data = [
            {
                "_original_id": "old-task-1",
                "name": "Task 1",
                "_references": {
                    "project_id": {
                        "resource_type": "projects",
                        "lookup_field": "name",
                        "lookup_value": "Project A",
                        "original_id": "old-project-id",
                    }
                },
            }
        ]
        file_content = json.dumps(file_data).encode("utf-8")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/tasks",
                "file": (io.BytesIO(file_content), "tasks.json"),
                "resolve_refs": "true",
            },
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["import_report"]["success"] == 1
        assert data["resolution_report"]["resolved"] == 1

        # Verify resolved ID was used
        post_call = mock_post.call_args[1]["json"]
        assert post_call["project_id"] == "resolved-project-id"

    @patch("app.resources.import_json.requests.post")
    def test_partial_import_failure(self, mock_post, client, auth_headers):
        """Test partial import with some failures."""
        # First succeeds, second fails
        success_response = Mock()
        success_response.json.return_value = {
            "id": "new-id",
            "name": "User 1",
        }
        success_response.status_code = 201

        fail_response = Mock()
        fail_response.status_code = 400
        fail_response.text = "Validation error"

        mock_post.side_effect = [
            success_response,
            HTTPError(response=fail_response),
        ]

        file_data = [
            {"_original_id": "id-1", "name": "User 1"},
            {"_original_id": "id-2", "name": "User 2"},
        ]
        file_content = json.dumps(file_data).encode("utf-8")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(file_content), "data.json"),
                "resolve_refs": "false",
            },
        )

        assert response.status_code == 207  # Partial success
        data = json.loads(response.data)
        assert data["import_report"]["success"] == 1
        assert data["import_report"]["failed"] == 1
        assert len(data["import_report"]["errors"]) == 1

    @patch("app.resources.import_json.requests.post")
    def test_all_imports_fail(self, mock_post, client, auth_headers):
        """Test when all imports fail."""
        mock_post.side_effect = RequestsConnectionError("Cannot connect")

        file_data = [{"_original_id": "id-1", "name": "User 1"}]
        file_content = json.dumps(file_data).encode("utf-8")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(file_content), "data.json"),
                "resolve_refs": "false",
            },
        )

        assert response.status_code == 400  # All failed
        data = json.loads(response.data)
        assert data["import_report"]["success"] == 0
        assert data["import_report"]["failed"] == 1

    def test_circular_reference_error(self, client, auth_headers):
        """Test error when circular references detected."""
        file_data = [
            {"_original_id": "a", "name": "A", "parent_id": "b"},
            {"_original_id": "b", "name": "B", "parent_id": "a"},
        ]
        file_content = json.dumps(file_data).encode("utf-8")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/categories",
                "file": (io.BytesIO(file_content), "circular.json"),
                "resolve_refs": "false",
            },
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "circular" in data["message"].lower()

    @patch("app.resources.import_json.requests.post")
    def test_forwards_jwt_cookie(self, mock_post, client, auth_headers):
        """Test that JWT cookie is forwarded to target service."""
        mock_response = Mock()
        mock_response.json.return_value = {"id": "new-id", "name": "User"}
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        file_data = [{"_original_id": "old-id", "name": "User"}]
        file_content = json.dumps(file_data).encode("utf-8")

        auth_headers["set_cookie"](client)
        client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(file_content), "data.json"),
                "resolve_refs": "false",
            },
        )

        # Verify JWT cookie was forwarded
        mock_post.assert_called()
        call_kwargs = mock_post.call_args[1]
        assert "access_token" in call_kwargs["cookies"]

    def test_non_utf8_encoding(self, client, auth_headers):
        """Test error when file is not UTF-8 encoded."""
        auth_headers["set_cookie"](client)
        # Create non-UTF-8 content
        non_utf8_content = b"\xff\xfe"
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/users",
                "file": (io.BytesIO(non_utf8_content), "data.json"),
            },
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "utf-8" in data["message"].lower()

    @patch("app.resources.import_json.requests.get")
    @patch("app.resources.import_json.requests.post")
    def test_ambiguous_reference_resolution(
        self, mock_post, mock_get, client, auth_headers
    ):
        """Test import with ambiguous reference resolution."""
        # Mock GET returning multiple matches
        mock_get_response = Mock()
        mock_get_response.json.return_value = [
            {"id": "id-1", "name": "Project A"},
            {"id": "id-2", "name": "Project A"},
        ]
        mock_get_response.status_code = 200
        mock_get.return_value = mock_get_response

        # Mock POST for import
        mock_post_response = Mock()
        mock_post_response.json.return_value = {
            "id": "new-task-id",
            "name": "Task 1",
        }
        mock_post_response.status_code = 201
        mock_post.return_value = mock_post_response

        file_data = [
            {
                "_original_id": "old-task-1",
                "name": "Task 1",
                "_references": {
                    "project_id": {
                        "resource_type": "projects",
                        "lookup_field": "name",
                        "lookup_value": "Project A",
                        "original_id": "old-project-id",
                    }
                },
            }
        ]
        file_content = json.dumps(file_data).encode("utf-8")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/tasks",
                "file": (io.BytesIO(file_content), "tasks.json"),
                "resolve_refs": "true",
            },
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["resolution_report"]["ambiguous"] == 1

    @patch("app.resources.import_json.requests.get")
    @patch("app.resources.import_json.requests.post")
    def test_missing_reference_resolution(
        self, mock_post, mock_get, client, auth_headers
    ):
        """Test import with missing reference."""
        # Mock GET returning no matches
        mock_get_response = Mock()
        mock_get_response.json.return_value = []
        mock_get_response.status_code = 200
        mock_get.return_value = mock_get_response

        # Mock POST for import
        mock_post_response = Mock()
        mock_post_response.json.return_value = {
            "id": "new-task-id",
            "name": "Task 1",
        }
        mock_post_response.status_code = 201
        mock_post.return_value = mock_post_response

        file_data = [
            {
                "_original_id": "old-task-1",
                "name": "Task 1",
                "_references": {
                    "project_id": {
                        "resource_type": "projects",
                        "lookup_field": "name",
                        "lookup_value": "Project A",
                        "original_id": "old-project-id",
                    }
                },
            }
        ]
        file_content = json.dumps(file_data).encode("utf-8")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/tasks",
                "file": (io.BytesIO(file_content), "tasks.json"),
                "resolve_refs": "true",
            },
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["resolution_report"]["missing"] == 1

    @patch("app.resources.import_json.requests.get")
    @patch("app.resources.import_json.requests.post")
    def test_reference_resolution_with_error(
        self, mock_post, mock_get, client, auth_headers
    ):
        """Test import with reference resolution error."""
        # Mock GET throwing error
        mock_get.side_effect = RequestsConnectionError("Cannot connect")

        # Mock POST for import
        mock_post_response = Mock()
        mock_post_response.json.return_value = {
            "id": "new-task-id",
            "name": "Task 1",
        }
        mock_post_response.status_code = 201
        mock_post.return_value = mock_post_response

        file_data = [
            {
                "_original_id": "old-task-1",
                "name": "Task 1",
                "_references": {
                    "project_id": {
                        "resource_type": "projects",
                        "lookup_field": "name",
                        "lookup_value": "Project A",
                        "original_id": "old-project-id",
                    }
                },
            }
        ]
        file_content = json.dumps(file_data).encode("utf-8")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/tasks",
                "file": (io.BytesIO(file_content), "tasks.json"),
                "resolve_refs": "true",
            },
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["resolution_report"]["errors"] == 1

    @patch("app.resources.import_json.requests.post")
    def test_orphaned_child_with_failed_parent(
        self, mock_post, client, auth_headers
    ):
        """Test child with parent_id that failed import (line 226)."""
        # Create HTTPError for parent failure
        error_response = Mock()
        error_response.status_code = 500
        error_response.text = "Server error"
        parent_error = requests.exceptions.HTTPError(response=error_response)

        # Child succeeds
        child_response = Mock()
        child_response.status_code = 201
        child_response.json.return_value = {
            "id": "new-child-id",
            "name": "Child",
            "parent_id": None,
        }
        child_response.raise_for_status.return_value = None

        mock_post.side_effect = [parent_error, child_response]

        file_data = [
            {"_original_id": "parent-1", "name": "Parent", "parent_id": None},
            {
                "_original_id": "child-1",
                "name": "Child",
                "parent_id": "parent-1",
            },
        ]
        file_content = json.dumps(file_data).encode("utf-8")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/categories",
                "file": (io.BytesIO(file_content), "tree.json"),
                "resolve_refs": "false",
            },
        )

        # 207 partial success
        assert response.status_code == 207
        data = json.loads(response.data)
        assert data["import_report"]["success"] == 1
        assert data["import_report"]["failed"] == 1
        # Child has parent_id "parent-1" but parent-1 not in id_mapping
        # This triggers line 226 warning


class TestImportJsonAmbiguousAndMissingModes:
    """Tests for on_ambiguous and on_missing modes (Bug #4)."""

    @patch("app.resources.import_json.requests.get")
    @patch("app.resources.import_json.requests.post")
    def test_ambiguous_skip_mode_sets_null(
        self, mock_post, mock_get, client, auth_headers
    ):
        """Test ambiguous reference with skip mode sets FK to null."""
        # Mock GET returning 2 matches (ambiguous)
        mock_get_response = Mock()
        mock_get_response.json.return_value = [
            {"id": "id-1", "name": "Duplicate"},
            {"id": "id-2", "name": "Duplicate"},
        ]
        mock_get_response.status_code = 200
        mock_get.return_value = mock_get_response

        # Mock POST for import
        mock_post_response = Mock()
        mock_post_response.json.return_value = {
            "id": "new-task-id",
            "name": "Task 1",
            "project_id": None,
        }
        mock_post_response.status_code = 201
        mock_post.return_value = mock_post_response

        file_data = [
            {
                "_original_id": "task-1",
                "name": "Task 1",
                "_references": {
                    "project_id": {
                        "resource_type": "projects",
                        "lookup_field": "name",
                        "lookup_value": "Duplicate",
                        "original_id": "old-project-id",
                    }
                },
            }
        ]
        file_content = json.dumps(file_data).encode("utf-8")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/tasks",
                "file": (io.BytesIO(file_content), "tasks.json"),
                "resolve_refs": "true",
                "on_ambiguous": "skip",
            },
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["import_report"]["success"] == 1
        assert data["resolution_report"]["ambiguous"] == 1

        # Verify FK was set to None (not random ID)
        post_call = mock_post.call_args[1]["json"]
        assert post_call["project_id"] is None

    @patch("app.resources.import_json.requests.get")
    def test_ambiguous_fail_mode_returns_400(
        self, mock_get, client, auth_headers
    ):
        """Test ambiguous reference with fail mode returns 400."""
        # Mock GET returning 2 matches (ambiguous)
        mock_get_response = Mock()
        mock_get_response.json.return_value = [
            {"id": "id-1", "name": "Duplicate"},
            {"id": "id-2", "name": "Duplicate"},
        ]
        mock_get_response.status_code = 200
        mock_get.return_value = mock_get_response

        file_data = [
            {
                "_original_id": "task-1",
                "name": "Task 1",
                "_references": {
                    "project_id": {
                        "resource_type": "projects",
                        "lookup_field": "name",
                        "lookup_value": "Duplicate",
                        "original_id": "old-project-id",
                    }
                },
            }
        ]
        file_content = json.dumps(file_data).encode("utf-8")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/tasks",
                "file": (io.BytesIO(file_content), "tasks.json"),
                "resolve_refs": "true",
                "on_ambiguous": "fail",
            },
        )

        # Should fail with 400
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "ambiguous" in data["message"].lower()
        assert data["resolution_report"]["ambiguous"] == 1
        # No import should have occurred
        assert "import_report" not in data

    @patch("app.resources.import_json.requests.get")
    @patch("app.resources.import_json.requests.post")
    def test_missing_skip_mode_sets_null(
        self, mock_post, mock_get, client, auth_headers
    ):
        """Test missing reference with skip mode sets FK to null."""
        # Mock GET returning no matches
        mock_get_response = Mock()
        mock_get_response.json.return_value = []
        mock_get_response.status_code = 200
        mock_get.return_value = mock_get_response

        # Mock POST for import
        mock_post_response = Mock()
        mock_post_response.json.return_value = {
            "id": "new-task-id",
            "name": "Task 1",
            "project_id": None,
        }
        mock_post_response.status_code = 201
        mock_post.return_value = mock_post_response

        file_data = [
            {
                "_original_id": "task-1",
                "name": "Task 1",
                "_references": {
                    "project_id": {
                        "resource_type": "projects",
                        "lookup_field": "name",
                        "lookup_value": "NonExistent",
                        "original_id": "old-project-id",
                    }
                },
            }
        ]
        file_content = json.dumps(file_data).encode("utf-8")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/tasks",
                "file": (io.BytesIO(file_content), "tasks.json"),
                "resolve_refs": "true",
                "on_missing": "skip",
            },
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["import_report"]["success"] == 1
        assert data["resolution_report"]["missing"] == 1

        # Verify FK was set to None
        post_call = mock_post.call_args[1]["json"]
        assert post_call["project_id"] is None

    @patch("app.resources.import_json.requests.get")
    def test_missing_fail_mode_returns_400(
        self, mock_get, client, auth_headers
    ):
        """Test missing reference with fail mode returns 400."""
        # Mock GET returning no matches
        mock_get_response = Mock()
        mock_get_response.json.return_value = []
        mock_get_response.status_code = 200
        mock_get.return_value = mock_get_response

        file_data = [
            {
                "_original_id": "task-1",
                "name": "Task 1",
                "_references": {
                    "project_id": {
                        "resource_type": "projects",
                        "lookup_field": "name",
                        "lookup_value": "NonExistent",
                        "original_id": "old-project-id",
                    }
                },
            }
        ]
        file_content = json.dumps(file_data).encode("utf-8")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/tasks",
                "file": (io.BytesIO(file_content), "tasks.json"),
                "resolve_refs": "true",
                "on_missing": "fail",
            },
        )

        # Should fail with 400
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "missing" in data["message"].lower()
        assert data["resolution_report"]["missing"] == 1
        # No import should have occurred
        assert "import_report" not in data

    def test_invalid_on_ambiguous_mode(self, client, auth_headers):
        """Test error when on_ambiguous mode is invalid."""
        file_content = json.dumps([{"name": "Test"}]).encode("utf-8")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/tasks",
                "file": (io.BytesIO(file_content), "tasks.json"),
                "on_ambiguous": "invalid_mode",
            },
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "on_ambiguous" in data["message"].lower()
        assert (
            "skip" in data["message"].lower()
            or "fail" in data["message"].lower()
        )

    def test_invalid_on_missing_mode(self, client, auth_headers):
        """Test error when on_missing mode is invalid."""
        file_content = json.dumps([{"name": "Test"}]).encode("utf-8")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/tasks",
                "file": (io.BytesIO(file_content), "tasks.json"),
                "on_missing": "invalid_mode",
            },
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "on_missing" in data["message"].lower()
        assert (
            "skip" in data["message"].lower()
            or "fail" in data["message"].lower()
        )

    @patch("app.resources.import_json.requests.get")
    @patch("app.resources.import_json.requests.post")
    def test_mixed_ambiguous_and_missing_with_skip(
        self, mock_post, mock_get, client, auth_headers
    ):
        """Test handling both ambiguous and missing refs with skip mode."""

        # Mock GET responses for different fields
        def get_side_effect(url, **kwargs):
            if "projects" in url:
                # Ambiguous
                response = Mock()
                response.json.return_value = [
                    {"id": "id-1", "name": "Duplicate"},
                    {"id": "id-2", "name": "Duplicate"},
                ]
                response.status_code = 200
                return response
            else:  # users
                # Missing
                response = Mock()
                response.json.return_value = []
                response.status_code = 200
                return response

        mock_get.side_effect = get_side_effect

        # Mock POST for import
        mock_post_response = Mock()
        mock_post_response.json.return_value = {
            "id": "new-task-id",
            "name": "Task 1",
        }
        mock_post_response.status_code = 201
        mock_post.return_value = mock_post_response

        file_data = [
            {
                "_original_id": "task-1",
                "name": "Task 1",
                "_references": {
                    "project_id": {
                        "resource_type": "projects",
                        "lookup_field": "name",
                        "lookup_value": "Duplicate",
                        "original_id": "old-project",
                    },
                    "assigned_to": {
                        "resource_type": "users",
                        "lookup_field": "email",
                        "lookup_value": "missing@example.com",
                        "original_id": "old-user",
                    },
                },
            }
        ]
        file_content = json.dumps(file_data).encode("utf-8")

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=json",
            data={
                "url": "http://localhost:5001/api/tasks",
                "file": (io.BytesIO(file_content), "tasks.json"),
                "resolve_refs": "true",
                "on_ambiguous": "skip",
                "on_missing": "skip",
            },
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["import_report"]["success"] == 1
        assert data["resolution_report"]["ambiguous"] == 1
        assert data["resolution_report"]["missing"] == 1

        # Both FKs should be None
        post_call = mock_post.call_args[1]["json"]
        assert post_call["project_id"] is None
        assert post_call["assigned_to"] is None
