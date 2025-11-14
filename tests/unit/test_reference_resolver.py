"""Unit tests for reference_resolver utilities."""

import pytest
from unittest.mock import Mock, patch
from app.utils.reference_resolver import (
    build_references_metadata,
    build_tree,
    detect_cycles,
    detect_foreign_keys,
    detect_tree_structure,
    enrich_record,
    flatten_tree,
    is_uuid,
    resolve_reference,
    topological_sort,
)


class TestIsUuid:
    """Tests for is_uuid function."""

    def test_valid_uuid(self):
        """Test valid UUID strings."""
        assert is_uuid("a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d") is True
        assert is_uuid("A1B2C3D4-E5F6-4A5B-8C9D-0E1F2A3B4C5D") is True

    def test_invalid_uuid(self):
        """Test invalid UUID strings."""
        assert is_uuid("not-a-uuid") is False
        assert is_uuid("12345") is False
        assert is_uuid("") is False

    def test_non_string_values(self):
        """Test non-string values."""
        assert is_uuid(None) is False
        assert is_uuid(123) is False
        assert is_uuid([]) is False


class TestGetResourceTypeFromUrl:
    """Tests for get_resource_type_from_url function."""

    def test_extract_resource_type(self):
        """Test extracting resource type from URL."""
        from app.utils.reference_resolver import get_resource_type_from_url

        assert (
            get_resource_type_from_url("http://localhost:5001/api/users")
            == "users"
        )
        assert (
            get_resource_type_from_url("http://localhost:5001/api/projects/")
            == "projects"
        )

    def test_empty_url(self):
        """Test with empty URL."""
        from app.utils.reference_resolver import get_resource_type_from_url

        assert get_resource_type_from_url("") == ""


class TestDetectForeignKeys:
    """Tests for detect_foreign_keys function."""

    def test_detect_id_suffix(self):
        """Test detection of fields ending with _id."""
        record = {
            "name": "Test",
            "project_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
        }
        fks = detect_foreign_keys(record)
        assert "project_id" in fks

    def test_detect_uuid_suffix(self):
        """Test detection of fields ending with _uuid."""
        record = {
            "name": "Test",
            "project_uuid": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
        }
        fks = detect_foreign_keys(record)
        assert "project_uuid" in fks

    def test_ignore_non_uuid_values(self):
        """Test that non-UUID values are ignored."""
        record = {"name": "Test", "project_id": "not-a-uuid"}
        fks = detect_foreign_keys(record)
        assert "project_id" not in fks

    def test_multiple_foreign_keys(self):
        """Test detection of multiple foreign keys."""
        record = {
            "project_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
            "user_id": "b2c3d4e5-f6a7-4b5c-9d0e-1f2a3b4c5d6e",
            "name": "Task",
        }
        fks = detect_foreign_keys(record)
        assert len(fks) == 2
        assert "project_id" in fks
        assert "user_id" in fks


class TestDetectTreeStructure:
    """Tests for detect_tree_structure function."""

    def test_detect_parent_id(self):
        """Test detection of parent_id field."""
        data = [{"id": "1", "parent_id": None}, {"id": "2", "parent_id": "1"}]
        parent_field = detect_tree_structure(data)
        assert parent_field == "parent_id"

    def test_detect_parent_uuid(self):
        """Test detection of parent_uuid field."""
        data = [
            {"id": "1", "parent_uuid": None},
            {"id": "2", "parent_uuid": "1"},
        ]
        parent_field = detect_tree_structure(data)
        assert parent_field == "parent_uuid"

    def test_no_parent_field(self):
        """Test when no parent field exists."""
        data = [{"id": "1", "name": "Test"}]
        parent_field = detect_tree_structure(data)
        assert parent_field is None

    def test_empty_data(self):
        """Test with empty data."""
        parent_field = detect_tree_structure([])
        assert parent_field is None


class TestBuildReferencesMetadata:
    """Tests for build_references_metadata function."""

    def test_build_project_reference(self):
        """Test building reference for project_id."""
        record = {
            "project_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
            "name": "Task 1",
        }
        refs = build_references_metadata(record, ["project_id"])

        assert "project_id" in refs
        assert refs["project_id"]["resource_type"] == "projects"
        assert (
            refs["project_id"]["original_id"]
            == "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d"
        )
        assert refs["project_id"]["lookup_field"] == "name"

    def test_build_user_reference(self):
        """Test building reference for user field (assigned_to)."""
        record = {
            "assigned_to": "b2c3d4e5-f6a7-4b5c-9d0e-1f2a3b4c5d6e",
            "name": "Task 1",
        }
        refs = build_references_metadata(record, ["assigned_to"])

        assert "assigned_to" in refs
        assert refs["assigned_to"]["resource_type"] == "users"
        assert refs["assigned_to"]["lookup_field"] == "email"

    def test_custom_lookup_config(self):
        """Test custom lookup configuration."""
        record = {
            "project_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
        }
        lookup_config = {"projects": ["code", "name"]}
        refs = build_references_metadata(record, ["project_id"], lookup_config)

        assert refs["project_id"]["lookup_field"] == "code"

    def test_skip_null_values(self):
        """Test that null/empty FK values are skipped."""
        record = {"project_id": None, "name": "Task"}
        refs = build_references_metadata(record, ["project_id"])
        assert "project_id" not in refs


class TestEnrichRecord:
    """Tests for enrich_record function."""

    def test_enrich_with_fks(self):
        """Test enriching record with foreign keys."""
        record = {
            "id": "task-1",
            "project_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
            "name": "Task 1",
        }
        enriched = enrich_record(record)

        assert "_references" in enriched
        assert "project_id" in enriched["_references"]
        assert enriched["name"] == "Task 1"  # Original data preserved

    def test_enrich_without_fks(self):
        """Test enriching record without foreign keys."""
        record = {"id": "1", "name": "Test"}
        enriched = enrich_record(record)
        assert enriched == record  # No changes

    def test_exclude_parent_field(self):
        """Test excluding parent field from enrichment."""
        record = {
            "id": "cat-1",
            "parent_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
            "project_id": "b2c3d4e5-f6a7-4b5c-9d0e-1f2a3b4c5d6e",
        }
        enriched = enrich_record(record, parent_field="parent_id")

        assert "_references" in enriched
        assert "parent_id" not in enriched["_references"]
        assert "project_id" in enriched["_references"]


class TestResolveReference:
    """Tests for resolve_reference function."""

    @patch("app.utils.reference_resolver.requests.get")
    def test_resolve_single_match(self, mock_get):
        """Test resolving with exactly one match."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {"id": "new-uuid-1", "name": "Project A"}
        ]
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        ref_meta = {
            "resource_type": "projects",
            "lookup_field": "name",
            "lookup_value": "Project A",
        }

        status, resolved_id, candidates, error = resolve_reference(
            ref_meta, "http://localhost:5001/api/tasks"
        )

        assert status == "resolved"
        assert resolved_id == "new-uuid-1"
        assert len(candidates) == 1
        assert candidates[0]["id"] == "new-uuid-1"
        assert error is None

    @patch("app.utils.reference_resolver.requests.get")
    def test_resolve_no_matches(self, mock_get):
        """Test resolving with no matches."""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        ref_meta = {
            "resource_type": "projects",
            "lookup_field": "name",
            "lookup_value": "Non-existent",
        }

        status, resolved_id, candidates, error = resolve_reference(
            ref_meta, "http://localhost:5001/api/tasks"
        )

        assert status == "missing"
        assert resolved_id is None
        assert candidates == []
        assert "No projects found" in error

    @patch("app.utils.reference_resolver.requests.get")
    def test_resolve_ambiguous(self, mock_get):
        """Test resolving with multiple matches."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {"id": "uuid-1", "name": "Project A", "code": "PROJ1"},
            {"id": "uuid-2", "name": "Project A", "code": "PROJ2"},
        ]
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        ref_meta = {
            "resource_type": "projects",
            "lookup_field": "name",
            "lookup_value": "Project A",
        }

        status, resolved_id, candidates, error = resolve_reference(
            ref_meta, "http://localhost:5001/api/tasks"
        )

        assert status == "ambiguous"
        assert resolved_id is None
        assert len(candidates) == 2
        assert "Multiple projects found" in error

    @patch("app.utils.reference_resolver.requests.get")
    def test_resolve_error(self, mock_get):
        """Test resolving with request error."""
        from requests.exceptions import RequestException

        mock_get.side_effect = RequestException("Connection error")

        ref_meta = {
            "resource_type": "projects",
            "lookup_field": "name",
            "lookup_value": "Project A",
        }

        status, resolved_id, candidates, error = resolve_reference(
            ref_meta, "http://localhost:5001/api/tasks"
        )

        assert status == "error"
        assert resolved_id is None
        assert candidates == []
        assert "Connection error" in error

    def test_missing_metadata_fields(self):
        """Test with incomplete reference metadata."""
        ref_meta = {"resource_type": "projects"}  # Missing lookup fields

        status, _, _, error = resolve_reference(
            ref_meta, "http://localhost:5001/api/tasks"
        )

        assert status == "error"
        assert "Missing reference metadata" in error


class TestTopologicalSort:
    """Tests for topological_sort function."""

    def test_sort_simple_tree(self):
        """Test sorting a simple tree structure."""
        records = [
            {"_original_id": "child", "parent_id": "parent", "name": "Child"},
            {"_original_id": "parent", "parent_id": None, "name": "Parent"},
        ]
        sorted_records = topological_sort(records, "parent_id")

        assert len(sorted_records) == 2
        assert sorted_records[0]["name"] == "Parent"
        assert sorted_records[1]["name"] == "Child"

    def test_sort_complex_tree(self):
        """Test sorting a multi-level tree."""
        records = [
            {
                "_original_id": "grandchild",
                "parent_id": "child",
                "name": "Grandchild",
            },
            {
                "_original_id": "child",
                "parent_id": "parent",
                "name": "Child",
            },
            {
                "_original_id": "parent",
                "parent_id": None,
                "name": "Parent",
            },
        ]
        sorted_records = topological_sort(records, "parent_id")

        names = [r["name"] for r in sorted_records]
        assert names == ["Parent", "Child", "Grandchild"]

    def test_sort_multiple_roots(self):
        """Test sorting with multiple root nodes."""
        records = [
            {"_original_id": "root1", "parent_id": None, "name": "Root 1"},
            {
                "_original_id": "child1",
                "parent_id": "root1",
                "name": "Child 1",
            },
            {"_original_id": "root2", "parent_id": None, "name": "Root 2"},
        ]
        sorted_records = topological_sort(records, "parent_id")

        # Roots should come before children
        root_indices = [
            i for i, r in enumerate(sorted_records) if r["parent_id"] is None
        ]
        child_index = [
            i for i, r in enumerate(sorted_records) if r["name"] == "Child 1"
        ][0]

        assert all(root_idx < child_index for root_idx in root_indices)

    def test_circular_reference_raises_error(self):
        """Test that circular references raise ValueError."""
        records = [
            {"_original_id": "a", "parent_id": "b", "name": "A"},
            {"_original_id": "b", "parent_id": "a", "name": "B"},
        ]

        with pytest.raises(ValueError, match="Circular reference"):
            topological_sort(records, "parent_id")

    def test_record_without_id(self):
        """Test handling records without _original_id or id."""
        records = [
            {"_original_id": "parent", "parent_id": None, "name": "Parent"},
            {
                "_original_id": "child",
                "parent_id": "parent",
                "name": "Child",
            },
        ]
        sorted_records = topological_sort(records, "parent_id")
        # All records with IDs should be sorted
        assert len(sorted_records) == 2
        assert sorted_records[0]["name"] == "Parent"


class TestDetectCycles:
    """Tests for detect_cycles function."""

    def test_no_cycles(self):
        """Test tree without cycles."""
        records = [
            {"_original_id": "parent", "parent_id": None},
            {"_original_id": "child", "parent_id": "parent"},
        ]
        cycle = detect_cycles(records, "parent_id")
        assert cycle is None

    def test_simple_cycle(self):
        """Test detection of simple cycle."""
        records = [
            {"_original_id": "a", "parent_id": "b"},
            {"_original_id": "b", "parent_id": "a"},
        ]
        cycle = detect_cycles(records, "parent_id")
        assert cycle is not None
        assert len(cycle) >= 2

    def test_three_node_cycle(self):
        """Test detection of three-node cycle."""
        records = [
            {"_original_id": "a", "parent_id": "b"},
            {"_original_id": "b", "parent_id": "c"},
            {"_original_id": "c", "parent_id": "a"},
        ]
        cycle = detect_cycles(records, "parent_id")
        assert cycle is not None
        assert len(cycle) >= 3

    def test_already_visited_path(self):
        """Test that already-visited nodes are skipped."""
        records = [
            {"_original_id": "root", "parent_id": None},
            {"_original_id": "child1", "parent_id": "root"},
            {"_original_id": "child2", "parent_id": "root"},
        ]
        # Should not detect cycles in a valid tree
        cycle = detect_cycles(records, "parent_id")
        assert cycle is None


class TestBuildTree:
    """Tests for build_tree function."""

    def test_build_simple_tree(self):
        """Test building a simple tree."""
        flat = [
            {"_original_id": "parent", "parent_id": None, "name": "Parent"},
            {
                "_original_id": "child",
                "parent_id": "parent",
                "name": "Child",
            },
        ]
        tree = build_tree(flat, "parent_id")

        assert len(tree) == 1  # One root
        assert tree[0]["name"] == "Parent"
        assert len(tree[0]["children"]) == 1
        assert tree[0]["children"][0]["name"] == "Child"

    def test_build_multi_level_tree(self):
        """Test building multi-level tree."""
        flat = [
            {"_original_id": "root", "parent_id": None, "name": "Root"},
            {"_original_id": "child", "parent_id": "root", "name": "Child"},
            {
                "_original_id": "grandchild",
                "parent_id": "child",
                "name": "Grandchild",
            },
        ]
        tree = build_tree(flat, "parent_id")

        assert len(tree) == 1
        assert tree[0]["name"] == "Root"
        assert tree[0]["children"][0]["name"] == "Child"
        assert tree[0]["children"][0]["children"][0]["name"] == "Grandchild"

    def test_build_multiple_roots(self):
        """Test building tree with multiple roots."""
        flat = [
            {"_original_id": "root1", "parent_id": None, "name": "Root 1"},
            {"_original_id": "root2", "parent_id": None, "name": "Root 2"},
        ]
        tree = build_tree(flat, "parent_id")

        assert len(tree) == 2


class TestFlattenTree:
    """Tests for flatten_tree function."""

    def test_flatten_simple_tree(self):
        """Test flattening a simple tree."""
        tree = [
            {
                "_original_id": "parent",
                "name": "Parent",
                "children": [
                    {"_original_id": "child", "name": "Child", "children": []}
                ],
            }
        ]
        flat = flatten_tree(tree, "parent_id")

        assert len(flat) == 2
        parent_rec = [r for r in flat if r["name"] == "Parent"][0]
        child_rec = [r for r in flat if r["name"] == "Child"][0]

        assert parent_rec["parent_id"] is None
        assert child_rec["parent_id"] == "parent"

    def test_flatten_multi_level(self):
        """Test flattening multi-level tree."""
        tree = [
            {
                "_original_id": "root",
                "name": "Root",
                "children": [
                    {
                        "_original_id": "child",
                        "name": "Child",
                        "children": [
                            {
                                "_original_id": "grandchild",
                                "name": "Grandchild",
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ]
        flat = flatten_tree(tree, "parent_id")

        assert len(flat) == 3
        grandchild = [r for r in flat if r["name"] == "Grandchild"][0]
        assert grandchild["parent_id"] == "child"

    def test_round_trip(self):
        """Test that build_tree and flatten_tree are inverses."""
        original = [
            {"_original_id": "root", "parent_id": None, "name": "Root"},
            {"_original_id": "child", "parent_id": "root", "name": "Child"},
        ]

        tree = build_tree(original, "parent_id")
        flat = flatten_tree(tree, "parent_id")

        # Should have same number of records
        assert len(flat) == len(original)

        # Should have same parent relationships
        for orig_rec in original:
            orig_id = orig_rec["_original_id"]
            orig_parent = orig_rec.get("parent_id")

            flat_rec = [r for r in flat if r["_original_id"] == orig_id][0]
            assert flat_rec["parent_id"] == orig_parent
