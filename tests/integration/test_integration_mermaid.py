"""Integration tests for Mermaid import/export workflow."""

# pylint: disable=redefined-outer-name,unused-argument

import io
import json
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def mock_mermaid_service():
    """Provide a simple mock service for Mermaid tests."""

    class Service:
        def __init__(self):
            self.storage = {}
            self.id_counter = 1

        def create_record(self, data):
            record_id = f"mmd-id-{self.id_counter}"
            self.id_counter += 1
            record = {"id": record_id, **data}
            self.storage[record_id] = record
            return record

    return Service()


class TestMermaidIntegrationWorkflow:
    """Integration tests for Mermaid export→import workflows."""

    @patch("app.resources.export_mermaid.requests.get")
    @patch("app.resources.import_mermaid.requests.post")
    def test_simple_flowchart_roundtrip(
        self,
        mock_import_post,
        mock_export_get,
        client,
        auth_headers,
        mock_mermaid_service,
    ):
        """Test complete Mermaid flowchart workflow: export → import."""
        # Source data
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

        # Mock export GET
        mock_export_response = Mock()
        mock_export_response.json.return_value = source_data
        mock_export_response.status_code = 200
        mock_export_get.return_value = mock_export_response

        # Step 1: EXPORT to Mermaid flowchart
        auth_headers["set_cookie"](client)
        export_response = client.get(
            "/export?type=mermaid&diagram_type=flowchart"
            "&url=http://source:5000/api/categories"
        )

        assert export_response.status_code == 200
        assert "text/plain" in export_response.content_type

        # Verify Mermaid content structure
        mermaid_content = export_response.get_data(as_text=True)
        assert "flowchart TD" in mermaid_content
        assert "Backend" in mermaid_content
        assert "_original_id: cat-1" in mermaid_content
        assert "node_cat_1 --> node_cat_2" in mermaid_content
        assert "node_cat_1 --> node_cat_3" in mermaid_content

        # Step 2: IMPORT Mermaid to target service
        # Mock import POST with ID mapping
        id_mapping = {}

        def mock_create(url, json=None, cookies=None, timeout=None):
            # Handle parent_id mapping
            if json.get("parent_id") and json["parent_id"] in id_mapping:
                json["parent_id"] = id_mapping[json["parent_id"]]

            created = mock_mermaid_service.create_record(json)

            # Track original ID for mapping
            if "Backend" in json.get("name", ""):
                id_mapping["cat-1"] = created["id"]
            elif "API" in json.get("name", ""):
                id_mapping["cat-2"] = created["id"]
            elif "Database" in json.get("name", ""):
                id_mapping["cat-3"] = created["id"]

            response = Mock()
            response.json.return_value = created
            response.status_code = 201
            return response

        mock_import_post.side_effect = mock_create

        # Import Mermaid
        mermaid_bytes = export_response.get_data()
        import_response = client.post(
            "/import?type=mermaid&url=http://target:5000/api/categories",
            data={
                "file": (io.BytesIO(mermaid_bytes), "diagram.mmd"),
            },
        )

        assert import_response.status_code == 200
        import_data = json.loads(import_response.data)

        # Verify import success
        assert import_data["total_records"] == 3
        assert import_data["successful_imports"] == 3
        assert import_data["failed_imports"] == 0

        # Verify ID mapping created
        assert "cat-1" in import_data["id_mapping"]
        assert "cat-2" in import_data["id_mapping"]
        assert "cat-3" in import_data["id_mapping"]

    @patch("app.resources.export_mermaid.requests.get")
    @patch("app.resources.import_mermaid.requests.post")
    def test_mindmap_roundtrip(
        self,
        mock_import_post,
        mock_export_get,
        client,
        auth_headers,
        mock_mermaid_service,
    ):
        """Test Mermaid mindmap export→import workflow."""
        # Source tree data
        source_tree = [
            {"id": "root-1", "name": "Backend", "parent_id": None},
            {"id": "child-1", "name": "API", "parent_id": "root-1"},
            {"id": "grandchild-1", "name": "REST", "parent_id": "child-1"},
            {"id": "child-2", "name": "Database", "parent_id": "root-1"},
        ]

        # Mock export GET
        mock_export_response = Mock()
        mock_export_response.json.return_value = source_tree
        mock_export_response.status_code = 200
        mock_export_get.return_value = mock_export_response

        # Export to Mermaid mindmap
        auth_headers["set_cookie"](client)
        export_response = client.get(
            "/export?type=mermaid&diagram_type=mindmap"
            "&url=http://source:5000/api/categories"
        )

        assert export_response.status_code == 200

        # Verify mindmap structure
        mermaid_content = export_response.get_data(as_text=True)
        assert "mindmap" in mermaid_content
        assert "root((Backend))" in mermaid_content
        assert "API" in mermaid_content
        assert "REST" in mermaid_content
        assert "Database" in mermaid_content

        # Mock import with ID mapping
        id_mapping = {}
        call_order = []

        def mock_create_with_mapping(
            url, json=None, cookies=None, timeout=None
        ):
            call_order.append(json["name"])

            # Handle parent_id mapping
            if json.get("parent_id") and json["parent_id"] in id_mapping:
                json["parent_id"] = id_mapping[json["parent_id"]]

            created = mock_mermaid_service.create_record(json)

            # Build ID mapping based on generated node IDs
            # Mindmap creates sequential node-X IDs
            node_num = len(id_mapping) + 1
            id_mapping[f"node-{node_num}"] = created["id"]

            response = Mock()
            response.json.return_value = created
            response.status_code = 201
            return response

        mock_import_post.side_effect = mock_create_with_mapping

        # Import Mermaid
        mermaid_bytes = export_response.get_data()
        import_response = client.post(
            "/import?type=mermaid&url=http://target:5000/api/categories",
            data={
                "file": (io.BytesIO(mermaid_bytes), "mindmap.mmd"),
            },
        )

        assert import_response.status_code == 200
        import_data = json.loads(import_response.data)

        # All records should be imported
        assert import_data["successful_imports"] >= 4
        assert import_data["failed_imports"] == 0

        # Verify topological order: parents before children
        backend_idx = call_order.index("Backend")
        api_idx = call_order.index("API")
        rest_idx = call_order.index("REST")
        database_idx = call_order.index("Database")

        assert (
            backend_idx < api_idx
        ), "Backend should be created before API"
        assert api_idx < rest_idx, "API should be created before REST"
        assert (
            backend_idx < database_idx
        ), "Backend should be created before Database"

    @patch("app.resources.export_mermaid.requests.get")
    @patch("app.resources.import_mermaid.requests.post")
    def test_graph_diagram_roundtrip(
        self,
        mock_import_post,
        mock_export_get,
        client,
        auth_headers,
        mock_mermaid_service,
    ):
        """Test Mermaid graph export→import workflow."""
        # Source data
        source_data = [
            {"id": "node-1", "name": "Node A", "parent_id": None},
            {"id": "node-2", "name": "Node B", "parent_id": "node-1"},
            {"id": "node-3", "name": "Node C", "parent_id": "node-1"},
        ]

        # Mock export GET
        mock_export_response = Mock()
        mock_export_response.json.return_value = source_data
        mock_export_response.status_code = 200
        mock_export_get.return_value = mock_export_response

        # Export to Mermaid graph
        auth_headers["set_cookie"](client)
        export_response = client.get(
            "/export?type=mermaid&diagram_type=graph"
            "&url=http://source:5000/api/nodes"
        )

        assert export_response.status_code == 200

        # Verify graph structure
        mermaid_content = export_response.get_data(as_text=True)
        assert "graph TD" in mermaid_content
        assert "Node A" in mermaid_content
        assert "Node B" in mermaid_content
        assert "Node C" in mermaid_content
        assert "---" in mermaid_content  # Graph uses --- for edges

        # Mock import
        id_mapping = {}

        def mock_create(url, json=None, cookies=None, timeout=None):
            # Handle parent_id mapping
            if json.get("parent_id") and json["parent_id"] in id_mapping:
                json["parent_id"] = id_mapping[json["parent_id"]]

            created = mock_mermaid_service.create_record(json)

            # Track original IDs
            if "Node A" in json.get("name", ""):
                id_mapping["node-1"] = created["id"]
            elif "Node B" in json.get("name", ""):
                id_mapping["node-2"] = created["id"]
            elif "Node C" in json.get("name", ""):
                id_mapping["node-3"] = created["id"]

            response = Mock()
            response.json.return_value = created
            response.status_code = 201
            return response

        mock_import_post.side_effect = mock_create

        # Import Mermaid
        mermaid_bytes = export_response.get_data()
        import_response = client.post(
            "/import?type=mermaid&url=http://target:5000/api/nodes",
            data={
                "file": (io.BytesIO(mermaid_bytes), "graph.mmd"),
            },
        )

        assert import_response.status_code == 200
        import_data = json.loads(import_response.data)

        # Verify import success
        assert import_data["total_records"] == 3
        assert import_data["successful_imports"] == 3
        assert import_data["failed_imports"] == 0

        # Verify ID mapping exists (graph parser extracts numeric IDs)
        assert len(import_data["id_mapping"]) == 3
        # IDs will be sequential numbers from the parsed graph
        assert any(
            k in import_data["id_mapping"]
            for k in ["1", "2", "3", "node-1", "node-2", "node-3"]
        )
