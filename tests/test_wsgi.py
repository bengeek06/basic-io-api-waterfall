"""
Tests for the WSGI entrypoint.

This module contains tests for the WSGI entrypoint to ensure the correct configuration
class is selected based on the FLASK_ENV environment variable.
"""

import importlib
import sys
import os


def test_wsgi_forces_production_config(monkeypatch):
    """
    Test that the WSGI entrypoint always uses ProductionConfig.

    This test verifies that the WSGI entrypoint always uses ProductionConfig regardless
    of the initial FLASK_ENV environment variable.

    This test patches app.create_app to avoid side effects and verifies
    that wsgi.py forces production environment and uses ProductionConfig.
    """
    # Patch app.create_app BEFORE importing wsgi
    captured = {}

    def fake_create_app(config_class):
        captured["config_class"] = config_class

        class DummyApp:
            """Dummy Flask application for testing."""

            def run(self):
                """Mock run method to prevent actual server startup."""
                return None

        return DummyApp()

    monkeypatch.setattr("app.create_app", fake_create_app)

    # Clean up any existing wsgi module
    if "wsgi" in sys.modules:
        del sys.modules["wsgi"]

    # Set a different environment initially to verify it gets overridden
    original_env = os.environ.get("FLASK_ENV")
    os.environ["FLASK_ENV"] = "development"

    try:
        wsgi = importlib.import_module("wsgi")

        # Verify the wsgi module has the app attribute
        assert hasattr(wsgi, "app")

        # Verify create_app was called with ProductionConfig
        assert "config_class" in captured, "create_app was not called"
        assert captured["config_class"] == "app.config.ProductionConfig"

        # Verify FLASK_ENV was forced to production
        assert os.environ["FLASK_ENV"] == "production"

    finally:
        # Restore original environment
        if original_env is not None:
            os.environ["FLASK_ENV"] = original_env
        elif "FLASK_ENV" in os.environ:
            del os.environ["FLASK_ENV"]
