"""
health.py
---------
Health check resource for the Flask application.
This module provides a simple health check endpoint to verify that the service is running.
"""

import os
from datetime import datetime, timezone
from flask_restful import Resource
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.logger import logger
from app.models.db import db
from app.resources.version import API_VERSION


class HealthResource(Resource):
    """
    Resource for health check endpoint.

    This resource provides a simple way to check if the service is running
    and responding to requests.
    """

    def get(self):
        """
        GET /health

        Returns comprehensive health information including database connectivity.

        Returns:
            dict: Health status information

        Status Codes:
            - 200: Service is healthy and all checks pass
            - 503: Service is unhealthy (database connection failed)
        """
        logger.debug("Health check requested")

        # Basic service info
        health_data = {
            "status": "healthy",
            "service": "template_service",
            "timestamp": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "version": API_VERSION,
            "environment": os.getenv("FLASK_ENV", "development"),
            "checks": {},
        }

        # Database connectivity check
        db_status = self._check_database()
        health_data["checks"]["database"] = db_status

        # Determine overall status
        if not db_status["healthy"]:
            health_data["status"] = "unhealthy"
            return health_data, 503

        return health_data, 200

    def _check_database(self):
        """
        Check database connectivity and basic operations.

        Returns:
            dict: Database health status
        """
        try:
            # Test basic database connectivity
            start_time = datetime.now(timezone.utc)
            result = db.session.execute(text("SELECT 1"))
            end_time = datetime.now(timezone.utc)

            # Check if result is as expected
            if result.scalar() == 1:
                response_time_ms = (
                    end_time - start_time
                ).total_seconds() * 1000
                return {
                    "healthy": True,
                    "message": "Database connection successful",
                    "response_time_ms": round(response_time_ms, 2),
                }

            return {
                "healthy": False,
                "message": "Database query returned unexpected result",
            }

        except (OSError, SQLAlchemyError) as e:
            logger.error(f"Database health check failed: {str(e)}")
            return {
                "healthy": False,
                "message": f"Database connection failed: {str(e)}",
            }
