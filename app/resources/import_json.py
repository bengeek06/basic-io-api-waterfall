"""JSON import resource for data import operations."""

import json
from typing import Any, Dict, List, Optional, Tuple

import requests
from flask import request

from app.logger import logger
from app.utils.reference_resolver import (
    detect_tree_structure,
    flatten_tree,
    resolve_reference,
    topological_sort,
)


# Functions for JSON import


def _parse_file(file) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Parse and validate uploaded JSON file.

    Args:
        file: FileStorage object from request

    Returns:
        Tuple of (data, error_message)
    """
    if not file:
        logger.error("No file provided")
        return None, "No file provided"

    if file.filename == "":
        logger.error("Empty filename")
        return None, "Empty filename"

    if not file.filename.endswith(".json"):
        logger.error(f"Invalid file type: {file.filename}")
        return None, "File must be a JSON file (.json)"

    try:
        logger.info(f"Reading JSON file: {file.filename}")
        content = file.read().decode("utf-8")
        data = json.loads(content)

        if not isinstance(data, list):
            logger.error("JSON file must be an array")
            return None, "JSON file must contain an array of records"

        logger.info(f"JSON contains {len(data)} records")
        return data, None

    except UnicodeDecodeError:
        logger.error("File encoding error - not UTF-8")
        return None, "File encoding must be UTF-8"
    except json.JSONDecodeError as exc:
        logger.error(f"JSON parsing error: {exc}")
        return None, f"Invalid JSON format: {exc}"


def _prepare_data(
    data: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Prepare data for import (flatten tree if needed, sort by dependencies).

    Args:
        data: Raw data from file

    Returns:
        Tuple of (prepared_data, parent_field)
    """
    # Check if data is in tree format (nested children)
    is_tree = any("children" in record for record in data)

    # Detect parent field
    parent_field = detect_tree_structure(data) if not is_tree else "parent_id"

    # Flatten tree structure if needed
    if is_tree:
        logger.info("Flattening tree structure")
        data = flatten_tree(data, parent_field)

    # Sort by dependencies if tree structure present
    if parent_field:
        logger.info(f"Sorting records by {parent_field} dependencies")
        data = topological_sort(data, parent_field)

    return data, parent_field


def _resolve_single_reference(
    field_name: str,
    ref_metadata: Dict[str, Any],
    target_url: str,
    cookies: Dict[str, str],
    resolution_report: Dict[str, Any],
    on_ambiguous: str = "skip",
    on_missing: str = "skip",
) -> Optional[str]:
    """Resolve a single foreign key reference.

    Args:
        field_name: Name of the field being resolved
        ref_metadata: Reference metadata
        target_url: Base URL of target service
        cookies: Authentication cookies
        resolution_report: Report dict to update
        on_ambiguous: How to handle ambiguous references ("skip" or "fail")
        on_missing: How to handle missing references ("skip" or "fail")

    Returns:
        Resolved ID or None depending on resolution status and mode
    """
    status, resolved_id, candidates, error = resolve_reference(
        ref_metadata, target_url, cookies
    )

    if status == "resolved":
        resolution_report["resolved"] += 1
        lookup_val = ref_metadata.get("lookup_value")
        logger.debug(f"Resolved {field_name}: {lookup_val} -> {resolved_id}")
        return resolved_id

    if status == "ambiguous":
        resolution_report["ambiguous"] += 1
        resolution_report["details"].append(
            {
                "field": field_name,
                "status": "ambiguous",
                "lookup_value": ref_metadata.get("lookup_value"),
                "candidates": len(candidates),
            }
        )
        # With skip mode: set FK to None instead of assigning random ID
        # With fail mode: will be validated later in import_json()
        if on_ambiguous == "skip":
            logger.warning(
                f"Ambiguous reference for {field_name}, setting to None (skip mode)"
            )
            return None
        # fail mode: return original_id to track the issue
        logger.warning(
            f"Ambiguous reference for {field_name} (fail mode will reject import)"
        )
        return ref_metadata.get("original_id")

    if status == "missing":
        resolution_report["missing"] += 1
        resolution_report["details"].append(
            {
                "field": field_name,
                "status": "missing",
                "lookup_value": ref_metadata.get("lookup_value"),
                "error": error,
            }
        )
        # Both skip and fail modes set FK to None
        # fail mode will be validated later in import_json()
        if on_missing == "skip":
            logger.warning(
                f"Missing reference for {field_name}, setting to None (skip mode)"
            )
        else:
            logger.warning(
                f"Missing reference for {field_name} (fail mode will reject import)"
            )
        return None

    # error
    resolution_report["errors"] += 1
    resolution_report["details"].append(
        {
            "field": field_name,
            "status": "error",
            "error": error,
        }
    )
    return ref_metadata.get("original_id")


def _resolve_references(
    records: List[Dict[str, Any]],
    target_url: str,
    cookies: Dict[str, str],
    on_ambiguous: str = "skip",
    on_missing: str = "skip",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Resolve foreign key references for records.

    Args:
        records: List of records with _references metadata
        target_url: Base URL of target service
        cookies: Authentication cookies
        on_ambiguous: How to handle ambiguous references ("skip" or "fail")
        on_missing: How to handle missing references ("skip" or "fail")

    Returns:
        Tuple of (resolved_records, resolution_report)
    """
    resolution_report = {
        "resolved": 0,
        "ambiguous": 0,
        "missing": 0,
        "errors": 0,
        "details": [],
    }

    resolved_records = []

    for record in records:
        # Skip records without references
        if "_references" not in record:
            resolved_records.append(record)
            continue

        references = record.pop("_references")
        resolved_record = record.copy()

        # Resolve each reference
        for field_name, ref_metadata in references.items():
            resolved_id = _resolve_single_reference(
                field_name,
                ref_metadata,
                target_url,
                cookies,
                resolution_report,
                on_ambiguous,
                on_missing,
            )
            resolved_record[field_name] = resolved_id

        resolved_records.append(resolved_record)

    return resolved_records, resolution_report


def _update_parent_reference(
    record: Dict[str, Any],
    parent_field: str,
    id_mapping: Dict[str, str],
) -> None:
    """Update parent reference in record using ID mapping.

    Args:
        record: Record to update
        parent_field: Name of parent field
        id_mapping: Mapping of old IDs to new IDs
    """
    old_parent_id = record.get(parent_field)
    if not old_parent_id:
        return

    new_parent_id = id_mapping.get(old_parent_id)
    if new_parent_id:
        record[parent_field] = new_parent_id
    else:
        logger.warning(
            f"Parent {old_parent_id} not found in mapping for record"
        )


def _clean_readonly_fields(record: Dict[str, Any]) -> Dict[str, Any]:
    """Remove read-only fields that should not be sent in POST requests.

    Args:
        record: Record to clean

    Returns:
        Cleaned record without read-only fields
    """
    readonly_fields = {
        "id",  # Generated by server
        "created_at",  # Auto-generated timestamp
        "updated_at",  # Auto-generated timestamp
        "_original_id",  # Import metadata
        "_references",  # Import metadata
        "children",  # Tree structure metadata
    }

    return {k: v for k, v in record.items() if k not in readonly_fields}


def _import_single_record(
    record: Dict[str, Any],
    target_url: str,
    cookies: Dict[str, str],
) -> Tuple[bool, Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    """Import a single record to target service.

    Args:
        record: Record to import
        target_url: Target service URL
        cookies: Authentication cookies

    Returns:
        Tuple of (success, original_id, new_id, error_detail)
    """
    original_id = record.get("_original_id")

    # Clean read-only fields before POST
    clean_record = _clean_readonly_fields(record)

    try:
        response = requests.post(
            target_url,
            json=clean_record,
            cookies=cookies,
            timeout=30,
        )
        response.raise_for_status()
        created = response.json()
        new_id = created.get("id")

        logger.debug(f"Imported record: {original_id} -> {new_id}")
        return True, original_id, new_id, None

    except requests.exceptions.HTTPError as exc:
        error_detail = {
            "original_id": original_id,
            "status_code": exc.response.status_code,
            "error": exc.response.text if exc.response else str(exc),
        }
        logger.error(f"Failed to import record {original_id}: {error_detail}")
        return False, original_id, None, error_detail

    except requests.exceptions.RequestException as exc:
        error_detail = {
            "original_id": original_id,
            "error": str(exc),
        }
        logger.error(f"Request failed for record {original_id}: {exc}")
        return False, original_id, None, error_detail


def _import_records(
    records: List[Dict[str, Any]],
    target_url: str,
    cookies: Dict[str, str],
    parent_field: Optional[str],
) -> Dict[str, Any]:
    """Import records to target service.

    Args:
        records: Prepared records to import
        target_url: Target service URL
        cookies: Authentication cookies
        parent_field: Name of parent field if tree structure

    Returns:
        Import report with success/failure counts
    """
    import_report = {
        "total": len(records),
        "success": 0,
        "failed": 0,
        "id_mapping": {},
        "errors": [],
    }

    for record in records:
        # Update parent reference if tree structure
        if parent_field:
            _update_parent_reference(
                record, parent_field, import_report["id_mapping"]
            )

        # Import single record
        success, original_id, new_id, error_detail = _import_single_record(
            record, target_url, cookies
        )

        if success:
            import_report["success"] += 1
            if original_id and new_id:
                import_report["id_mapping"][original_id] = new_id
        else:
            import_report["failed"] += 1
            if error_detail:
                import_report["errors"].append(error_detail)

    return import_report


def import_json():
    """Import data from a JSON file to a Waterfall service endpoint.

    Form Data:
        file: JSON file to import
        url (str): Target service URL to import to
        resolve_refs (bool): Resolve foreign key references (default: True)
        on_ambiguous (str): How to handle ambiguous references - "skip" or "fail" (default: "skip")
        on_missing (str): How to handle missing references - "skip" or "fail" (default: "skip")

    Returns:
        JSON response with import report
    """
    # Get file from request
    if "file" not in request.files:
        logger.error("No file provided in request")
        return {"message": "No file provided"}, 400

    file = request.files["file"]

    # Get URL from form data
    target_url = request.values.get("url")
    if not target_url:
        logger.error("Missing 'url' parameter")
        return {"message": "Missing required parameter: url"}, 400

    resolve_refs = request.values.get("resolve_refs", "true").lower() == "true"
    on_ambiguous = request.values.get("on_ambiguous", "skip").lower()
    on_missing = request.values.get("on_missing", "skip").lower()

    # Validate mode parameters
    if on_ambiguous not in ["skip", "fail"]:
        return {
            "message": f"Invalid on_ambiguous mode: {on_ambiguous}. Must be 'skip' or 'fail'"
        }, 400
    if on_missing not in ["skip", "fail"]:
        return {
            "message": f"Invalid on_missing mode: {on_missing}. Must be 'skip' or 'fail'"
        }, 400

    logger.info(
        f"JSON import request - url={target_url}, "
        f"resolve_refs={resolve_refs}, "
        f"on_ambiguous={on_ambiguous}, "
        f"on_missing={on_missing}, "
        f"file={file.filename}"
    )

    # Parse uploaded file
    logger.info(f"Parsing uploaded file for import to {target_url}")
    data, error = _parse_file(file)
    if error:
        return {"message": error}, 400

    logger.info(f"Parsed {len(data)} records from file")

    # Prepare data (flatten tree, sort dependencies)
    try:
        data, parent_field = _prepare_data(data)
        logger.info(f"Prepared {len(data)} records for import")
    except ValueError as exc:
        return {"message": f"Data preparation failed: {exc}"}, 400

    # Resolve references if requested
    resolution_report = None
    if resolve_refs:
        cookies = {"access_token": request.cookies.get("access_token")}
        logger.info("Resolving foreign key references")
        data, resolution_report = _resolve_references(
            data, target_url, cookies, on_ambiguous, on_missing
        )

        # Check for resolution issues based on fail modes
        if on_ambiguous == "fail" and resolution_report["ambiguous"] > 0:
            logger.error(
                f"Import aborted: {resolution_report['ambiguous']} ambiguous reference(s) "
                f"with on_ambiguous=fail mode"
            )
            return {
                "message": "Import failed due to ambiguous references",
                "resolution_report": resolution_report,
            }, 400

        if on_missing == "fail" and resolution_report["missing"] > 0:
            logger.error(
                f"Import aborted: {resolution_report['missing']} missing reference(s) "
                f"with on_missing=fail mode"
            )
            return {
                "message": "Import failed due to missing references",
                "resolution_report": resolution_report,
            }, 400

        # Log warnings for skip mode
        if (
            resolution_report["ambiguous"] > 0
            or resolution_report["missing"] > 0
        ):
            logger.warning(
                f"Reference resolution issues: "
                f"{resolution_report['ambiguous']} ambiguous, "
                f"{resolution_report['missing']} missing"
            )

    # Import records to target service
    cookies = {"access_token": request.cookies.get("access_token")}
    logger.info(f"Importing {len(data)} records to {target_url}")

    import_report = _import_records(data, target_url, cookies, parent_field)

    # Build response
    response = {
        "import_report": import_report,
    }

    if resolution_report:
        response["resolution_report"] = resolution_report

    # Determine status code
    if import_report["failed"] == 0:
        status_code = 201  # All records imported successfully
    elif import_report["success"] > 0:
        status_code = 207  # Partial success
    else:
        status_code = 400  # All records failed

    logger.info(
        f"Import completed: {import_report['success']} success, "
        f"{import_report['failed']} failed"
    )

    return response, status_code
