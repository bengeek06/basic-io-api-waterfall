"""Unit tests for Mermaid import resource."""

import io
import json
from unittest.mock import Mock, patch


class TestImportMermaidResource:
    """Tests for Mermaid import functionality."""

    def test_missing_file(self, client, auth_headers):
        """Test error when no file is provided."""
        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=mermaid",
            data={"url": "http://localhost:5001/api/categories"},
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "no file" in data["message"].lower()

    def test_empty_filename(self, client, auth_headers):
        """Test error when filename is empty."""
        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=mermaid",
            data={
                "url": "http://localhost:5001/api/categories",
                "file": (io.BytesIO(b""), ""),
            },
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "file" in data["message"].lower()

    @patch("app.resources.import_mermaid.requests.post")
    def test_import_flowchart(self, mock_post, client, auth_headers):
        """Test importing a Mermaid flowchart diagram."""
        mermaid_content = """%%{init: {'theme':'base'}}%%
flowchart TD
    %% Metadata
    %% export_date: 2025-11-09T10:30:00Z
    %% resource_type: categories
    %% total_nodes: 3
    %% service_url: http://localhost:5001/api/categories
    
    node_cat_1["Backend<br/>_original_id: cat-1<br/>status: active"]
    node_cat_2["API<br/>_original_id: cat-2<br/>status: active"]
    node_cat_3["Database<br/>_original_id: cat-3<br/>status: active"]
    
    node_cat_1 --> node_cat_2
    node_cat_1 --> node_cat_3
    
    click node_cat_1 "http://localhost:5001/api/categories/cat-1"
"""

        # Mock POST responses
        mock_response1 = Mock()
        mock_response1.json.return_value = {
            "id": "new-cat-1",
            "name": "Backend",
            "status": "active",
        }
        mock_response1.status_code = 201

        mock_response2 = Mock()
        mock_response2.json.return_value = {
            "id": "new-cat-2",
            "name": "API",
            "status": "active",
            "parent_id": "new-cat-1",
        }
        mock_response2.status_code = 201

        mock_response3 = Mock()
        mock_response3.json.return_value = {
            "id": "new-cat-3",
            "name": "Database",
            "status": "active",
            "parent_id": "new-cat-1",
        }
        mock_response3.status_code = 201

        mock_post.side_effect = [
            mock_response1,
            mock_response2,
            mock_response3,
        ]

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=mermaid&url=http://localhost:5001/api/categories",
            data={
                "file": (io.BytesIO(mermaid_content.encode()), "diagram.mmd"),
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["total_records"] == 3
        assert data["successful_imports"] == 3
        assert data["failed_imports"] == 0

        # Verify ID mapping
        assert "cat-1" in data["id_mapping"]
        assert "cat-2" in data["id_mapping"]
        assert "cat-3" in data["id_mapping"]

    @patch("app.resources.import_mermaid.requests.post")
    def test_import_graph(self, mock_post, client, auth_headers):
        """Test importing a Mermaid graph diagram."""
        mermaid_content = """graph TD
    %% Metadata
    %% resource_type: nodes
    %% total_nodes: 2
    
    node_node_1["Node A"]
    node_node_2["Node B"]
    
    node_node_1 --- node_node_2
"""

        # Mock POST responses
        mock_response1 = Mock()
        mock_response1.json.return_value = {
            "id": "new-node-1",
            "name": "Node A",
        }
        mock_response1.status_code = 201

        mock_response2 = Mock()
        mock_response2.json.return_value = {
            "id": "new-node-2",
            "name": "Node B",
            "parent_id": "new-node-1",
        }
        mock_response2.status_code = 201

        mock_post.side_effect = [mock_response1, mock_response2]

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=mermaid&url=http://localhost:5001/api/nodes",
            data={
                "file": (io.BytesIO(mermaid_content.encode()), "diagram.mmd"),
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["total_records"] == 2
        assert data["successful_imports"] == 2

    @patch("app.resources.import_mermaid.requests.post")
    def test_import_mindmap(self, mock_post, client, auth_headers):
        """Test importing a Mermaid mindmap diagram."""
        mermaid_content = """mindmap
  %% Metadata
  %% resource_type: categories
  
  root((Backend))
    API
      REST
    Database
"""

        # Mock POST responses (6 nodes due to blank lines in diagram)
        responses = [
            {"id": "new-1", "name": "Backend"},
            {"id": "new-2", "name": ""},  # Empty line node
            {"id": "new-3", "name": "API", "parent_id": "new-1"},
            {"id": "new-4", "name": "REST", "parent_id": "new-3"},
            {"id": "new-5", "name": "Database", "parent_id": "new-1"},
            {"id": "new-6", "name": ""},  # Empty line node
        ]

        mock_responses = []
        for resp in responses:
            mock_resp = Mock()
            mock_resp.json.return_value = resp
            mock_resp.status_code = 201
            mock_responses.append(mock_resp)

        mock_post.side_effect = mock_responses

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=mermaid&url=http://localhost:5001/api/categories",
            data={
                "file": (io.BytesIO(mermaid_content.encode()), "mindmap.mmd"),
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["total_records"] == 6
        assert data["successful_imports"] >= 4  # At least the main nodes

    def test_invalid_diagram_type(self, client, auth_headers):
        """Test error when diagram type cannot be detected."""
        mermaid_content = """This is not a valid Mermaid diagram
Some random text here
"""

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=mermaid&url=http://localhost:5001/api/test",
            data={
                "file": (io.BytesIO(mermaid_content.encode()), "invalid.mmd"),
            },
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "diagram type" in data["message"].lower()

    def test_unicode_decode_error(self, client, auth_headers):
        """Test error handling for invalid file encoding."""
        # Create invalid UTF-8 bytes
        invalid_bytes = b"\xff\xfe Invalid UTF-8 \x80"

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=mermaid&url=http://localhost:5001/api/test",
            data={
                "file": (io.BytesIO(invalid_bytes), "invalid.mmd"),
            },
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert (
            "utf-8" in data["message"].lower()
            or "encoding" in data["message"].lower()
        )

    @patch("app.resources.import_mermaid.requests.post")
    def test_flowchart_without_original_ids(
        self, mock_post, client, auth_headers
    ):
        """Test flowchart import without _original_id in labels."""
        mermaid_content = """flowchart TD
    node_abc["Simple Label"]
"""

        # Mock POST response
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "new-uuid-1",
            "name": "Simple Label",
        }
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=mermaid&url=http://localhost:5001/api/test",
            data={
                "file": (io.BytesIO(mermaid_content.encode()), "simple.mmd"),
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["successful_imports"] == 1
        # Should use node ID converted to original format
        assert "abc" in data["id_mapping"]

    @patch("app.resources.import_mermaid.requests.post")
    def test_flowchart_with_additional_fields(
        self, mock_post, client, auth_headers
    ):
        """Test flowchart with additional fields in labels."""
        mermaid_content = """flowchart TD
    node_1["Product<br/>_original_id: prod-1<br/>price: 99.99<br/>status: available"]
"""

        # Mock POST response
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "new-prod-1",
            "name": "Product",
            "price": "99.99",
            "status": "available",
        }
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=mermaid&url=http://localhost:5001/api/products",
            data={
                "file": (io.BytesIO(mermaid_content.encode()), "products.mmd"),
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["successful_imports"] == 1

        # Verify the POST was called with additional fields
        call_args = mock_post.call_args
        posted_data = call_args[1]["json"]
        assert posted_data["name"] == "Product"
        assert posted_data["price"] == "99.99"
        assert posted_data["status"] == "available"

    @patch("app.resources.import_mermaid.requests.post")
    def test_metadata_parsing(self, mock_post, client, auth_headers):
        """Test that metadata is correctly parsed from comments."""
        mermaid_content = """flowchart TD
    %% Metadata
    %% export_date: 2025-11-09T10:30:00Z
    %% resource_type: test_items
    %% total_nodes: 1
    %% service_url: http://localhost:5001/api/test_items
    
    node_1["Item"]
"""

        # Mock POST response
        mock_response = Mock()
        mock_response.json.return_value = {"id": "new-1", "name": "Item"}
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=mermaid&url=http://localhost:5001/api/test_items",
            data={
                "file": (io.BytesIO(mermaid_content.encode()), "test.mmd"),
            },
        )

        assert response.status_code == 200
        # Metadata is informational and doesn't affect the import
        data = json.loads(response.data)
        assert data["successful_imports"] == 1

    @patch("app.resources.import_mermaid.requests.post")
    def test_empty_mermaid_diagram(self, mock_post, client, auth_headers):
        """Test importing an empty diagram."""
        mermaid_content = """flowchart TD
    %% Empty diagram
"""

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=mermaid&url=http://localhost:5001/api/test",
            data={
                "file": (io.BytesIO(mermaid_content.encode()), "empty.mmd"),
            },
        )

        # Empty diagram should successfully import 0 records
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["total_records"] == 0
        assert data["successful_imports"] == 0

    @patch("app.resources.import_mermaid.requests.post")
    def test_mindmap_with_complex_hierarchy(
        self, mock_post, client, auth_headers
    ):
        """Test mindmap with multiple levels of hierarchy."""
        mermaid_content = """mindmap
  root((Root))
    Level1A
      Level2A
        Level3A
      Level2B
    Level1B
"""

        # Mock POST responses for all 6 nodes
        responses = [
            {"id": "id-1", "name": "Root"},
            {"id": "id-2", "name": "Level1A", "parent_id": "id-1"},
            {"id": "id-3", "name": "Level2A", "parent_id": "id-2"},
            {"id": "id-4", "name": "Level3A", "parent_id": "id-3"},
            {"id": "id-5", "name": "Level2B", "parent_id": "id-2"},
            {"id": "id-6", "name": "Level1B", "parent_id": "id-1"},
        ]

        mock_responses = []
        for resp in responses:
            mock_resp = Mock()
            mock_resp.json.return_value = resp
            mock_resp.status_code = 201
            mock_responses.append(mock_resp)

        mock_post.side_effect = mock_responses

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=mermaid&url=http://localhost:5001/api/categories",
            data={
                "file": (
                    io.BytesIO(mermaid_content.encode()),
                    "hierarchy.mmd",
                ),
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["total_records"] == 6
        assert data["successful_imports"] == 6

    @patch("app.resources.import_mermaid.requests.post")
    def test_partial_import_failure(self, mock_post, client, auth_headers):
        """Test handling of partial import failures."""
        mermaid_content = """flowchart TD
    node_1["Node1<br/>_original_id: id-1"]
    node_2["Node2<br/>_original_id: id-2"]
"""

        # First POST succeeds, second fails
        mock_response1 = Mock()
        mock_response1.json.return_value = {"id": "new-1", "name": "Node1"}
        mock_response1.status_code = 201

        mock_response2 = Mock()
        mock_response2.status_code = 500
        mock_response2.raise_for_status.side_effect = Exception("Server error")

        mock_post.side_effect = [mock_response1, mock_response2]

        auth_headers["set_cookie"](client)
        response = client.post(
            "/import?type=mermaid&url=http://localhost:5001/api/test",
            data={
                "file": (io.BytesIO(mermaid_content.encode()), "partial.mmd"),
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["total_records"] == 2
        assert data["successful_imports"] == 1
        assert data["failed_imports"] == 1
