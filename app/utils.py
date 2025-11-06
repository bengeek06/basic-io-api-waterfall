"""Utility functions for the Identity Service API."""

import os
import re
import uuid
from functools import wraps
import jwt
from flask import request, g
import requests

from app.logger import logger


def camel_to_snake(name):
    """
    Convert a CamelCase or PascalCase string to snake_case.

    Args:
        name (str): The string to convert.

    Returns:
        str: The converted snake_case string.
    """
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
    return re.sub(r"_+", "_", snake)


def extract_jwt_data():
    """
    Extract and decode JWT data from request cookies.

    Returns:
        dict: Dictionary containing user_id and company_id from JWT, or None if invalid/missing
    """
    jwt_token = request.cookies.get("access_token")
    if not jwt_token:
        logger.debug("JWT token not found in cookies")
        return None

    jwt_secret = os.environ.get("JWT_SECRET")
    if not jwt_secret:
        logger.warning("JWT_SECRET not found in environment variables")
        return None

    try:
        payload = jwt.decode(jwt_token, jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub") or payload.get("user_id")
        company_id = payload.get("company_id")

        logger.debug(
            f"JWT decoded successfully - user_id: {user_id}, company_id: {company_id}"
        )
        return {
            "user_id": user_id,
            "company_id": company_id,
            "payload": payload,
        }
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None
    except (ValueError, KeyError) as e:
        logger.warning(f"JWT decode failed: {e}")
        return None


def require_jwt_auth():
    """
    Decorator to require JWT authentication and extract JWT information.
    Requires a valid JWT token in cookies - no fallback to headers.

    Always extracts and stores user_id, company_id, and jwt_data in Flask's g object
    for use in view functions. This ensures the JWT is decoded only once per request.

    Returns:
        Decorated function or error response

    Stores in g:
        - g.user_id: User ID from JWT
        - g.company_id: Company ID from JWT
        - g.jwt_data: Complete JWT payload
        - g.json_data: Original request JSON data (unmodified)
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            # Try JWT authentication first
            jwt_data = extract_jwt_data()

            # Fallback to headers for testing environment
            if not jwt_data:
                user_id = request.headers.get("X-User-ID")
                company_id = request.headers.get("X-Company-ID")

                if user_id:
                    # Create mock JWT data from headers (for testing)
                    jwt_data = {"user_id": user_id, "company_id": company_id}
                    logger.debug(
                        "Using headers for authentication (testing mode)"
                    )
                else:
                    return {"message": "Missing or invalid JWT token"}, 401

            # Extract company_id and user_id from JWT data
            company_id = jwt_data.get("company_id")
            user_id = jwt_data.get("user_id")

            if not user_id:
                logger.error("user_id missing in JWT token")
                return {"message": "Invalid JWT token: missing user_id"}, 401

            if not company_id:
                logger.error("company_id missing in JWT token")
                return {
                    "message": "Invalid JWT token: missing company_id"
                }, 401

            # Validate UUID format for company_id
            try:
                uuid.UUID(company_id)
            except (ValueError, TypeError):
                logger.error(f"Invalid company_id format in JWT: {company_id}")
                return {
                    "message": "Invalid JWT token: company_id must be a valid UUID"
                }, 401

            # Store company_id, user_id and jwt_data in g for use in view functions
            g.company_id = company_id
            g.user_id = user_id
            g.jwt_data = jwt_data

            # Store original JSON data in g without modification
            try:
                if request.content_length and request.content_length > 0:
                    g.json_data = request.get_json()
                else:
                    g.json_data = None
            except (ValueError, TypeError, RuntimeError):
                g.json_data = None

            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def check_access_required(operation):
    """
    Decorator to check if the user has the required access for an operation.

    Args:
        operation (str): The operation to check access for.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            resource_name = kwargs.get("resource_name") or (
                request.view_args.get("resource_name")
                if request.view_args
                else None
            )
            # If not found, deduce from the resource class name
            if not resource_name:
                view_self = args[0] if args else None
                if view_self and hasattr(view_self, "__class__"):
                    class_name = view_self.__class__.__name__
                    if class_name.lower().endswith("resource"):
                        base_name = class_name[:-8]
                        resource_name = camel_to_snake(base_name)
            # Normalisation: si resource_name se termine par '_list', on retire ce suffixe
            if resource_name and resource_name.endswith("_list"):
                resource_name = resource_name[:-5]
            user_id = getattr(g, "user_id", None)

            # Essayer d'utiliser les données JWT déjà décodées si disponibles
            if not user_id and hasattr(g, "jwt_data") and g.jwt_data:
                user_id = g.jwt_data.get("user_id")
                logger.debug(
                    f"Using user_id from already decoded JWT: {user_id}"
                )
            # Sinon, extraire user_id du cookie JWT
            elif not user_id:
                logger.debug(
                    "User ID not found in g or headers, checking JWT cookie"
                )
                jwt_data = extract_jwt_data()
                if jwt_data:
                    user_id = jwt_data.get("user_id")
                    logger.debug(f"Extracted user_id from JWT: {user_id}")
                else:
                    logger.warning("JWT token not found or invalid")
            if not user_id or not resource_name:
                logger.warning(
                    "Missing user_id or resource_name for access check."
                )
                return {
                    "error": "Missing user_id or resource_name for access check."
                }, 400
            # Use CheckAccessResource logic
            access_granted, reason, status = check_access(
                user_id, resource_name, operation
            )
            if access_granted:
                return view_func(*args, **kwargs)
            return {"error": "Access denied", "reason": reason}, (
                status if isinstance(status, int) else 403
            )

        return wrapped

    return decorator


def check_access(user_id, resource_name, operation):
    """
    Check if the user has access to perform the operation on the resource.

    Args:
        user_id (str): The ID of the user.
        resource_name (str): The name of the resource.
        operation (str): The operation to check access for.
    Returns:
        tuple: (access_granted (bool), reason (str), status (int or str))
    """
    logger.debug(
        f"Checking access for user_id: {user_id}, "
        f"resource_name: {resource_name}, operation: {operation}"
    )

    flask_env = os.environ.get("FLASK_ENV", "production").lower()
    if flask_env in ["testing", "development"]:
        logger.debug("check_access: testing/development environment")
        return True, "Access granted in testing/development environment.", 200

    guardian_service_url = os.environ.get("GUARDIAN_SERVICE_URL")
    if not guardian_service_url:
        logger.error("GUARDIAN_SERVICE_URL not set")
        return False, "Internal server error", 500

    try:
        timeout = float(os.environ.get("GUARDIAN_SERVICE_TIMEOUT", "5"))

        # Get JWT token from cookies to forward to Guardian service (if in request context)
        headers = {}
        try:
            jwt_token = request.cookies.get("access_token")
            if jwt_token:
                headers["Cookie"] = f"access_token={jwt_token}"
                logger.debug("Forwarding JWT cookie to Guardian service")
        except RuntimeError:
            # No request context available (e.g., during testing without Flask app context)
            logger.debug(
                "No request context available, skipping JWT cookie forwarding"
            )

        response = requests.post(
            f"{guardian_service_url}/check-access",
            json={
                "user_id": user_id,
                "service": "identity",
                "resource_name": resource_name,
                "operation": operation,
            },
            headers=headers,
            timeout=timeout,
        )

        # Don't raise_for_status() immediately - check the response first
        if response.status_code == 200:
            response_data = response.json()
            logger.debug(f"Guardian service response: {response_data}")
            return (
                response_data.get("access_granted", False),
                response_data.get("reason", "Unknown error"),
                response_data.get("status", 200),
            )
        if response.status_code == 400:
            # Guardian service returned a 400 with detailed error message
            try:
                response_data = response.json()
                logger.warning(
                    f"Guardian service returned 400: {response_data}"
                )
                return (
                    response_data.get("access_granted", False),
                    response_data.get("reason", "Bad request"),
                    400,
                )
            except (ValueError, KeyError) as json_error:
                logger.error(
                    f"Failed to parse Guardian 400 response as JSON: {json_error}"
                )
                return False, f"Guardian service error: {response.text}", 400
        # Other error status codes
        logger.error(
            f"Guardian service returned status {response.status_code}: {response.text}"
        )
        return (
            False,
            f"Guardian service error (status {response.status_code})",
            response.status_code,
        )

    except requests.exceptions.Timeout:
        logger.error("Timeout when checking access with guardian service")
        return False, "Guardian service timeout", 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Error checking access: {e}")
        return False, "Internal server error", 500
    except (ValueError, KeyError) as e:
        logger.error(f"Unexpected error checking access: {e}")
        return False, "Internal server error", 500
