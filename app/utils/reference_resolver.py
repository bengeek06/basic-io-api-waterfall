"""Reference resolution utilities for import/export operations.

This module provides utilities for:
- Detecting foreign key fields in data records
- Enriching records with reference metadata for intelligent imports
- Resolving foreign key references using lookup fields
- Detecting and handling tree structures (parent_id fields)
- Topological sorting for dependency-ordered imports
- Cycle detection in hierarchical data
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict, deque

import requests

from app.logger import logger


# UUID pattern for detecting foreign key fields
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Common plural forms for resource types
PLURALIZATION_MAP = {
    "company": "companies",
    "category": "categories",
    "entity": "entities",
    "activity": "activities",
}


def pluralize(word: str) -> str:
    """Convert a singular word to plural form.

    Args:
        word: Singular form of the word

    Returns:
        Plural form of the word
    """
    # Check custom mappings first
    if word in PLURALIZATION_MAP:
        return PLURALIZATION_MAP[word]

    # Apply simple English pluralization rules
    if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    return word + "s"


# Default lookup fields for common resource types
DEFAULT_LOOKUP_CONFIG = {
    "users": ["email"],
    "companies": ["name"],
    "positions": ["title"],
    "organization_units": ["name"],
    "customers": ["name"],
    "subcontractors": ["name"],
    "projects": ["name"],
    "tasks": ["name"],
    "roles": ["name"],
    "categories": ["name"],
}


def is_uuid(value: Any) -> bool:
    """Check if a value is a valid UUID string.

    Args:
        value: The value to check

    Returns:
        True if the value is a valid UUID string, False otherwise
    """
    if not isinstance(value, str):
        return False
    return bool(UUID_PATTERN.match(value))


def detect_foreign_keys(record: Dict[str, Any]) -> List[str]:
    """Detect foreign key fields in a record.

    Foreign keys are identified as fields ending with '_id' or '_uuid'
    that contain valid UUID values. Excludes technical/metadata fields.

    Args:
        record: The data record to analyze

    Returns:
        List of field names that are foreign keys
    """
    # Technical fields that look like FKs but aren't real foreign keys
    excluded_fields = {"_original_id", "id"}

    fk_fields = []
    for field_name, field_value in record.items():
        if field_name in excluded_fields:
            continue
        if field_name.endswith(("_id", "_uuid")) and is_uuid(field_value):
            fk_fields.append(field_name)
    return fk_fields


def detect_tree_structure(data: List[Dict[str, Any]]) -> Optional[str]:
    """Detect if data has a tree structure (parent_id field).

    Args:
        data: List of records to analyze

    Returns:
        The name of the parent field if found, None otherwise
    """
    if not data:
        return None

    # Check first record for parent_id or parent_uuid field
    first_record = data[0]
    for field_name in ["parent_id", "parent_uuid"]:
        if field_name in first_record:
            return field_name

    return None


def get_resource_type_from_url(url: str) -> str:
    """Extract resource type from a URL.

    Args:
        url: The URL to parse (e.g., 'http://localhost:5001/api/users')

    Returns:
        The resource type (e.g., 'users')
    """
    # Extract the last path segment
    parts = url.rstrip("/").split("/")
    return parts[-1] if parts else ""


def _fetch_lookup_value(
    base_url: str,
    resource_type: str,
    resource_id: str,
    lookup_field: str,
    cookies: Dict,
) -> Optional[Any]:
    """Fetch lookup value from a referenced resource.

    Args:
        base_url: Base URL of the service
        resource_type: Type of resource (e.g., 'users', 'projects')
        resource_id: ID of the referenced resource
        lookup_field: Field name to extract for lookup
        cookies: Authentication cookies

    Returns:
        The lookup value, or None if fetch fails
    """
    try:
        fetch_url = f"{base_url.rstrip('/')}/{resource_type}/{resource_id}"
        logger.debug(f"Fetching lookup value from {fetch_url}")
        response = requests.get(fetch_url, cookies=cookies, timeout=10)
        if response.status_code == 200:
            referenced_record = response.json()
            value = referenced_record.get(lookup_field)
            logger.debug(f"Fetched lookup value: {lookup_field}={value}")
            return value
        logger.warning(
            f"Failed to fetch {fetch_url}: status={response.status_code}"
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Defensive: catch all exceptions to avoid breaking export
        # Import will handle None gracefully
        logger.warning(f"Exception fetching lookup value: {exc}")
    return None


def build_references_metadata(
    record: Dict[str, Any],
    fk_fields: List[str],
    lookup_config: Optional[Dict[str, List[str]]] = None,
    base_url: Optional[str] = None,
    cookies: Optional[Dict] = None,
) -> Dict[str, Dict[str, Any]]:
    """Build reference metadata for foreign key fields.

    For each FK field, creates reference metadata and optionally fetches
    the lookup values from the referenced resources.

    Args:
        record: The data record containing foreign keys
        fk_fields: List of foreign key field names
        lookup_config: Custom lookup field configuration
        base_url: Base URL of the service (e.g., http://service:5000)
        cookies: Authentication cookies to use for fetching

    Returns:
        Dictionary mapping field names to reference metadata
    """
    if lookup_config is None:
        lookup_config = DEFAULT_LOOKUP_CONFIG

    references = {}

    for field_name in fk_fields:
        fk_value = record[field_name]
        if not fk_value:  # Skip null/empty FKs
            continue

        # Determine resource type from field name
        # e.g., 'project_id' -> 'projects', 'assigned_to' -> 'users'
        if field_name in ["assigned_to", "created_by", "updated_by"]:
            resource_type = "users"
        else:
            # Remove '_id' or '_uuid' suffix and pluralize
            base_name = field_name.replace("_id", "").replace("_uuid", "")
            resource_type = pluralize(base_name)

        # Get lookup fields for this resource type
        lookup_fields = lookup_config.get(
            resource_type, DEFAULT_LOOKUP_CONFIG.get(resource_type, ["name"])
        )

        lookup_field = lookup_fields[0]  # Use first lookup field
        lookup_value = None

        # Fetch the actual lookup value if base_url is provided
        if base_url and cookies is not None:
            lookup_value = _fetch_lookup_value(
                base_url, resource_type, fk_value, lookup_field, cookies
            )

        references[field_name] = {
            "resource_type": resource_type,
            "original_id": fk_value,
            "lookup_field": lookup_field,
            "lookup_value": lookup_value,
        }

    return references


def enrich_record(
    record: Dict[str, Any],
    lookup_config: Optional[Dict[str, List[str]]] = None,
    parent_field: Optional[str] = None,
    base_url: Optional[str] = None,
    cookies: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Enrich a record with reference metadata.

    Args:
        record: The data record to enrich
        lookup_config: Custom lookup field configuration
        parent_field: Name of parent field to exclude from enrichment
        base_url: Base URL of the service for fetching lookup values
        cookies: Authentication cookies for API calls

    Returns:
        Enriched record with _references metadata
    """
    # Detect foreign keys (excluding parent_field which is special)
    all_fk_fields = detect_foreign_keys(record)
    fk_fields = (
        [f for f in all_fk_fields if f != parent_field]
        if parent_field
        else all_fk_fields
    )

    if not fk_fields:
        return record

    # Build reference metadata (with optional lookup value fetching)
    references = build_references_metadata(
        record, fk_fields, lookup_config, base_url, cookies
    )

    enriched = record.copy()
    enriched["_references"] = references

    return enriched


def resolve_reference(
    reference_metadata: Dict[str, Any],
    target_url: str,
    cookies: Optional[Dict[str, str]] = None,
) -> Tuple[str, Optional[str], List[Dict[str, Any]], Optional[str]]:
    """Resolve a foreign key reference using lookup fields.

    Args:
        reference_metadata: Reference metadata with lookup information
        target_url: Base URL of the target service
        cookies: Authentication cookies to forward

    Returns:
        Tuple of (status, resolved_id, candidates, error_message)
        - status: 'resolved', 'ambiguous', 'missing', or 'error'
        - resolved_id: The new UUID if resolved, None otherwise
        - candidates: List of matching records for ambiguous case
        - error_message: Error description if applicable
    """
    resource_type = reference_metadata.get("resource_type")
    lookup_field = reference_metadata.get("lookup_field")
    lookup_value = reference_metadata.get("lookup_value")

    if not all([resource_type, lookup_field, lookup_value]):
        return (
            "error",
            None,
            [],
            "Missing reference metadata fields",
        )

    # Build query URL
    # Note: Some services may not support query parameters, so we fetch all records
    # and filter client-side for exact matches
    base_url = target_url.rstrip("/").rsplit("/", 1)[0]
    query_url = f"{base_url}/{resource_type}"

    try:
        response = requests.get(query_url, cookies=cookies, timeout=30)
        response.raise_for_status()
        all_records = response.json()

        # Filter for exact matches client-side
        # This handles services that don't support query parameter filtering
        matches = [
            record
            for record in all_records
            if record.get(lookup_field) == lookup_value
        ]

        if not matches:
            return (
                "missing",
                None,
                [],
                f"No {resource_type} found with {lookup_field}="
                f"'{lookup_value}'",
            )

        if len(matches) == 1:
            # Exactly one match - resolved!
            return "resolved", matches[0].get("id"), matches, None

        # Multiple matches - ambiguous
        return (
            "ambiguous",
            None,
            matches,
            f"Multiple {resource_type} found with {lookup_field}="
            f"'{lookup_value}'",
        )

    except requests.RequestException as exc:
        return "error", None, [], str(exc)


def topological_sort(
    records: List[Dict[str, Any]], parent_field: str
) -> List[Dict[str, Any]]:
    """Sort records in dependency order (parents before children).

    Uses Kahn's algorithm for topological sorting.

    Args:
        records: List of records with parent relationships
        parent_field: Name of the parent ID field

    Returns:
        List of records sorted in dependency order

    Raises:
        ValueError: If a cycle is detected
    """
    # Build adjacency list and in-degree map
    id_to_record = {}
    in_degree = defaultdict(int)
    children = defaultdict(list)

    for record in records:
        record_id = record.get("_original_id") or record.get("id")
        if not record_id:
            continue

        id_to_record[record_id] = record
        parent_id = record.get(parent_field)

        if parent_id:
            children[parent_id].append(record_id)
            in_degree[record_id] += 1
        else:
            # Root nodes have in-degree 0
            in_degree[record_id] = in_degree.get(record_id, 0)

    # Find all nodes with in-degree 0 (roots)
    queue = deque([rid for rid in id_to_record if in_degree[rid] == 0])
    sorted_records = []

    while queue:
        current_id = queue.popleft()
        sorted_records.append(id_to_record[current_id])

        # Decrease in-degree for children
        for child_id in children[current_id]:
            in_degree[child_id] -= 1
            if in_degree[child_id] == 0:
                queue.append(child_id)

    # Check if all nodes were processed
    if len(sorted_records) != len(records):
        raise ValueError("Circular reference detected in tree structure")

    return sorted_records


def detect_cycles(
    records: List[Dict[str, Any]], parent_field: str
) -> Optional[List[str]]:
    """Detect cycles in parent-child relationships.

    Args:
        records: List of records with parent relationships
        parent_field: Name of the parent ID field

    Returns:
        List of IDs forming a cycle if detected, None otherwise
    """
    # Build parent map
    parent_map = {}
    for record in records:
        record_id = record.get("_original_id") or record.get("id")
        parent_id = record.get(parent_field)
        if record_id and parent_id:
            parent_map[record_id] = parent_id

    # Check each node for cycles using tortoise and hare
    visited: Set[str] = set()

    for start_id in parent_map:
        if start_id in visited:
            continue

        # Track path for cycle reconstruction
        path = []
        current = start_id

        while current and current not in visited:
            if current in path:
                # Cycle detected - return the cycle
                cycle_start = path.index(current)
                return path[cycle_start:] + [current]

            path.append(current)
            current = parent_map.get(current)

        # Mark all nodes in path as visited
        visited.update(path)

    return None


def build_tree(
    flat_records: List[Dict[str, Any]], parent_field: str = "parent_id"
) -> List[Dict[str, Any]]:
    """Convert flat list to nested tree structure.

    Args:
        flat_records: List of flat records with parent references
        parent_field: Name of the parent ID field

    Returns:
        List of root nodes with nested children
    """
    # Build ID to record map
    id_map = {}
    for record in flat_records:
        record_id = record.get("_original_id") or record.get("id")
        if record_id:
            # Create a copy with children array
            record_copy = record.copy()
            record_copy["children"] = []
            id_map[record_id] = record_copy

    # Build tree structure
    roots = []
    for record in id_map.values():
        parent_id = record.get(parent_field)
        if parent_id and parent_id in id_map:
            # Add to parent's children
            id_map[parent_id]["children"].append(record)
        else:
            # Root node
            roots.append(record)

    return roots


def flatten_tree(
    tree_records: List[Dict[str, Any]], parent_field: str = "parent_id"
) -> List[Dict[str, Any]]:
    """Convert nested tree structure to flat list.

    Args:
        tree_records: List of root nodes with nested children
        parent_field: Name of the parent ID field

    Returns:
        Flat list of records
    """
    flat = []

    def traverse(node: Dict[str, Any], parent_id: Optional[str] = None):
        """Recursively traverse tree and flatten."""
        # Create a copy without children
        node_copy = {k: v for k, v in node.items() if k != "children"}
        node_copy[parent_field] = parent_id
        flat.append(node_copy)

        # Process children
        children = node.get("children", [])
        node_id = node.get("_original_id") or node.get("id")
        for child in children:
            traverse(child, node_id)

    for root in tree_records:
        traverse(root)

    return flat
