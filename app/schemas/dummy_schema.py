"""
schemas.py
----------

This module defines Marshmallow schemas for serializing and validating
the application's data models.

Classes:
    - DummySchema: Schema for serializing and validating Dummy model instances.
"""

from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from marshmallow import ValidationError, validates

from app.models.dummy import Dummy


class DummySchema(SQLAlchemyAutoSchema):
    """
    Serialization and validation schema for the Dummy model.

    Attributes:
        id (int): Unique identifier for the Dummy entity.
        name (str): Name of the Dummy entity.
        description (str): Description of the Dummy entity.
    """

    class Meta:
        """
        Meta options for the Dummy schema.

        Attributes:
            model: The SQLAlchemy model associated with this schema.
            load_instance: Whether to load model instances.
            include_fk: Whether to include foreign keys.
            dump_only: Fields that are only used for serialization.
        """

        model = Dummy
        load_instance = True
        include_fk = True
        dump_only = ("id",)

    @validates("name")
    def validate_name(self, value, **kwargs):
        """
        Validate that the name is not empty and is unique.

        Args:
            value (str): The name to validate.

        Raises:
            ValidationError: If the name is empty or already exists.

        Returns:
            str: The validated name.
        """
        _ = kwargs

        if not value:
            raise ValidationError("Name cannot be empty.")
        dummy = Dummy.get_by_name(value)
        if dummy:
            raise ValidationError("Name must be unique.")
        return value

    @validates("description")
    def validate_description(self, value, **kwargs):
        """
        Validate that the description does not exceed 200 characters.

        Args:
            value (str): The description to validate.

        Raises:
            ValidationError: If the description exceeds 200 characters.

        Returns:
            str: The validated description.
        """
        _ = kwargs
        if value and len(value) > 200:
            raise ValidationError("Description cannot exceed 200 characters.")
        return value
