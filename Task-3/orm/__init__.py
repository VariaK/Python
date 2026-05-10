"""
orm/__init__.py
───────────────
Public surface of the custom ORM package.

Users only need to import from here:

    from orm import Model, CharField, IntegerField, FloatField
    from orm import BooleanField, TextField, ForeignKey
    from orm import Database, ValidationError
"""

from .connection import Database
from .fields import (
    BooleanField,
    CharField,
    Field,
    FloatField,
    ForeignKey,
    IntegerField,
    TextField,
    ValidationError,
)
from .model import Model, ModelRegistry
from .query import QuerySet

__all__ = [
    # Connection
    "Database",
    # Fields
    "Field",
    "IntegerField",
    "FloatField",
    "CharField",
    "TextField",
    "BooleanField",
    "ForeignKey",
    # Validation
    "ValidationError",
    # Model
    "Model",
    "ModelRegistry",
    # Query
    "QuerySet",
]
