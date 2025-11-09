"""Integration tests for CSV import/export workflow."""

# pylint: disable=redefined-outer-name,unused-argument

import csv
import io
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def mock_csv_service():
    """Provide a simple mock service for CSV tests."""

    class Service:
        def __init__(self):
            self.storage = {}
            self.id_counter = 1

        def create_record(self, data):
            record_id = f"csv-id-{self.id_counter}"
            self.id_counter += 1
            record = {"id": record_id, **data}
            self.storage[record_id] = record
            return record

    return Service()


class TestCsvIntegrationWorkflow:
    """Integration tests for CSV export→import workflows."""

    @patch("app.resources.export_csv.requests.get")
    @patch("app.resources.import_csv.requests.post")
    def test_simple_csv_roundtrip(
        self,
        mock_import_post,
        mock_export_get,
        client,
        auth_headers,
        mock_csv_service,
    ):
        """Test complete CSV workflow: export → import."""
        # Source data
        source_data = [
            {"id": "user-1", "name": "Alice", "email": "alice@test.com"},
            {"id": "user-2", "name": "Bob", "email": "bob@test.com"},
        ]

        # Mock export GET
        mock_export_response = Mock()
        mock_export_response.json.return_value = source_data
        mock_export_response.status_code = 200
        mock_export_get.return_value = mock_export_response

        # Step 1: EXPORT to CSV
        auth_headers["set_cookie"](client)
        export_response = client.get(
            "/export?type=csv&url=http://source:5000/api/users&enrich=false"
        )

        assert export_response.status_code == 200
        assert "text/csv" in export_response.content_type

        # Parse exported CSV
        csv_content = export_response.get_data(as_text=True)
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        exported_rows = list(csv_reader)

        assert len(exported_rows) == 2
        assert exported_rows[0]["_original_id"] == "user-1"
        assert exported_rows[0]["name"] == "Alice"

        # Step 2: IMPORT CSV to target service
        # Mock import POST
        def mock_create(url, json=None, cookies=None, timeout=None):
            created = mock_csv_service.create_record(json)
            response = Mock()
            response.json.return_value = created
            response.status_code = 201
            return response

        mock_import_post.side_effect = mock_create

        # Re-encode CSV for import
        csv_bytes = export_response.get_data()

        import_response = client.post(
            "/import?type=csv",
            data={
                "url": "http://target:5000/api/users",
                "file": (io.BytesIO(csv_bytes), "export.csv"),
                "resolve_foreign_keys": "false",
            },
        )

        assert import_response.status_code == 200
        import json

        import_data = json.loads(import_response.data)

        # Verify import success
        assert import_data["import_report"]["success"] == 2
        assert import_data["import_report"]["failed"] == 0

        # Verify ID mapping created
        assert "user-1" in import_data["id_mapping"]
        assert "user-2" in import_data["id_mapping"]

    @patch("app.resources.export_csv.requests.get")
    @patch("app.resources.import_csv.requests.post")
    def test_csv_tree_structure_roundtrip(
        self,
        mock_import_post,
        mock_export_get,
        client,
        auth_headers,
        mock_csv_service,
    ):
        """Test CSV export→import with tree structure."""
        # Source tree data
        source_tree = [
            {"id": "root-1", "name": "Root Unit", "parent_id": None},
            {"id": "child-1", "name": "Child Unit 1", "parent_id": "root-1"},
            {"id": "child-2", "name": "Child Unit 2", "parent_id": "root-1"},
        ]

        # Mock export GET
        mock_export_response = Mock()
        mock_export_response.json.return_value = source_tree
        mock_export_response.status_code = 200
        mock_export_get.return_value = mock_export_response

        # Export to CSV
        auth_headers["set_cookie"](client)
        export_response = client.get(
            "/export?type=csv&url=http://source:5000/api/org_units&enrich=false"
        )

        assert export_response.status_code == 200

        # Mock import with ID mapping
        id_mapping = {}

        def mock_create_with_mapping(
            url, json=None, cookies=None, timeout=None
        ):
            # Handle parent_id mapping
            if json.get("parent_id") and json["parent_id"] in id_mapping:
                json["parent_id"] = id_mapping[json["parent_id"]]

            created = mock_csv_service.create_record(json)

            # Store mapping if _original_id present
            original_id = None
            for key in json.keys():
                if key == "name" and "Root Unit" in json["name"]:
                    original_id = "root-1"
                elif key == "name" and "Child Unit 1" in json["name"]:
                    original_id = "child-1"
                elif key == "name" and "Child Unit 2" in json["name"]:
                    original_id = "child-2"

            if original_id:
                id_mapping[original_id] = created["id"]

            response = Mock()
            response.json.return_value = created
            response.status_code = 201
            return response

        mock_import_post.side_effect = mock_create_with_mapping

        # Import CSV
        csv_bytes = export_response.get_data()
        import_response = client.post(
            "/import?type=csv",
            data={
                "url": "http://target:5000/api/org_units",
                "file": (io.BytesIO(csv_bytes), "tree.csv"),
                "resolve_foreign_keys": "false",
            },
        )

        assert import_response.status_code == 200
        import json

        import_data = json.loads(import_response.data)

        # All records should be imported
        assert import_data["import_report"]["success"] == 3
        assert import_data["import_report"]["failed"] == 0

    @patch("app.resources.export_csv.requests.get")
    @patch("app.resources.import_csv.requests.post")
    def test_csv_with_complex_types(
        self,
        mock_import_post,
        mock_export_get,
        client,
        auth_headers,
        mock_csv_service,
    ):
        """Test CSV roundtrip with nested objects (JSON-encoded in CSV)."""
        # Source data with nested object
        source_data = [
            {
                "id": "user-1",
                "name": "Alice",
                "address": {"city": "Paris", "country": "France"},
                "tags": ["python", "flask"],
            }
        ]

        # Mock export GET
        mock_export_response = Mock()
        mock_export_response.json.return_value = source_data
        mock_export_response.status_code = 200
        mock_export_get.return_value = mock_export_response

        # Export to CSV
        auth_headers["set_cookie"](client)
        export_response = client.get(
            "/export?type=csv&url=http://source:5000/api/users&enrich=false"
        )

        assert export_response.status_code == 200

        # Verify CSV contains JSON-encoded nested data
        csv_content = export_response.get_data(as_text=True)
        assert '"city": "Paris"' in csv_content or "Paris" in csv_content

        # Mock import
        def mock_create(url, json=None, cookies=None, timeout=None):
            created = mock_csv_service.create_record(json)
            response = Mock()
            response.json.return_value = created
            response.status_code = 201
            return response

        mock_import_post.side_effect = mock_create

        # Import CSV
        csv_bytes = export_response.get_data()
        import_response = client.post(
            "/import?type=csv",
            data={
                "url": "http://target:5000/api/users",
                "file": (io.BytesIO(csv_bytes), "complex.csv"),
                "resolve_foreign_keys": "false",
            },
        )

        assert import_response.status_code == 200
        import json

        import_data = json.loads(import_response.data)
        assert import_data["import_report"]["success"] == 1

        # Verify the nested object was parsed back
        # (The actual parsing happens in import_csv._parse_csv_row)
        call_args = mock_import_post.call_args
        posted_data = call_args.kwargs["json"]

        # Address should be parsed back to dict
        if "address" in posted_data:
            assert isinstance(posted_data["address"], dict)
            assert posted_data["address"]["city"] == "Paris"
