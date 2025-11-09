"""Utility modules for the Basic I/O Service."""

from app.utils.auth import (
    camel_to_snake,
    check_access,
    check_access_required,
    extract_jwt_data,
    require_jwt_auth,
)
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

__all__ = [
    # Auth utilities
    "camel_to_snake",
    "check_access",
    "check_access_required",
    "extract_jwt_data",
    "require_jwt_auth",
    # Reference resolution utilities
    "build_references_metadata",
    "build_tree",
    "detect_cycles",
    "detect_foreign_keys",
    "detect_tree_structure",
    "enrich_record",
    "flatten_tree",
    "is_uuid",
    "resolve_reference",
    "topological_sort",
]
