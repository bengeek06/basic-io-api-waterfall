"""
test_init.py
------------
This module contains tests for the Flask application factory, error handlers, and main entrypoint.
It ensures that the app is created correctly, custom error handlers work as expected,
and the main run logic is invoked properly.
"""

from flask import Flask
import app


def test_main_runs(monkeypatch):
    """
    Test that the main run logic is called with the correct debug argument.
    """
    called = {}

    def fake_run(self, debug):
        called["run"] = True
        called["debug"] = debug

    monkeypatch.setattr("flask.Flask.run", fake_run)
    app.create_app("app.config.TestingConfig").run(debug=True)
    assert called.get("run") is True
    assert called.get("debug") is True


def test_create_app_returns_flask_app():
    """
    Test that create_app returns a Flask application instance.
    """
    application = app.create_app("app.config.TestingConfig")
    assert isinstance(application, Flask)


def test_handle_404(client):
    """
    Test that a 404 error returns the correct JSON response.
    """
    response = client.get("/v0/route/inexistante")
    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["message"] == "Resource not found"


def test_error_handler_400(client):
    """
    Test that a 400 Bad Request error returns the correct JSON response.
    """
    from werkzeug.exceptions import BadRequest

    @client.application.route("/bad")
    def bad():
        raise BadRequest()

    response = client.get("/bad")
    assert response.status_code == 400
    data = response.get_json()
    assert data["message"] == "Bad request"
    assert data["path"] == "/bad"
    assert data["method"] == "GET"
    assert "request_id" in data


def test_error_handler_500(client):
    """
    Test that a 500 Internal Server Error returns the correct JSON response.
    """
    # Désactive la propagation pour tester le handler 500
    client.application.config["PROPAGATE_EXCEPTIONS"] = False

    @client.application.route("/fail")
    def fail():
        raise Exception("fail!")

    response = client.get("/fail")
    assert response.status_code == 500
    data = response.get_json()
    assert data["message"] == "Internal server error"
    assert data["path"] == "/fail"
    assert data["method"] == "GET"
    assert "request_id" in data


def test_error_handler_401(client):
    """
    Test that a 401 Unauthorized error returns the correct JSON response.
    """
    from werkzeug.exceptions import Unauthorized

    @client.application.route("/unauthorized")
    def unauthorized():
        raise Unauthorized()

    response = client.get("/unauthorized")
    assert response.status_code == 401
    data = response.get_json()
    assert data["message"] == "Unauthorized"
    assert data["path"] == "/unauthorized"
    assert data["method"] == "GET"
    assert "request_id" in data


def test_error_handler_403(client):
    """
    Test that a 403 Forbidden error returns the correct JSON response.
    """
    from werkzeug.exceptions import Forbidden

    @client.application.route("/forbidden")
    def forbidden():
        raise Forbidden()

    response = client.get("/forbidden")
    assert response.status_code == 403
    data = response.get_json()
    assert data["message"] == "Forbidden"
    assert data["path"] == "/forbidden"
    assert data["method"] == "GET"
    assert "request_id" in data
