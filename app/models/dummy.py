"""
models.py
---------

This module defines the SQLAlchemy database models for the application.
"""

from app.models.db import db


class Dummy(db.Model):
    """
    Data model for a Dummy entity.

    Attributes:
        id (int): Unique identifier for the Dummy entity.
        name (str): Name of the Dummy entity.
        description (str): Description of the Dummy entity.
    """

    __tablename__ = "dummy"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return (
            f"<Dummy {self.name}>"
            f" (ID: {self.id}, Description: {self.description})"
        )

    @classmethod
    def get_all(cls):
        """
        Retrieve all records from the Dummy table.

        Returns:
            list: List of all Dummy objects.
        """
        return cls.query.all()

    @classmethod
    def get_by_id(cls, dummy_id):
        """
        Retrieve a Dummy record by its ID.

        Args:
            dummy_id (int): ID of the Dummy entity to retrieve.

        Returns:
            Dummy: The Dummy object with the given ID, or None if not found.
        """
        return db.session.get(cls, dummy_id)

    @classmethod
    def get_by_name(cls, name):
        """
        Retrieve a Dummy record by its name.

        Args:
            name (str): Name of the Dummy entity to retrieve.

        Returns:
            Dummy: The Dummy object with the given name, or None if not found.
        """
        return cls.query.filter_by(name=name).first()

    @classmethod
    def create(cls, name, description=None):
        """
        Create a new Dummy record.

        Args:
            name (str): Name of the Dummy entity.
            description (str, optional): Description of the Dummy entity.

        Returns:
            Dummy: The created Dummy object.
        """
        dummy = cls(name=name, description=description)
        db.session.add(dummy)
        db.session.commit()
        return dummy

    def update(self, name=None, description=None):
        """
        Update the attributes of the Dummy entity.

        Args:
            name (str, optional): New name for the Dummy entity.
            description (str, optional): New description for the Dummy entity.
        """
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
        db.session.commit()

    def delete(self):
        """
        Delete the Dummy record from the database.
        """
        db.session.delete(self)
        db.session.commit()
