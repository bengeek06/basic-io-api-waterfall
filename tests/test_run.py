"""
Test suite for the run module of a Flask application.

This module tests the configuration mapping logic based on the
environment variable `FLASK_ENV` and the main application startup.
"""

import os
from unittest.mock import patch, MagicMock

import pytest
from run import main


@pytest.mark.parametrize(
    "env,expected_config,env_file_exists,expected_debug",
    [
        ("production", "app.config.ProductionConfig", True, False),
        ("staging", "app.config.StagingConfig", False, True),
        ("testing", "app.config.TestingConfig", True, False),
        ("development", "app.config.DevelopmentConfig", True, True),
        ("unknown", "app.config.DevelopmentConfig", False, False),
    ],
)
def test_run_config_mapping(
    env, expected_config, env_file_exists, expected_debug
):
    """
    Test that the run module correctly maps FLASK_ENV to config class and handles .env files.
    """
    # Set environment
    original_env = os.environ.get("FLASK_ENV")
    original_port = os.environ.get("PORT")
    original_docker = os.environ.get("IN_DOCKER_CONTAINER")
    original_app_mode = os.environ.get("APP_MODE")

    os.environ["FLASK_ENV"] = env
    os.environ["PORT"] = "5000"  # Set default port

    # Ensure we're not in Docker for this test
    if original_docker:
        del os.environ["IN_DOCKER_CONTAINER"]
    if original_app_mode:
        del os.environ["APP_MODE"]

    try:
        # Mock all external dependencies
        mock_create_app = MagicMock()
        mock_logger = MagicMock()
        mock_load_dotenv = MagicMock()
        mock_os_path_exists = MagicMock(return_value=env_file_exists)

        # Mock the app instance to prevent actual server startup
        mock_app = MagicMock()
        # Mock app.config.get to return expected debug value
        mock_app.config.get.return_value = expected_debug
        mock_create_app.return_value = mock_app

        with (
            patch("run.create_app", mock_create_app),
            patch("run.logger", mock_logger),
            patch("run.load_dotenv", mock_load_dotenv),
            patch("run.os.path.exists", mock_os_path_exists),
        ):
            # Call main function
            main()

            # Verify create_app was called with correct config
            mock_create_app.assert_called_once_with(expected_config)

            # Verify .env file handling
            expected_env_file = f".env.{env}"
            mock_os_path_exists.assert_called_once_with(expected_env_file)

            if env_file_exists:
                mock_load_dotenv.assert_called_once_with(expected_env_file)
                mock_logger.info.assert_any_call(
                    f"Loaded environment from {expected_env_file}"
                )
            else:
                mock_load_dotenv.assert_not_called()
                mock_logger.warning.assert_any_call(
                    f"Environment file {expected_env_file} not found"
                )

            # Verify app.config.get was called to get DEBUG setting
            mock_app.config.get.assert_called_with("DEBUG", False)

            # Verify app.run was called with debug from app config
            mock_app.run.assert_called_once_with(
                host="0.0.0.0", port=5000, debug=expected_debug
            )

    finally:
        # Restore original environment
        if original_env is not None:
            os.environ["FLASK_ENV"] = original_env
        elif "FLASK_ENV" in os.environ:
            del os.environ["FLASK_ENV"]

        if original_port is not None:
            os.environ["PORT"] = original_port
        elif "PORT" in os.environ:
            del os.environ["PORT"]

        if original_docker is not None:
            os.environ["IN_DOCKER_CONTAINER"] = original_docker

        if original_app_mode is not None:
            os.environ["APP_MODE"] = original_app_mode


def test_main_with_custom_port():
    """
    Test that the main function uses custom PORT environment variable.
    """
    original_env = os.environ.get("FLASK_ENV")
    original_port = os.environ.get("PORT")
    original_docker = os.environ.get("IN_DOCKER_CONTAINER")
    original_app_mode = os.environ.get("APP_MODE")

    os.environ["FLASK_ENV"] = "development"
    os.environ["PORT"] = "8080"

    # Ensure we're not in Docker for this test
    if original_docker:
        del os.environ["IN_DOCKER_CONTAINER"]
    if original_app_mode:
        del os.environ["APP_MODE"]

    try:
        mock_create_app = MagicMock()
        mock_logger = MagicMock()
        mock_load_dotenv = MagicMock()
        mock_os_path_exists = MagicMock(return_value=True)
        mock_app = MagicMock()
        # Mock debug=True for development
        mock_app.config.get.return_value = True
        mock_create_app.return_value = mock_app

        with (
            patch("run.create_app", mock_create_app),
            patch("run.logger", mock_logger),
            patch("run.load_dotenv", mock_load_dotenv),
            patch("run.os.path.exists", mock_os_path_exists),
        ):
            main()

            # Verify app.run was called with custom port and debug from config
            mock_app.run.assert_called_once_with(
                host="0.0.0.0", port=8080, debug=True
            )

    finally:
        # Restore original environment
        if original_env is not None:
            os.environ["FLASK_ENV"] = original_env
        elif "FLASK_ENV" in os.environ:
            del os.environ["FLASK_ENV"]

        if original_port is not None:
            os.environ["PORT"] = original_port
        elif "PORT" in os.environ:
            del os.environ["PORT"]

        if original_docker is not None:
            os.environ["IN_DOCKER_CONTAINER"] = original_docker

        if original_app_mode is not None:
            os.environ["APP_MODE"] = original_app_mode


def test_main_debug_mode_from_app_config():
    """
    Test that debug mode is retrieved from app configuration.
    """
    test_cases = [
        ("production", False),
        ("staging", True),
        ("development", True),
        ("testing", False),
    ]

    for env, expected_debug in test_cases:
        original_env = os.environ.get("FLASK_ENV")
        original_docker = os.environ.get("IN_DOCKER_CONTAINER")
        original_app_mode = os.environ.get("APP_MODE")

        os.environ["FLASK_ENV"] = env

        # Ensure we're not in Docker for this test
        if original_docker:
            del os.environ["IN_DOCKER_CONTAINER"]
        if original_app_mode:
            del os.environ["APP_MODE"]

        try:
            mock_create_app = MagicMock()
            mock_logger = MagicMock()
            mock_load_dotenv = MagicMock()
            mock_os_path_exists = MagicMock(return_value=True)
            mock_app = MagicMock()
            # Mock app.config.get to return expected debug value
            mock_app.config.get.return_value = expected_debug
            mock_create_app.return_value = mock_app

            with (
                patch("run.create_app", mock_create_app),
                patch("run.logger", mock_logger),
                patch("run.load_dotenv", mock_load_dotenv),
                patch("run.os.path.exists", mock_os_path_exists),
            ):
                main()

                # Verify debug mode is retrieved from app config
                mock_app.config.get.assert_called_with("DEBUG", False)
                mock_app.run.assert_called_once_with(
                    host="0.0.0.0", port=5000, debug=expected_debug
                )

        finally:
            # Restore original environment
            if original_env is not None:
                os.environ["FLASK_ENV"] = original_env
            elif "FLASK_ENV" in os.environ:
                del os.environ["FLASK_ENV"]

            if original_docker is not None:
                os.environ["IN_DOCKER_CONTAINER"] = original_docker

            if original_app_mode is not None:
                os.environ["APP_MODE"] = original_app_mode


def test_docker_environment_skips_env_file():
    """
    Test that .env file loading is skipped when running in Docker.
    """
    original_env = os.environ.get("FLASK_ENV")
    original_docker = os.environ.get("IN_DOCKER_CONTAINER")

    os.environ["FLASK_ENV"] = "development"
    os.environ["IN_DOCKER_CONTAINER"] = "true"

    try:
        mock_create_app = MagicMock()
        mock_logger = MagicMock()
        mock_load_dotenv = MagicMock()
        mock_os_path_exists = MagicMock()
        mock_app = MagicMock()
        mock_app.config.get.return_value = True
        mock_create_app.return_value = mock_app

        with (
            patch("run.create_app", mock_create_app),
            patch("run.logger", mock_logger),
            patch("run.load_dotenv", mock_load_dotenv),
            patch("run.os.path.exists", mock_os_path_exists),
        ):
            main()

            # Verify .env file loading was skipped
            mock_os_path_exists.assert_not_called()
            mock_load_dotenv.assert_not_called()
            mock_logger.info.assert_any_call(
                "Running in Docker container, skipping .env file loading"
            )

    finally:
        # Restore original environment
        if original_env is not None:
            os.environ["FLASK_ENV"] = original_env
        elif "FLASK_ENV" in os.environ:
            del os.environ["FLASK_ENV"]

        if original_docker is not None:
            os.environ["IN_DOCKER_CONTAINER"] = original_docker
        elif "IN_DOCKER_CONTAINER" in os.environ:
            del os.environ["IN_DOCKER_CONTAINER"]


def test_app_mode_skips_env_file():
    """
    Test that .env file loading is skipped when APP_MODE is set.
    """
    original_env = os.environ.get("FLASK_ENV")
    original_app_mode = os.environ.get("APP_MODE")

    os.environ["FLASK_ENV"] = "staging"
    os.environ["APP_MODE"] = "staging"

    try:
        mock_create_app = MagicMock()
        mock_logger = MagicMock()
        mock_load_dotenv = MagicMock()
        mock_os_path_exists = MagicMock()
        mock_app = MagicMock()
        mock_app.config.get.return_value = False
        mock_create_app.return_value = mock_app

        with (
            patch("run.create_app", mock_create_app),
            patch("run.logger", mock_logger),
            patch("run.load_dotenv", mock_load_dotenv),
            patch("run.os.path.exists", mock_os_path_exists),
        ):
            main()

            # Verify .env file loading was skipped
            mock_os_path_exists.assert_not_called()
            mock_load_dotenv.assert_not_called()
            mock_logger.info.assert_any_call(
                "Running in Docker container, skipping .env file loading"
            )

    finally:
        # Restore original environment
        if original_env is not None:
            os.environ["FLASK_ENV"] = original_env
        elif "FLASK_ENV" in os.environ:
            del os.environ["FLASK_ENV"]

        if original_app_mode is not None:
            os.environ["APP_MODE"] = original_app_mode
        elif "APP_MODE" in os.environ:
            del os.environ["APP_MODE"]
