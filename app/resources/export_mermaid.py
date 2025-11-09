"""Mermaid diagram export resource for visual data export operations."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from flask import Response, request

from app.logger import logger
from app.utils.reference_resolver import detect_tree_structure

# Constants
MIME_JSON = "application/json"


def _parse_parameters() -> tuple[Optional[str], str]:
    """Parse and validate query parameters.

    Returns:
        Tuple of (target_url, diagram_type)
    """
    target_url = request.args.get("url")
    diagram_type = request.args.get("diagram_type", "flowchart")

    return target_url, diagram_type


def _fetch_data(target_url: str) -> Optional[List[Dict[str, Any]]]:
    """Fetch data from target URL.

    Args:
        target_url: The URL to fetch from

    Returns:
        List of records or None if error
    """
    cookies = {"access_token": request.cookies.get("access_token")}
    response = requests.get(target_url, cookies=cookies, timeout=30)
    response.raise_for_status()
    data = response.json()

    if not isinstance(data, list):
        logger.error("Target URL did not return a JSON array")
        return None

    return data


def _sanitize_label(text: str) -> str:
    """Sanitize text for use in Mermaid labels.

    Args:
        text: The text to sanitize

    Returns:
        Sanitized text safe for Mermaid
    """
    # Replace quotes and special characters that break Mermaid syntax
    text = (
        str(text)
        .replace('"', "'")
        .replace("\n", " ")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return text[:100]  # Limit length for readability


def _generate_node_id(record_id: str) -> str:
    """Generate a valid Mermaid node ID from a record ID.

    Args:
        record_id: The original record ID (UUID)

    Returns:
        Valid Mermaid node identifier
    """
    # Replace hyphens with underscores for valid Mermaid node IDs
    return f"node_{record_id.replace('-', '_')}"


def _get_label_field(record: Dict[str, Any]) -> str:
    """Extract the most appropriate label field from a record.

    Args:
        record: The data record

    Returns:
        Label text for the node
    """
    # Priority: name > title > label > description > id
    for field in ["name", "title", "label", "description"]:
        if field in record and record[field]:
            return str(record[field])

    # Fallback to id
    return str(record.get("id", "Unknown"))


def _generate_metadata(
    data: List[Dict[str, Any]],
    target_url: str,
    diagram_type: str,
    is_tree: bool = False,
) -> List[str]:
    """Generate metadata comments for the Mermaid diagram.

    Args:
        data: The data records
        target_url: The source URL
        diagram_type: The diagram type
        is_tree: Whether data has tree structure

    Returns:
        List of metadata comment lines
    """
    # Extract resource type from URL
    parsed = urlparse(target_url)
    resource_type = parsed.path.split("/")[-1] if parsed.path else "unknown"

    metadata = [
        "%% Metadata",
        f"%% export_date: {datetime.now(timezone.utc).isoformat()}",
        f"%% resource_type: {resource_type}",
        f"%% total_nodes: {len(data)}",
        f"%% service_url: {target_url}",
        f"%% diagram_type: {diagram_type}",
        f"%% is_tree: {str(is_tree).lower()}",
    ]

    return metadata


def _generate_flowchart_nodes(data: List[Dict[str, Any]]) -> List[str]:
    """Generate flowchart node definitions.

    Args:
        data: The data records

    Returns:
        List of node definition lines
    """
    lines = []
    for record in data:
        node_id = _generate_node_id(record["id"])
        label = _sanitize_label(_get_label_field(record))

        # Add original ID to label
        original_id = record.get("id", "")
        node_label = f"{label}<br/>_original_id: {original_id}"

        # Add status or other key field if present
        if "status" in record:
            node_label += f"<br/>status: {record['status']}"

        lines.append(f'    {node_id}["{node_label}"]')

    return lines


def _generate_flowchart_edges(
    data: List[Dict[str, Any]], is_tree: bool, parent_key: str
) -> List[str]:
    """Generate flowchart edge definitions.

    Args:
        data: The data records
        is_tree: Whether data has tree structure
        parent_key: Name of parent field

    Returns:
        List of edge definition lines
    """
    lines = []
    if is_tree:
        # Tree structure: parent -> child
        for record in data:
            if parent_key in record and record[parent_key]:
                child_id = _generate_node_id(record["id"])
                parent_id = _generate_node_id(record[parent_key])
                lines.append(f"    {parent_id} --> {child_id}")
    else:
        # Flat structure: sequential connections
        if len(data) > 1:
            for i in range(len(data) - 1):
                node1_id = _generate_node_id(data[i]["id"])
                node2_id = _generate_node_id(data[i + 1]["id"])
                lines.append(f"    {node1_id} --> {node2_id}")

    return lines


def _generate_click_handlers(
    data: List[Dict[str, Any]], target_url: str
) -> List[str]:
    """Generate click handler definitions.

    Args:
        data: The data records
        target_url: The base URL for links

    Returns:
        List of click handler lines
    """
    lines = []
    for record in data:
        node_id = _generate_node_id(record["id"])
        record_url = f"{target_url}/{record['id']}"
        lines.append(f'    click {node_id} "{record_url}"')

    return lines


def _generate_flowchart(data: List[Dict[str, Any]], target_url: str) -> str:
    """Generate a Mermaid flowchart diagram.

    Args:
        data: The data records
        target_url: The source URL for click links

    Returns:
        Mermaid flowchart syntax
    """
    lines = ["%%{init: {'theme':'base'}}%%", "flowchart TD"]

    # Detect tree structure
    parent_key = detect_tree_structure(data)
    is_tree = parent_key is not None

    # Add metadata
    lines.extend(_generate_metadata(data, target_url, "flowchart", is_tree))
    lines.append("")

    # Generate nodes
    lines.extend(_generate_flowchart_nodes(data))
    lines.append("")

    # Generate edges (relationships)
    lines.extend(
        _generate_flowchart_edges(data, is_tree, parent_key or "parent_id")
    )

    # Add click handlers for navigation
    lines.append("")
    lines.extend(_generate_click_handlers(data, target_url))

    return "\n".join(lines)


def _generate_graph(data: List[Dict[str, Any]], target_url: str) -> str:
    """Generate a Mermaid graph diagram.

    Args:
        data: The data records
        target_url: The source URL

    Returns:
        Mermaid graph syntax
    """
    lines = ["graph TD"]

    # Detect tree structure
    parent_key = detect_tree_structure(data)
    is_tree = parent_key is not None

    # Add metadata
    lines.extend(_generate_metadata(data, target_url, "graph", is_tree))
    lines.append("")

    # Generate nodes
    for record in data:
        node_id = _generate_node_id(record["id"])
        label = _sanitize_label(_get_label_field(record))
        lines.append(f'    {node_id}["{label}"]')

    lines.append("")

    # Generate edges
    if is_tree:
        for record in data:
            if parent_key in record and record[parent_key]:
                child_id = _generate_node_id(record["id"])
                parent_id = _generate_node_id(record[parent_key])
                lines.append(f"    {parent_id} --- {child_id}")
    else:
        # Flat: sequential connections
        if len(data) > 1:
            for i in range(len(data) - 1):
                node1_id = _generate_node_id(data[i]["id"])
                node2_id = _generate_node_id(data[i + 1]["id"])
                lines.append(f"    {node1_id} --- {node2_id}")

    return "\n".join(lines)


def _build_mindmap_tree(
    data: List[Dict[str, Any]], parent_key: str
) -> tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    """Build tree structure for mindmap.

    Args:
        data: The data records
        parent_key: Name of parent field

    Returns:
        Tuple of (root_nodes, children_map)
    """
    # Find root nodes (no parent or parent is null)
    roots = [r for r in data if not r.get(parent_key)]

    # Build children map
    children_map = {}
    for record in data:
        parent_id = record.get(parent_key)
        if parent_id:
            if parent_id not in children_map:
                children_map[parent_id] = []
            children_map[parent_id].append(record)

    return roots, children_map


def _generate_mindmap(data: List[Dict[str, Any]], target_url: str) -> str:
    """Generate a Mermaid mindmap diagram.

    Args:
        data: The data records
        target_url: The source URL

    Returns:
        Mermaid mindmap syntax
    """
    lines = ["mindmap"]

    # Detect tree structure
    parent_key = detect_tree_structure(data)
    is_tree = parent_key is not None

    # Add metadata
    lines.extend(_generate_metadata(data, target_url, "mindmap", is_tree))
    lines.append("")

    if not is_tree or not data:
        # Mindmaps work best with tree structures
        # For flat data, create a simple root with children
        lines.append("  root((Data))")
        for record in data:
            label = _sanitize_label(_get_label_field(record))
            lines.append(f"    {label}")
        return "\n".join(lines)

    # Build tree structure
    roots, children_map = _build_mindmap_tree(data, parent_key)

    def _add_node(record: Dict[str, Any], indent: int = 2):
        """Recursively add nodes to mindmap."""
        label = _sanitize_label(_get_label_field(record))
        prefix = "  " * indent

        # Root nodes use (()) syntax
        if indent == 2:
            lines.append(f"{prefix}root(({label}))")
        else:
            lines.append(f"{prefix}{label}")

        # Add children
        record_id = record["id"]
        if record_id in children_map:
            for child in children_map[record_id]:
                _add_node(child, indent + 1)

    # Add all root nodes and their children
    for root in roots:
        _add_node(root)

    return "\n".join(lines)


def export_mermaid() -> Response:
    """Export data as a Mermaid diagram.

    Query Parameters:
        url (str): Target Waterfall service endpoint URL
        diagram_type (str): Type of diagram (flowchart, graph, mindmap)

    Returns:
        Response containing Mermaid diagram syntax (text/plain)
    """
    # Parse parameters
    target_url, diagram_type = _parse_parameters()

    # Validate URL
    if not target_url:
        return Response(
            '{"message": "Missing required parameter: url"}',
            status=400,
            mimetype=MIME_JSON,
        )

    # Validate diagram type
    valid_types = ["flowchart", "graph", "mindmap"]
    if diagram_type not in valid_types:
        return Response(
            f'{{"message": "Invalid diagram_type. Must be one of: {", ".join(valid_types)}"}}',
            status=400,
            mimetype=MIME_JSON,
        )

    try:
        # Fetch data
        data = _fetch_data(target_url)
        if data is None:
            return Response(
                '{"message": "Target URL did not return valid JSON array"}',
                status=400,
                mimetype=MIME_JSON,
            )

        # Generate diagram based on type
        if diagram_type == "flowchart":
            mermaid_content = _generate_flowchart(data, target_url)
        elif diagram_type == "graph":
            mermaid_content = _generate_graph(data, target_url)
        elif diagram_type == "mindmap":
            mermaid_content = _generate_mindmap(data, target_url)
        else:
            # Should never reach here due to validation
            mermaid_content = ""

        logger.info(
            f"Exported {len(data)} records as Mermaid {diagram_type} from {target_url}"
        )

        # Return as text/plain with .mmd extension suggestion
        response = Response(mermaid_content, mimetype="text/plain")
        response.headers["Content-Disposition"] = (
            "attachment; filename=export.mmd"
        )
        return response

    except requests.RequestException as exc:
        logger.error(f"Failed to fetch data from target URL: {exc}")
        return Response(
            f'{{"message": "Failed to fetch data: {str(exc)}"}}',
            status=502,
            mimetype=MIME_JSON,
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.error(f"Export failed: {exc}")
        return Response(
            f'{{"message": "Export failed: {str(exc)}"}}',
            status=500,
            mimetype=MIME_JSON,
        )
