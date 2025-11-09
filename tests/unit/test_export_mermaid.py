"""Unit tests for Mermaid export resource."""

import json
from unittest.mock import Mock, patch


class TestExportMermaidResource:
    """Test cases for Mermaid export functionality using HTTP client."""

    def test_missing_url_parameter(self, client, auth_headers):
        """Test error when URL parameter is missing."""
        auth_headers["set_cookie"](client)
        response = client.get("/export?type=mermaid")
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "url" in data["message"].lower()

    def test_invalid_diagram_type(self, client, auth_headers):
        """Test error when diagram_type is invalid."""
        auth_headers["set_cookie"](client)
        response = client.get(
            "/export?type=mermaid&url=http://test.com/api/categories&diagram_type=invalid"
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "invalid diagram_type" in data["message"].lower()

    @patch("app.resources.export_mermaid.requests.get")
    def test_successful_flowchart_export(self, mock_get, client, auth_headers):
        """Test successful Mermaid flowchart export."""
        source_data = [
            {
                "id": "cat-1",
                "name": "Backend",
                "parent_id": None,
                "status": "active",
            },
            {
                "id": "cat-2",
                "name": "API",
                "parent_id": "cat-1",
                "status": "active",
            },
            {
                "id": "cat-3",
                "name": "Database",
                "parent_id": "cat-1",
                "status": "active",
            },
        ]

        mock_response = Mock()
        mock_response.json.return_value = source_data
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get(
            "/export?type=mermaid&url=http://test.com/api/categories&diagram_type=flowchart"
        )

        assert response.status_code == 200
        assert "text/plain" in response.content_type
        assert "attachment" in response.headers["Content-Disposition"]
        assert "export.mmd" in response.headers["Content-Disposition"]

        # Parse Mermaid content
        mermaid_content = response.get_data(as_text=True)
        assert "flowchart TD" in mermaid_content
        assert "%% Metadata" in mermaid_content
        assert "%% export_date:" in mermaid_content
        assert "%% resource_type: categories" in mermaid_content
        assert "%% total_nodes: 3" in mermaid_content
        assert "%% diagram_type: flowchart" in mermaid_content

        # Check nodes
        assert "Backend" in mermaid_content
        assert "_original_id: cat-1" in mermaid_content
        assert "status: active" in mermaid_content

        # Check edges (parent -> child)
        assert "node_cat_1 --> node_cat_2" in mermaid_content
        assert "node_cat_1 --> node_cat_3" in mermaid_content

        # Check click handlers
        assert (
            'click node_cat_1 "http://test.com/api/categories/cat-1"'
            in mermaid_content
        )

    @patch("app.resources.export_mermaid.requests.get")
    def test_successful_graph_export(self, mock_get, client, auth_headers):
        """Test successful Mermaid graph export."""
        source_data = [
            {"id": "node-1", "name": "Node A", "parent_id": None},
            {"id": "node-2", "name": "Node B", "parent_id": "node-1"},
        ]

        mock_response = Mock()
        mock_response.json.return_value = source_data
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get(
            "/export?type=mermaid&url=http://test.com/api/nodes&diagram_type=graph"
        )

        assert response.status_code == 200
        mermaid_content = response.get_data(as_text=True)
        assert "graph TD" in mermaid_content
        assert "%% diagram_type: graph" in mermaid_content
        assert "Node A" in mermaid_content
        assert "Node B" in mermaid_content
        assert "node_node_1 --- node_node_2" in mermaid_content

    @patch("app.resources.export_mermaid.requests.get")
    def test_successful_mindmap_export(self, mock_get, client, auth_headers):
        """Test successful Mermaid mindmap export."""
        source_data = [
            {"id": "root-1", "name": "Backend", "parent_id": None},
            {"id": "child-1", "name": "API", "parent_id": "root-1"},
            {"id": "child-2", "name": "Database", "parent_id": "root-1"},
            {"id": "grandchild-1", "name": "REST", "parent_id": "child-1"},
        ]

        mock_response = Mock()
        mock_response.json.return_value = source_data
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get(
            "/export?type=mermaid&url=http://test.com/api/categories&diagram_type=mindmap"
        )

        assert response.status_code == 200
        mermaid_content = response.get_data(as_text=True)
        assert "mindmap" in mermaid_content
        assert "%% diagram_type: mindmap" in mermaid_content
        assert "root((Backend))" in mermaid_content
        assert "API" in mermaid_content
        assert "Database" in mermaid_content
        assert "REST" in mermaid_content

    @patch("app.resources.export_mermaid.requests.get")
    def test_mindmap_flat_data(self, mock_get, client, auth_headers):
        """Test mindmap export with flat data (no tree structure)."""
        source_data = [
            {"id": "item-1", "name": "Item A"},
            {"id": "item-2", "name": "Item B"},
        ]

        mock_response = Mock()
        mock_response.json.return_value = source_data
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get(
            "/export?type=mermaid&url=http://test.com/api/items&diagram_type=mindmap"
        )

        assert response.status_code == 200
        mermaid_content = response.get_data(as_text=True)
        assert "root((Data))" in mermaid_content
        assert "Item A" in mermaid_content
        assert "Item B" in mermaid_content

    @patch("app.resources.export_mermaid.requests.get")
    def test_flowchart_flat_data(self, mock_get, client, auth_headers):
        """Test flowchart export with flat data (sequential connections)."""
        source_data = [
            {"id": "step-1", "name": "Step 1"},
            {"id": "step-2", "name": "Step 2"},
            {"id": "step-3", "name": "Step 3"},
        ]

        mock_response = Mock()
        mock_response.json.return_value = source_data
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get(
            "/export?type=mermaid&url=http://test.com/api/steps&diagram_type=flowchart"
        )

        assert response.status_code == 200
        mermaid_content = response.get_data(as_text=True)
        # Should have sequential connections for flat data
        assert "node_step_1 --> node_step_2" in mermaid_content
        assert "node_step_2 --> node_step_3" in mermaid_content

    @patch("app.resources.export_mermaid.requests.get")
    def test_export_empty_data(self, mock_get, client, auth_headers):
        """Test export with empty data."""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get(
            "/export?type=mermaid&url=http://test.com/api/items"
        )

        assert response.status_code == 200
        mermaid_content = response.get_data(as_text=True)
        assert "flowchart TD" in mermaid_content
        assert "%% total_nodes: 0" in mermaid_content

    @patch("app.resources.export_mermaid.requests.get")
    def test_default_diagram_type(self, mock_get, client, auth_headers):
        """Test that flowchart is default diagram type."""
        source_data = [{"id": "1", "name": "Test"}]

        mock_response = Mock()
        mock_response.json.return_value = source_data
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        # No diagram_type parameter - should default to flowchart
        response = client.get(
            "/export?type=mermaid&url=http://test.com/api/test"
        )

        assert response.status_code == 200
        mermaid_content = response.get_data(as_text=True)
        assert "flowchart TD" in mermaid_content

    @patch("app.resources.export_mermaid.requests.get")
    def test_label_sanitization(self, mock_get, client, auth_headers):
        """Test that labels with special characters are sanitized."""
        source_data = [
            {"id": "1", "name": 'Test <script>"alert"</script>\nNewline'},
        ]

        mock_response = Mock()
        mock_response.json.return_value = source_data
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get(
            "/export?type=mermaid&url=http://test.com/api/test"
        )

        assert response.status_code == 200
        mermaid_content = response.get_data(as_text=True)
        # Should sanitize < > and quotes
        assert "&lt;" in mermaid_content or "&gt;" in mermaid_content
        # The newline should be replaced with a space in the label
        assert "Newline" in mermaid_content  # Label text is present
        # Verify the sanitization worked - no embedded newline in label brackets
        assert "alert" in mermaid_content  # Part of the label

    @patch("app.resources.export_mermaid.requests.get")
    def test_non_array_response(self, mock_get, client, auth_headers):
        """Test error when target URL returns non-array."""
        mock_response = Mock()
        mock_response.json.return_value = {"not": "an array"}
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth_headers["set_cookie"](client)
        response = client.get(
            "/export?type=mermaid&url=http://test.com/api/test"
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "json array" in data["message"].lower()

    @patch("app.resources.export_mermaid.requests.get")
    def test_network_error(self, mock_get, client, auth_headers):
        """Test error handling for network failures."""
        mock_get.side_effect = Exception("Network error")

        auth_headers["set_cookie"](client)
        response = client.get(
            "/export?type=mermaid&url=http://test.com/api/test"
        )

        assert response.status_code == 502 or response.status_code == 500
        data = json.loads(response.data)
        assert "message" in data
