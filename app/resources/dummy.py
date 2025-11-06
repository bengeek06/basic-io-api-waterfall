"""
resources.py
-----------
This module defines the resources for managing dummy items in the application.
It includes endpoints for creating, retrieving, updating, and deleting dummy.
"""

from flask import request
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from flask_restful import Resource

from app.models.db import db
from app.models.dummy import Dummy
from app.schemas.dummy_schema import DummySchema
from app.logger import logger
from app.utils import require_jwt_auth, check_access_required

dummy_schema = DummySchema(session=db.session)
dummy_schemas = DummySchema(session=db.session, many=True)


class DummyListResource(Resource):
    """
    Resource for managing the collection of dummy items.

    Methods:
        get():
            Retrieve all dummy items from the database.

        post():
            Create a new dummy item with the provided data.
    """

    @require_jwt_auth()
    @check_access_required("list")
    def get(self):
        """
        Retrieve all dummy items.

        Returns:
            tuple: A tuple containing a list of serialized dummy items and the
            HTTP status code 200.
        """
        logger.info("Retrieving all dummy items")

        dummy = Dummy.get_all()
        return dummy_schemas.dump(dummy), 200

    @require_jwt_auth()
    @check_access_required("create")
    def post(self):
        """
        Create a new dummy item.

        Expects:
            JSON payload with at least the 'name' field.

        Returns:
            tuple: The serialized created dummy item and HTTP status code 201
                   on success.
            tuple: Error message and HTTP status code 400 or 500 on failure.
        """
        logger.info("Creating a new dummy item")

        json_data = request.get_json()
        try:
            dummy_schema.load(json_data)
        except ValidationError as err:
            logger.error("Validation error: %s", err.messages)
            return {"message": "Validation error", "errors": err.messages}, 400

        try:
            dummy = Dummy.create(
                name=json_data["name"],
                description=json_data.get("description"),
            )
        except IntegrityError as e:
            db.session.rollback()
            logger.error("Integrity error: %s", str(e))
            return {"message": "Integrity error", "error": str(e)}, 400
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error("Database error: %s", str(e))
            return {"message": "Database error", "error": str(e)}, 500

        return dummy_schema.dump(dummy), 201


class DummyResource(Resource):
    """
    Resource for managing a single dummy item by its ID.

    Methods:
        get(dummy_id):
            Retrieve a dummy item by its ID.

        put(dummy_id):
            Update a dummy item by replacing all fields.

        patch(dummy_id):
            Partially update a dummy item.

        delete(dummy_id):
            Delete a dummy item by its ID.
    """

    @require_jwt_auth()
    @check_access_required("read")
    def get(self, dummy_id):
        """
        Retrieve a dummy item by its ID.

        Args:
            dummy_id (int): The ID of the dummy item to retrieve.

        Returns:
            tuple: The serialized dummy item and HTTP status code 200 if found.
            tuple: Error message and HTTP status code 404 if not found.
        """
        logger.info("Retrieving dummy with ID: %s", dummy_id)

        dummy = Dummy.get_by_id(dummy_id)
        if not dummy:
            logger.warning("Dummy with ID %s not found", dummy_id)
            return {"message": "Dummy not found"}, 404

        return dummy_schema.dump(dummy), 200

    @require_jwt_auth()
    @check_access_required("update")
    def put(self, dummy_id):
        """
        Update a dummy item by replacing all fields.

        Args:
            dummy_id (int): The ID of the dummy item to update.

        Expects:
            JSON payload with the new 'name' and optionally 'description'.

        Returns:
            tuple: The serialized updated dummy item and HTTP status code 200
                   on success.
            tuple: Error message and HTTP status code 400, 404, or 500 on
                   failure.
        """
        logger.info("Updating dummy with ID: %s", dummy_id)

        json_data = request.get_json()
        try:
            dummy_schema.load(json_data)
        except ValidationError as err:
            logger.error("Validation error: %s", err.messages)
            return {"message": "Validation error", "errors": err.messages}, 400

        dummy = Dummy.get_by_id(dummy_id)
        if not dummy:
            logger.warning("Dummy with ID %s not found", dummy_id)
            return {"message": "Dummy not found"}, 404

        try:
            dummy.update(
                name=json_data["name"],
                description=json_data.get("description"),
            )
        except IntegrityError as e:
            db.session.rollback()
            logger.error("Integrity error: %s", str(e))
            return {"message": "Integrity error", "error": str(e)}, 400
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error("Database error: %s", str(e))
            return {"message": "Database error", "error": str(e)}, 500

        return dummy_schema.dump(dummy), 200

    @require_jwt_auth()
    @check_access_required("update")
    def patch(self, dummy_id):
        """
        Partially update a dummy item.

        Args:
            dummy_id (int): The ID of the dummy item to update.

        Expects:
            JSON payload with fields to update
            (e.g., 'name' and/or 'description').

        Returns:
            tuple: The serialized updated dummy item and HTTP status code 200
                   on success.
            tuple: Error message and HTTP status code 400, 404, or 500 on
                   failure.
        """
        logger.info("Partially updating dummy with ID: %s", dummy_id)

        json_data = request.get_json()
        try:
            dummy_schema.load(json_data, partial=True)
        except ValidationError as err:
            logger.error("Validation error: %s", err.messages)
            return {"message": "Validation error", "errors": err.messages}, 400

        dummy = Dummy.get_by_id(dummy_id)
        if not dummy:
            logger.warning("Dummy item with ID %s not found", dummy_id)
            return {"message": "Dummy item not found"}, 404

        update_kwargs = {}
        if "name" in json_data:
            update_kwargs["name"] = json_data["name"]
        if "description" in json_data:
            update_kwargs["description"] = json_data.get("description")
        try:
            dummy.update(**update_kwargs)
        except IntegrityError as e:
            db.session.rollback()
            logger.error("Integrity error: %s", str(e))
            return {"message": "Integrity error", "error": str(e)}, 400
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error("Database error: %s", str(e))
            return {"message": "Database error", "error": str(e)}, 500

        return dummy_schema.dump(dummy), 200

    @require_jwt_auth()
    @check_access_required("delete")
    def delete(self, dummy_id):
        """
        Delete a dummy item by its ID.

        Args:
            dummy_id (int): The ID of the dummy item to delete.

        Returns:
            tuple: Success message and HTTP status code 204 if deleted.
            tuple: Error message and HTTP status code 404 or 500 on failure.
        """
        logger.info("Deleting dummy with ID: %s", dummy_id)

        dummy = Dummy.get_by_id(dummy_id)
        if not dummy:
            logger.warning("Dummy with ID %s not found", dummy_id)
            return {"message": "Dummy not found"}, 404

        try:
            dummy.delete()
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error("Database error: %s", str(e))
            return {"message": "Database error", "error": str(e)}, 500

        return {"message": "Dummy deleted successfully"}, 204
