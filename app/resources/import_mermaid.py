"""Mermaid diagram import resource for importing visual diagram data."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

import requests
from flask import Response, request
from werkzeug.datastructures import FileStorage

from app.logger import logger

# Constants
MIME_JSON = "application/json"


def _parse_metadata(lines: List[str]) -> Dict[str, str]:
    """Parse metadata from Mermaid comment lines.

    Args:
        lines: List of lines from the Mermaid file

    Returns:
        Dictionary of metadata key-value pairs
    """
    metadata = {}
    for line in lines:
        if line.startswith("%%") and ":" in line:
            # Remove %% prefix and parse key: value
            content = line.lstrip("%").strip()
            if content and ":" in content:
                key, value = content.split(":", 1)
                metadata[key.strip()] = value.strip()

    return metadata


def _parse_node_definition(
    line: str, records: Dict[str, Dict[str, Any]]
) -> bool:
    """Parse a node definition line.

    Args:
        line: The line to parse
        records: Dictionary to add the parsed node to

    Returns:
        True if a node was parsed, False otherwise
    """
    # Parse node definitions: node_id["Label<br/>field: value"]
    node_match = re.match(r'(\w+)\["([^"]+)"\]', line)
    if not node_match:
        return False

    node_id, label_content = node_match.groups()

    # Parse label content (split by <br/>)
    parts = label_content.split("<br/>")
    name = parts[0] if parts else "Unknown"

    # Extract fields from additional parts
    record = {"name": name}

    for part in parts[1:]:
        if ":" in part:
            key, value = part.split(":", 1)
            key = key.strip()
            value = value.strip()

            if key == "_original_id":
                record["id"] = value
            else:
                record[key] = value

    # If no ID was found in label, use node_id
    if "id" not in record:
        # Convert node_node_id format back to node-id
        original_id = node_id.replace("node_", "").replace("_", "-")
        record["id"] = original_id

    records[node_id] = record
    return True


def _parse_flowchart_lines(
    lines: List[str],
) -> Tuple[Dict[str, Dict[str, Any]], List[Tuple[str, str]]]:
    """Parse flowchart lines into nodes and relationships.

    Args:
        lines: List of lines from the diagram

    Returns:
        Tuple of (records dict, relationships list)
    """
    records = {}
    relationships = []

    for line in lines:
        line = line.strip()

        # Skip metadata comments, empty lines, declarations
        if (
            not line
            or line.startswith("%%")
            or line.startswith("flowchart")
            or line.startswith("%%{init")
            or line.startswith("click")
        ):
            continue

        # Parse edges (relationships): node1 --> node2
        edge_match = re.match(r"(\w+)\s*-->\s*(\w+)", line)
        if edge_match:
            parent_id, child_id = edge_match.groups()
            relationships.append((parent_id, child_id))
            continue

        # Try to parse node definition
        _parse_node_definition(line, records)

    return records, relationships


def _parse_flowchart(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse a Mermaid flowchart diagram.

    Args:
        lines: List of lines from the diagram

    Returns:
        List of records extracted from the diagram
    """
    # Parse metadata to check if this is a tree structure
    metadata = _parse_metadata(lines)
    is_tree = metadata.get("is_tree", "false").lower() == "true"

    records, relationships = _parse_flowchart_lines(lines)

    # Apply relationships to establish parent_id ONLY if tree structure
    if is_tree:
        for parent_node_id, child_node_id in relationships:
            if child_node_id in records and parent_node_id in records:
                parent_original_id = records[parent_node_id].get("id")
                records[child_node_id]["parent_id"] = parent_original_id

    return list(records.values())


def _parse_graph(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse a Mermaid graph diagram.

    Args:
        lines: List of lines from the diagram

    Returns:
        List of records extracted from the diagram
    """
    # Parse metadata to check if this is a tree structure
    metadata = _parse_metadata(lines)
    is_tree = metadata.get("is_tree", "false").lower() == "true"

    records = {}
    relationships = []

    # Parse node definitions and edges
    for line in lines:
        line = line.strip()

        # Skip metadata comments and empty lines
        if line.startswith("%%") or not line or line.startswith("graph"):
            continue

        # Parse edges: node1 --- node2
        edge_match = re.match(r"(\w+)\s*---\s*(\w+)", line)
        if edge_match:
            parent_id, child_id = edge_match.groups()
            relationships.append((parent_id, child_id))
            continue

        # Parse node definitions: node_id["Label"]
        node_match = re.match(r'(\w+)\["([^"]+)"\]', line)
        if node_match:
            node_id, label = node_match.groups()

            # Convert node_id back to original ID
            original_id = node_id.replace("node_", "").replace("_", "-")

            record = {"id": original_id, "name": label}
            records[node_id] = record

    # Apply relationships to establish parent_id ONLY if tree structure
    if is_tree:
        for parent_node_id, child_node_id in relationships:
            if child_node_id in records and parent_node_id in records:
                parent_original_id = records[parent_node_id].get("id")
                records[child_node_id]["parent_id"] = parent_original_id

    return list(records.values())


def _extract_mindmap_label(label: str) -> Optional[str]:
    """Extract label from mindmap node syntax.

    Args:
        label: Raw label text

    Returns:
        Extracted label or None if empty
    """
    # Extract label from root((Label)) or just Label
    if label.startswith("root((") and label.endswith("))"):
        label = label[6:-2]  # Remove root(( and ))
    elif label.startswith("((") and label.endswith("))"):
        label = label[2:-2]

    return label if label else None


def _parse_mindmap(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse a Mermaid mindmap diagram.

    Args:
        lines: List of lines from the diagram

    Returns:
        List of records extracted from the diagram
    """
    records = []
    stack = []  # Stack to track parent hierarchy

    for line in lines:
        # Skip metadata and empty lines
        if (
            line.startswith("%%")
            or not line.strip()
            or line.strip() == "mindmap"
        ):
            continue

        # Calculate indentation level
        indent = len(line) - len(line.lstrip())
        label = _extract_mindmap_label(line.strip())

        # Skip empty labels
        if not label:
            continue

        # Generate ID from label (simple approach)
        record_id = f"node-{len(records) + 1}"
        record = {"id": record_id, "name": label}

        # Determine parent based on indentation
        # Pop stack until we find the right parent level
        while stack and stack[-1][0] >= indent:
            stack.pop()

        if stack:
            _, parent_id = stack[-1]
            record["parent_id"] = parent_id

        records.append(record)
        stack.append((indent, record_id))

    return records


def _detect_diagram_type(content: str) -> Optional[str]:
    """Detect the type of Mermaid diagram from content.

    Args:
        content: The Mermaid diagram content

    Returns:
        Diagram type (flowchart, graph, mindmap) or None
    """
    lines = content.split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("flowchart"):
            return "flowchart"
        if line.startswith("graph"):
            return "graph"
        if line.strip() == "mindmap":
            return "mindmap"

    return None


def _topological_sort(
    records: List[Dict[str, Any]], parent_field: str
) -> List[Dict[str, Any]]:
    """Sort records in dependency order (parents before children).

    Args:
        records: List of records to sort
        parent_field: Name of parent field

    Returns:
        Sorted list of records
    """
    # Build ID to record map
    id_map = {r["id"]: r for r in records}

    # Build dependency graph
    visited = set()
    result = []

    def visit(record_id):
        if record_id in visited:
            return
        visited.add(record_id)

        record = id_map.get(record_id)
        if not record:
            return

        # Visit parent first
        parent_id = record.get(parent_field)
        if parent_id and parent_id in id_map:
            visit(parent_id)

        result.append(record)

    # Visit all records
    for record in records:
        visit(record["id"])

    return result


def _import_records(
    records: List[Dict[str, Any]],
    target_url: str,
    cookies: Dict[str, str],
) -> Dict[str, Any]:
    """Import records to target service.

    Args:
        records: Records to import
        target_url: Target service URL
        cookies: Authentication cookies

    Returns:
        Import report
    """
    report = {
        "total_records": len(records),
        "successful_imports": 0,
        "failed_imports": 0,
        "id_mapping": {},
        "errors": [],
    }

    for record in records:
        original_id = record.get("id")

        # Update parent_id if it was remapped
        if (
            "parent_id" in record
            and record["parent_id"] in report["id_mapping"]
        ):
            record["parent_id"] = report["id_mapping"][record["parent_id"]]

        # Remove read-only fields before POST
        # Note: parent_id is intentionally kept if present for tree structures
        readonly_fields = {"id", "created_at", "updated_at", "children"}
        clean_record = {
            k: v for k, v in record.items() if k not in readonly_fields
        }

        try:
            response = requests.post(
                target_url,
                json=clean_record,
                cookies=cookies,
                timeout=30,
            )
            response.raise_for_status()

            new_record = response.json()
            new_id = new_record.get("id")

            if new_id and original_id:
                report["id_mapping"][original_id] = new_id

            report["successful_imports"] += 1

        except Exception as exc:  # pylint: disable=broad-except
            report["failed_imports"] += 1
            report["errors"].append(
                {
                    "original_id": original_id,
                    "error": str(exc),
                }
            )

    return report


def import_mermaid() -> Response:
    """Import data from a Mermaid diagram file.

    Form Parameters:
        file: The Mermaid .mmd file to import

    Query Parameters:
        url (str): Target Waterfall service endpoint URL
        resolve_foreign_keys (bool): Whether to resolve FKs (default: true)
        skip_on_ambiguous (bool): Skip records with ambiguous FKs (default: false)
        skip_on_missing (bool): Skip records with missing FKs (default: false)

    Returns:
        JSON response with import report
    """
    # Validate file upload
    if "file" not in request.files:
        return Response(
            '{"message": "No file uploaded"}',
            status=400,
            mimetype=MIME_JSON,
        )

    file: FileStorage = request.files["file"]
    if file.filename == "":
        return Response(
            '{"message": "No file selected"}',
            status=400,
            mimetype=MIME_JSON,
        )

    try:
        # Read Mermaid content
        content = file.read().decode("utf-8")
        lines = content.split("\n")

        # Parse metadata
        metadata = _parse_metadata(lines)
        logger.info(f"Parsed Mermaid metadata: {metadata}")

        # Detect diagram type
        diagram_type = _detect_diagram_type(content)
        if not diagram_type:
            return Response(
                '{"message": "Could not detect Mermaid diagram type"}',
                status=400,
                mimetype=MIME_JSON,
            )

        # Parse diagram based on type
        if diagram_type == "flowchart":
            records = _parse_flowchart(lines)
        elif diagram_type == "graph":
            records = _parse_graph(lines)
        elif diagram_type == "mindmap":
            records = _parse_mindmap(lines)
        else:
            return Response(
                f'{{"message": "Unsupported diagram type: {diagram_type}"}}',
                status=400,
                mimetype=MIME_JSON,
            )

        logger.info(
            f"Parsed {len(records)} records from Mermaid {diagram_type} diagram"
        )

        # Get target URL from query params
        target_url = request.values.get("url")
        if not target_url:
            return Response(
                '{"message": "Missing required parameter: url"}',
                status=400,
                mimetype=MIME_JSON,
            )

        # Sort records if they have parent_id (tree structure)
        has_parent = any("parent_id" in r for r in records)
        if has_parent:
            records = _topological_sort(records, "parent_id")
            logger.info("Sorted records in topological order")

        # Import records
        cookies = {"access_token": request.cookies.get("access_token")}
        result = _import_records(records, target_url, cookies)

        logger.info(
            f"Import completed: {result['successful_imports']} success, "
            f"{result['failed_imports']} failed"
        )

        return Response(
            json.dumps(result),
            status=200,
            mimetype=MIME_JSON,
        )

    except UnicodeDecodeError as exc:
        logger.error(f"File encoding error: {exc}")
        return Response(
            '{"message": "File must be UTF-8 encoded"}',
            status=400,
            mimetype=MIME_JSON,
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.error(f"Import failed: {exc}")
        return Response(
            f'{{"message": "Import failed: {str(exc)}"}}',
            status=500,
            mimetype=MIME_JSON,
        )
