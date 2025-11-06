"""
WSGI entry point for production deployment with Gunicorn.

This module forces the production environment and creates the Flask
application instance for deployment with WSGI servers like Gunicorn.
"""

import os

from app import create_app

# Force production environment
os.environ["FLASK_ENV"] = "production"

# Create application instance
app = create_app("app.config.ProductionConfig")

if __name__ == "__main__":
    app.run()
