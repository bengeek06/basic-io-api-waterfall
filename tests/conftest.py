"""
# conftest.py
# -----------
"""

import os
from pytest import fixture
from dotenv import load_dotenv
import jwt
from app import create_app
from app.models.db import db

os.environ["FLASK_ENV"] = "testing"
load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env.test")
)


@fixture
def app():
    """
    Fixture to create and configure a Flask application for testing.
    This fixture sets up the application context, initializes the database,
    and ensures that the database is created before tests run and dropped after tests complete.
    """
    app = create_app("app.config.TestingConfig")
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@fixture
def client(app):
    """
    Fixture to create a test client for the Flask application.
    This client can be used to simulate HTTP requests to the application.
    """
    return app.test_client()


@fixture
def session(app):
    """
    Fixture to provide a database session for tests.
    This session is scoped to the application context and can be used
    to interact with the database during tests.
    """
    with app.app_context():
        yield db.session


def get_init_db_payload():
    """
    Generate a valid payload for full database initialization via /init-db.
    Returns a dictionary containing data for company, organization_unit, position, and user.
    """
    return {
        "company": {"name": "TestCorp", "description": "A test company"},
        "organization_unit": {
            "name": "Direction",
            "description": "Direction générale",
        },
        "position": {"title": "CEO", "description": "Chief Executive Officer"},
        "user": {
            "email": "admin@testcorp.com",
            "first_name": "Alice",
            "last_name": "Admin",
            "password": "supersecret",
        },
    }


def create_jwt_token(company_id, user_id):
    """Helper function to create a JWT token for testing."""
    jwt_secret = os.environ.get("JWT_SECRET", "test_secret")
    payload = {"company_id": company_id, "user_id": user_id}
    return jwt.encode(payload, jwt_secret, algorithm="HS256")
