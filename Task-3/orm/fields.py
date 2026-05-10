"""
orm/fields.py
─────────────
Descriptor-based field definitions for the custom ORM.

Each field class implements the descriptor protocol:
    __set_name__  – called by the metaclass when the field is bound to a model class
    __get__       – returns the stored value (or self when accessed on the class)
    __set__       – validates and stores the value on the instance

SQL DDL helpers (column_def) return the appropriate SQL fragment used by
ModelBase when auto-generating CREATE TABLE statements.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional, Type

if TYPE_CHECKING:
    from .model import Model


# ──────────────────────────────────────────────────────────────────────────────
# Validation helpers
# ──────────────────────────────────────────────────────────────────────────────

class ValidationError(Exception):
    """Raised when a field value fails validation."""


# ──────────────────────────────────────────────────────────────────────────────
# Base Field
# ──────────────────────────────────────────────────────────────────────────────

class Field:
    """
    Base descriptor class for all model fields.

    Attributes
    ----------
    column_name : str
        The name of the column in the database (set via __set_name__).
    nullable : bool
        Whether NULL values are allowed (default False).
    default : Any
        Default value used when no value is provided.
    unique : bool
        Whether to add a UNIQUE constraint.
    primary_key : bool
        Whether this field is the primary key.
    """

    # Counter used to preserve declaration order across all field instances
    _creation_counter: int = 0

    def __init__(
        self,
        nullable: bool = False,
        default: Any = None,
        unique: bool = False,
        primary_key: bool = False,
    ) -> None:
        self.nullable = nullable
        self.default = default
        self.unique = unique
        self.primary_key = primary_key

        # Store declaration order so ModelBase can sort fields predictably
        Field._creation_counter += 1
        self._order = Field._creation_counter

        # Set by __set_name__
        self.column_name: str = ""
        self.attr_name: str = ""        # the Python attribute name on the model

    # ── Descriptor protocol ──────────────────────────────────────────────────

    def __set_name__(self, owner: Type["Model"], name: str) -> None:
        """Called by the metaclass when the descriptor is assigned to a class."""
        self.attr_name = name
        self.column_name = name          # may be overridden by subclasses (e.g. ForeignKey)

    def __get__(self, instance: Optional["Model"], owner: Type["Model"]) -> Any:
        if instance is None:
            # Accessed on the class itself – return the descriptor
            return self
        return instance.__dict__.get(self.attr_name, self.default)

    def __set__(self, instance: "Model", value: Any) -> None:
        if value is None and not self.nullable and not self.primary_key:
            raise ValidationError(
                f"Field '{self.attr_name}' does not allow NULL values."
            )
        validated = self.validate(value)
        instance.__dict__[self.attr_name] = validated

    # ── Validation ───────────────────────────────────────────────────────────

    def validate(self, value: Any) -> Any:
        """Override in subclasses to perform type-specific validation."""
        return value

    # ── SQL helpers ──────────────────────────────────────────────────────────

    def column_def(self) -> str:
        """Return the SQL column definition fragment (without column name)."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement column_def()."
        )

    def _sql_constraints(self) -> str:
        """Build trailing constraint keywords (NOT NULL, UNIQUE, etc.)."""
        parts: list[str] = []
        if not self.nullable and not self.primary_key:
            parts.append("NOT NULL")
        if self.unique:
            parts.append("UNIQUE")
        return (" " + " ".join(parts)) if parts else ""

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"column={self.column_name!r}, nullable={self.nullable})"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Concrete field types
# ──────────────────────────────────────────────────────────────────────────────

class IntegerField(Field):
    """Represents an INTEGER column."""

    def validate(self, value: Any) -> Any:
        if value is None:
            return value
        if not isinstance(value, int):
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise ValidationError(
                    f"Field '{self.attr_name}' expects an integer, got {type(value).__name__!r}."
                )
        return value

    def column_def(self) -> str:
        return f"INTEGER{self._sql_constraints()}"


class FloatField(Field):
    """Represents a REAL (floating-point) column."""

    def validate(self, value: Any) -> Any:
        if value is None:
            return value
        if not isinstance(value, (int, float)):
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise ValidationError(
                    f"Field '{self.attr_name}' expects a float, got {type(value).__name__!r}."
                )
        return float(value)

    def column_def(self) -> str:
        return f"REAL{self._sql_constraints()}"


class CharField(Field):
    """
    Represents a VARCHAR column.

    Parameters
    ----------
    max_length : int
        Maximum allowed string length (also used in column definition).
    """

    def __init__(self, max_length: int = 255, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.max_length = max_length

    def validate(self, value: Any) -> Any:
        if value is None:
            return value
        if not isinstance(value, str):
            value = str(value)
        if len(value) > self.max_length:
            raise ValidationError(
                f"Field '{self.attr_name}' exceeds max_length={self.max_length} "
                f"(got {len(value)} chars)."
            )
        return value

    def column_def(self) -> str:
        return f"VARCHAR({self.max_length}){self._sql_constraints()}"


class TextField(Field):
    """Represents an unbounded TEXT column."""

    def validate(self, value: Any) -> Any:
        if value is None:
            return value
        return str(value)

    def column_def(self) -> str:
        return f"TEXT{self._sql_constraints()}"


class BooleanField(Field):
    """
    Represents a BOOLEAN column (stored as INTEGER 0/1 in SQLite).
    """

    def validate(self, value: Any) -> Any:
        if value is None:
            return value
        return bool(value)

    def column_def(self) -> str:
        return f"INTEGER{self._sql_constraints()}"   # SQLite stores booleans as integers


# ──────────────────────────────────────────────────────────────────────────────
# ForeignKey field
# ──────────────────────────────────────────────────────────────────────────────

class ForeignKey(Field):
    """
    Descriptor that models a many-to-one relationship.

    On assignment you can pass either:
      • an integer (the raw FK id), or
      • a Model instance (the id is extracted automatically).

    Accessing ``instance.<field_name>`` returns the raw FK integer id.
    The convenience accessor ``instance.<field_name>_object`` lazily fetches
    the related model instance from the database (see __get__ override).

    Parameters
    ----------
    to : Type[Model] | str
        The related model class (or its name as a string for forward refs).
    related_name : str | None
        Name of the reverse-accessor added to the related model class.
        e.g. related_name="posts" → ``user.posts`` returns all posts for that user.
    on_delete : str
        Referential action on deletion.  Defaults to "CASCADE".
    """

    def __init__(
        self,
        to: "Type[Model] | str",
        related_name: Optional[str] = None,
        on_delete: str = "CASCADE",
        **kwargs: Any,
    ) -> None:
        # ForeignKey columns are always nullable=False by default but allow override
        super().__init__(**kwargs)
        self.to = to                        # resolved later by the metaclass
        self.related_name = related_name
        self.on_delete = on_delete

    # ── Descriptor ──────────────────────────────────────────────────────────

    def __set_name__(self, owner: "Type[Model]", name: str) -> None:
        self.attr_name = name
        # The physical column in the DB stores the integer id
        self.column_name = f"{name}_id"

    def __get__(self, instance: Optional["Model"], owner: "Type[Model]") -> Any:
        if instance is None:
            return self
        return instance.__dict__.get(self.attr_name)

    def __set__(self, instance: "Model", value: Any) -> None:
        from .model import Model as ModelBase  # local import to avoid circular

        if isinstance(value, ModelBase):
            # Store the integer id
            instance.__dict__[self.attr_name] = value.id
        elif isinstance(value, int) or value is None:
            instance.__dict__[self.attr_name] = value
        else:
            try:
                instance.__dict__[self.attr_name] = int(value)
            except (TypeError, ValueError):
                raise ValidationError(
                    f"ForeignKey '{self.attr_name}' expects a Model instance or integer id."
                )

    # ── SQL helpers ──────────────────────────────────────────────────────────

    def column_def(self) -> str:
        from .model import ModelRegistry  # lazy import

        if isinstance(self.to, str):
            related_table = self.to.lower()
        else:
            related_table = self.to.__name__.lower()

        constraints = self._sql_constraints()
        return (
            f"INTEGER{constraints} REFERENCES {related_table}(id) "
            f"ON DELETE {self.on_delete}"
        )
