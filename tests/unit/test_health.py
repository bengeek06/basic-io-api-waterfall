"""
test_health.py
--------------
Tests for the health check endpoint.
"""

import json
from time import sleep
import threading
import logging
from unittest.mock import patch, MagicMock
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError


class TestHealthEndpoint:
    """Test cases for the health check endpoint."""

    def test_health_check_success(self, client):
        """Test successful health check with all systems healthy."""
        response = client.get("/health")

        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] == "healthy"
        assert data["service"] == "template_service"
        assert "timestamp" in data
        assert "environment" in data
        assert "checks" in data

        # Validate timestamp format (ISO 8601)
        timestamp = data["timestamp"]
        assert timestamp.endswith("Z")
        # Should be able to parse the timestamp
        datetime.fromisoformat(timestamp[:-1])

        # Check database status
        db_check = data["checks"]["database"]
        assert db_check["healthy"] is True
        assert db_check["message"] == "Database connection successful"
        assert "response_time_ms" in db_check
        assert isinstance(db_check["response_time_ms"], (int, float))
        assert db_check["response_time_ms"] >= 0

    def test_health_check_database_failure(self, client):
        """Test health check when database connection fails."""
        with patch("app.resources.health.db.session.execute") as mock_execute:
            mock_execute.side_effect = SQLAlchemyError("Connection timeout")

            response = client.get("/health")

            assert response.status_code == 503

            data = response.get_json()
            assert data["status"] == "unhealthy"
            assert data["service"] == "template_service"

            db_check = data["checks"]["database"]
            assert db_check["healthy"] is False
            assert "Connection timeout" in db_check["message"]

    def test_health_check_database_unexpected_result(self, client):
        """Test health check when database returns unexpected result."""
        with patch("app.resources.health.db.session.execute") as mock_execute:
            # Mock result that returns something other than 1
            mock_result = MagicMock()
            mock_result.scalar.return_value = 0
            mock_execute.return_value = mock_result

            response = client.get("/health")

            assert response.status_code == 503

            data = response.get_json()
            assert data["status"] == "unhealthy"

            db_check = data["checks"]["database"]
            assert db_check["healthy"] is False
            assert "unexpected result" in db_check["message"]

    def test_health_check_response_format(self, client):
        """Test that health check response has correct format and required fields."""
        response = client.get("/health")

        assert response.content_type == "application/json"

        data = response.get_json()

        # Required top-level fields
        required_fields = [
            "status",
            "service",
            "timestamp",
            "version",
            "environment",
            "checks",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Status should be either 'healthy' or 'unhealthy'
        assert data["status"] in ["healthy", "unhealthy"]

        # Service should be template_service
        assert data["service"] == "template_service"

        # Checks should contain database
        assert "database" in data["checks"]

        # Database check should have required fields
        db_check = data["checks"]["database"]
        assert "healthy" in db_check
        assert "message" in db_check
        assert isinstance(db_check["healthy"], bool)

    def test_health_check_environment_variable(self, client):
        """Test that health check includes environment information."""
        with patch.dict("os.environ", {"FLASK_ENV": "testing"}):
            response = client.get("/health")

            data = response.get_json()
            assert data["environment"] == "testing"

    def test_health_check_default_environment(self, client):
        """Test default environment when FLASK_ENV is not set."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("os.getenv") as mock_getenv:
                mock_getenv.return_value = "development"

                response = client.get("/health")

                data = response.get_json()
                assert data["environment"] == "development"

    def test_health_check_multiple_requests(self, client):
        """Test that multiple health check requests work correctly."""
        # Make multiple requests
        responses = []
        for _ in range(3):
            response = client.get("/health")
            responses.append(response)

        # All should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "healthy"

    def test_health_check_database_response_time_measurement(self, client):
        """Test that database response time is measured correctly."""
        response = client.get("/health")

        assert response.status_code == 200

        data = response.get_json()
        db_check = data["checks"]["database"]

        # Response time should be a positive number
        response_time = db_check["response_time_ms"]
        assert isinstance(response_time, (int, float))
        assert response_time >= 0
        # Should be reasonable (less than 1 second for local DB)
        assert response_time < 1000

    def test_health_check_logging(self, client, caplog):
        """Test that health check requests are logged."""

        # Set the log level to DEBUG to capture debug messages
        with caplog.at_level(logging.DEBUG):
            response = client.get("/health")

            assert response.status_code == 200

            # Check that debug message was logged
            assert any(
                "Health check requested" in record.message
                for record in caplog.records
            )

    def test_health_check_database_logging_on_error(self, client, caplog):
        """Test that database errors are properly logged."""

        with caplog.at_level(logging.ERROR):
            with patch(
                "app.resources.health.db.session.execute"
            ) as mock_execute:
                mock_execute.side_effect = SQLAlchemyError(
                    "Test database error"
                )

                response = client.get("/health")

                assert response.status_code == 503

                # Check that error was logged
                assert any(
                    "Database health check failed" in record.message
                    and "Test database error" in record.message
                    for record in caplog.records
                )

    def test_health_check_sql_query_execution(self, client):
        """Test that the correct SQL query is executed for health check."""
        with patch("app.resources.health.db.session.execute") as mock_execute:
            # Mock successful result
            mock_result = MagicMock()
            mock_result.scalar.return_value = 1
            mock_execute.return_value = mock_result

            response = client.get("/health")

            # Verify the SQL query was called
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args[0]
            assert len(call_args) == 1

            # Check that it's a SQL text object with SELECT 1
            sql_obj = call_args[0]
            assert hasattr(sql_obj, "text") or str(sql_obj) == "SELECT 1"

            assert response.status_code == 200

    def test_health_check_json_serializable(self, client):
        """Test that health check response is JSON serializable."""
        response = client.get("/health")

        # Should not raise exception
        data = response.get_json()

        # Should be able to serialize back to JSON
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

        # Should be able to deserialize
        parsed_data = json.loads(json_str)
        assert parsed_data == data

    def test_health_check_only_supports_get(self, client):
        """Test that health endpoint only supports GET method."""
        # POST should return 405 Method Not Allowed
        response = client.post("/health")
        assert response.status_code == 405

        # PUT should return 405 Method Not Allowed
        response = client.put("/health")
        assert response.status_code == 405

        # DELETE should return 405 Method Not Allowed
        response = client.delete("/health")
        assert response.status_code == 405

    def test_health_check_database_slow_response(self, client):
        """Test health check with a slow database response."""

        def slow_execute(*_args, **_kwargs):
            # Simulate a slow database
            sleep(0.1)  # 100ms delay
            mock_result = MagicMock()
            mock_result.scalar.return_value = 1
            return mock_result

        with patch(
            "app.resources.health.db.session.execute", side_effect=slow_execute
        ):
            response = client.get("/health")

            assert response.status_code == 200

            data = response.get_json()
            db_check = data["checks"]["database"]
            assert db_check["healthy"] is True

            # Response time should reflect the delay (should be >= 100ms)
            assert db_check["response_time_ms"] >= 100

    def test_health_check_database_connection_none_result(self, client):
        """Test health check when database execute returns None."""
        with patch("app.resources.health.db.session.execute") as mock_execute:
            mock_result = MagicMock()
            mock_result.scalar.return_value = None
            mock_execute.return_value = mock_result

            response = client.get("/health")

            assert response.status_code == 503

            data = response.get_json()
            assert data["status"] == "unhealthy"

            db_check = data["checks"]["database"]
            assert db_check["healthy"] is False
            assert "unexpected result" in db_check["message"]

    def test_health_check_timestamp_format_consistency(self, client):
        """Test that timestamp format is consistent across multiple requests."""
        responses = []
        for _ in range(3):
            response = client.get("/health")
            responses.append(response)

        timestamps = [resp.get_json()["timestamp"] for resp in responses]

        # All timestamps should end with 'Z' (UTC indicator)
        for timestamp in timestamps:
            assert timestamp.endswith("Z")

        # All timestamps should be parseable as ISO format
        for timestamp in timestamps:
            # Remove 'Z' and parse
            dt = datetime.fromisoformat(timestamp[:-1])
            assert isinstance(dt, datetime)

    def test_health_check_concurrent_requests(self, client):
        """Test concurrent health check requests."""

        results = []
        errors = []

        def make_request():
            try:
                response = client.get("/health")
                results.append(response.status_code)
            except RuntimeError as e:  # pylint: disable=broad-exception-caught
                errors.append(str(e))

        # Start multiple threads making concurrent requests
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5)  # 5 second timeout

        # All requests should succeed
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 5
        assert all(status == 200 for status in results)
