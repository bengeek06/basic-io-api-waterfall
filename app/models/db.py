"""
app.models.db
-------------

This module initializes the SQLAlchemy instance (db) for the
PM Guardian API. The db object is used throughout the application
for ORM operations and database management.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
