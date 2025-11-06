"""
config.py
---------

This module defines configuration classes for the Flask application based on
the environment.

Classes:
    - Config: Base configuration common to all environments.
    - DevelopmentConfig: Configuration for development.
    - TestingConfig: Configuration for testing.
    - StagingConfig: Configuration for staging.
    - ProductionConfig: Configuration for production.

Each class defines main parameters such as the secret key, database URL,
debug mode, and SQLAlchemy modification tracking.
"""

import os
from dotenv import load_dotenv

# Load .env file ONLY if not running in Docker
# This hook ensures environment variables are loaded for flask commands
if not os.environ.get("IN_DOCKER_CONTAINER") and not os.environ.get(
    "APP_MODE"
):
    env = os.environ.get("FLASK_ENV", "development")
    ENV_FILE = f".env.{env}"
    if os.path.exists(ENV_FILE):
        load_dotenv(ENV_FILE)
    # Fallback to generic .env if environment-specific file doesn't exist
    elif os.path.exists(".env"):
        load_dotenv(".env")


class Config:
    """Base configuration common to all environments."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(Config):
    """Configuration for the development environment."""

    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    if not SQLALCHEMY_DATABASE_URI:
        raise ValueError("DATABASE_URL environment variable is not set.")


class TestingConfig(Config):
    """Configuration for the testing environment."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    if not SQLALCHEMY_DATABASE_URI:
        raise ValueError("DATABASE_URL environment variable is not set.")


class StagingConfig(Config):
    """Configuration for the staging environment."""

    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    if not SQLALCHEMY_DATABASE_URI:
        raise ValueError("DATABASE_URL environment variable is not set.")


class ProductionConfig(Config):
    """Configuration for the production environment."""

    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    if not SQLALCHEMY_DATABASE_URI:
        raise ValueError("DATABASE_URL environment variable is not set.")
