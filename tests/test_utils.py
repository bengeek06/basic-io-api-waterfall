"""
Tests for utility functions in app.utils module.
"""

from unittest import mock

import requests

from app.utils import check_access


class TestCheckAccess:
    """Test cases for check_access function."""

    def test_check_access_testing_environment(self):
        """Test that check_access returns True in testing environment."""
        with mock.patch.dict("os.environ", {"FLASK_ENV": "testing"}):
            access_granted, reason, status = check_access(
                "user123", "user", "list"
            )
            assert access_granted is True
            assert "testing" in reason.lower()
            assert status == 200

    def test_check_access_development_environment(self):
        """Test that check_access returns True in development environment."""
        with mock.patch.dict("os.environ", {"FLASK_ENV": "development"}):
            access_granted, reason, status = check_access(
                "user123", "user", "list"
            )
            assert access_granted is True
            assert "development" in reason.lower()
            assert status == 200

    def test_check_access_missing_guardian_url(self):
        """Test that check_access handles missing GUARDIAN_SERVICE_URL."""
        with mock.patch.dict(
            "os.environ", {"FLASK_ENV": "production"}, clear=True
        ):
            access_granted, reason, status = check_access(
                "user123", "user", "list"
            )
            assert access_granted is False
            assert "internal server error" in reason.lower()
            assert status == 500

    def test_check_access_guardian_success_200(self):
        """Test successful access check with Guardian service returning 200."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_granted": True,
            "reason": "User has permission",
            "status": 200,
        }

        with mock.patch(
            "requests.post", return_value=mock_response
        ) as mock_post:
            with mock.patch.dict(
                "os.environ",
                {
                    "FLASK_ENV": "production",
                    "GUARDIAN_SERVICE_URL": "http://guardian:5000",
                },
            ):
                access_granted, reason, status = check_access(
                    "user123", "user", "list"
                )

                assert access_granted is True
                assert reason == "User has permission"
                assert status == 200

                # Verify the correct API call was made
                mock_post.assert_called_once_with(
                    "http://guardian:5000/check-access",
                    json={
                        "user_id": "user123",
                        "service": "identity",
                        "resource_name": "user",
                        "operation": "list",
                    },
                    headers={},
                    timeout=5.0,
                )

    def test_check_access_guardian_denied_200(self):
        """Test access denied with Guardian service returning 200."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_granted": False,
            "reason": "Insufficient permissions",
            "status": 403,
        }

        with mock.patch("requests.post", return_value=mock_response):
            with mock.patch.dict(
                "os.environ",
                {
                    "FLASK_ENV": "production",
                    "GUARDIAN_SERVICE_URL": "http://guardian:5000",
                },
            ):
                access_granted, reason, status = check_access(
                    "user123", "user", "list"
                )

                assert access_granted is False
                assert reason == "Insufficient permissions"
                assert status == 403

    def test_check_access_guardian_400_with_json(self):
        """Test Guardian service returning 400 with JSON error message."""
        mock_response = mock.Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "access_granted": False,
            "reason": "Invalid user_id format",
        }

        with mock.patch("requests.post", return_value=mock_response):
            with mock.patch.dict(
                "os.environ",
                {
                    "FLASK_ENV": "production",
                    "GUARDIAN_SERVICE_URL": "http://guardian:5000",
                },
            ):
                access_granted, reason, status = check_access(
                    "invalid-user", "user", "list"
                )

                assert access_granted is False
                assert reason == "Invalid user_id format"
                assert status == 400

    def test_check_access_guardian_400_without_json(self):
        """Test Guardian service returning 400 without JSON response."""
        mock_response = mock.Mock()
        mock_response.status_code = 400
        mock_response.json.side_effect = ValueError(
            "No JSON object could be decoded"
        )
        mock_response.text = "Bad Request: Invalid parameters"

        with mock.patch("requests.post", return_value=mock_response):
            with mock.patch.dict(
                "os.environ",
                {
                    "FLASK_ENV": "production",
                    "GUARDIAN_SERVICE_URL": "http://guardian:5000",
                },
            ):
                access_granted, reason, status = check_access(
                    "user123", "user", "list"
                )

                assert access_granted is False
                assert (
                    "Guardian service error: Bad Request: Invalid parameters"
                    in reason
                )
                assert status == 400

    def test_check_access_guardian_500(self):
        """Test Guardian service returning 500."""
        mock_response = mock.Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with mock.patch("requests.post", return_value=mock_response):
            with mock.patch.dict(
                "os.environ",
                {
                    "FLASK_ENV": "production",
                    "GUARDIAN_SERVICE_URL": "http://guardian:5000",
                },
            ):
                access_granted, reason, status = check_access(
                    "user123", "user", "list"
                )

                assert access_granted is False
                assert "Guardian service error (status 500)" in reason
                assert status == 500

    def test_check_access_guardian_timeout(self):
        """Test Guardian service timeout."""
        with mock.patch(
            "requests.post", side_effect=requests.exceptions.Timeout
        ):
            with mock.patch.dict(
                "os.environ",
                {
                    "FLASK_ENV": "production",
                    "GUARDIAN_SERVICE_URL": "http://guardian:5000",
                },
            ):
                access_granted, reason, status = check_access(
                    "user123", "user", "list"
                )

                assert access_granted is False
                assert "timeout" in reason.lower()
                assert status == 504

    def test_check_access_guardian_connection_error(self):
        """Test Guardian service connection error."""
        with mock.patch(
            "requests.post", side_effect=requests.exceptions.ConnectionError
        ):
            with mock.patch.dict(
                "os.environ",
                {
                    "FLASK_ENV": "production",
                    "GUARDIAN_SERVICE_URL": "http://guardian:5000",
                },
            ):
                access_granted, reason, status = check_access(
                    "user123", "user", "list"
                )

                assert access_granted is False
                assert "internal server error" in reason.lower()
                assert status == 500

    def test_check_access_custom_timeout(self):
        """Test that custom timeout is used when set."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_granted": True,
            "reason": "Success",
            "status": 200,
        }

        with mock.patch(
            "requests.post", return_value=mock_response
        ) as mock_post:
            with mock.patch.dict(
                "os.environ",
                {
                    "FLASK_ENV": "production",
                    "GUARDIAN_SERVICE_URL": "http://guardian:5000",
                    "GUARDIAN_SERVICE_TIMEOUT": "10",
                },
            ):
                check_access("user123", "user", "list")

                # Verify custom timeout was used
                mock_post.assert_called_once_with(
                    "http://guardian:5000/check-access",
                    json={
                        "user_id": "user123",
                        "service": "identity",
                        "resource_name": "user",
                        "operation": "list",
                    },
                    headers={},
                    timeout=10.0,
                )

    def test_check_access_forwards_jwt_cookie(self):
        """Test that check_access forwards JWT cookie to Guardian service."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_granted": True,
            "reason": "Success",
            "status": 200,
        }

        # Mock Flask request context with JWT cookie
        from flask import Flask

        app = Flask(__name__)

        with app.test_request_context(
            "/", headers={"Cookie": "access_token=test-jwt-token"}
        ):
            with mock.patch(
                "requests.post", return_value=mock_response
            ) as mock_post:
                with mock.patch.dict(
                    "os.environ",
                    {
                        "FLASK_ENV": "production",
                        "GUARDIAN_SERVICE_URL": "http://guardian:5000",
                    },
                ):
                    check_access("user123", "user", "list")

                    # Verify the JWT cookie was forwarded in headers
                    mock_post.assert_called_once_with(
                        "http://guardian:5000/check-access",
                        json={
                            "user_id": "user123",
                            "service": "identity",
                            "resource_name": "user",
                            "operation": "list",
                        },
                        headers={"Cookie": "access_token=test-jwt-token"},
                        timeout=5.0,
                    )

    def test_check_access_without_jwt_cookie(self):
        """Test that check_access works without JWT cookie (no headers added)."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_granted": True,
            "reason": "Success",
            "status": 200,
        }

        # Mock Flask request context without JWT cookie
        from flask import Flask

        app = Flask(__name__)

        with app.test_request_context("/"):
            with mock.patch(
                "requests.post", return_value=mock_response
            ) as mock_post:
                with mock.patch.dict(
                    "os.environ",
                    {
                        "FLASK_ENV": "production",
                        "GUARDIAN_SERVICE_URL": "http://guardian:5000",
                    },
                ):
                    check_access("user123", "user", "list")

                    # Verify no Cookie header was added when JWT token is missing
                    mock_post.assert_called_once_with(
                        "http://guardian:5000/check-access",
                        json={
                            "user_id": "user123",
                            "service": "identity",
                            "resource_name": "user",
                            "operation": "list",
                        },
                        headers={},
                        timeout=5.0,
                    )
