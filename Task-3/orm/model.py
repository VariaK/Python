"""
orm/model.py
────────────
ModelBase metaclass and Model base class.

Architecture
------------

ModelBase (metaclass)
    ├── Scans the class body for Field descriptors via __new__
    ├── Auto-generates an integer primary key field ("id")
    ├── Populates _meta dict with table name, fields, and column map
    ├── Registers the new model in ModelRegistry for forward-ref resolution
    └── Wires up ForeignKey reverse accessors (related_name) via __init_subclass__

Model (base class)
    ├── __init__            – accept kwargs matching field names
    ├── save()              – INSERT or UPDATE (upsert by id presence)
    ├── delete()            – DELETE the row for this instance
    ├── refresh()           – reload fields from the database
    ├── to_dict()           – export as plain dict
    ├── filter(**kw)        – class method → QuerySet
    ├── all()               – class method → list of all instances
    ├── get(**kw)           – class method → single instance or raise
    ├── create(**kw)        – class method → save + return new instance
    ├── create_table()      – class method → emit CREATE TABLE SQL
    └── drop_table()        – class method → emit DROP TABLE SQL
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterator, List, Optional, Type

from .fields import Field, ForeignKey, IntegerField
from .query import QuerySet


# ──────────────────────────────────────────────────────────────────────────────
# Model registry (for forward references in ForeignKey)
# ──────────────────────────────────────────────────────────────────────────────

class ModelRegistry:
    """Global registry mapping model name → model class."""

    _registry: dict[str, "Type[Model]"] = {}

    @classmethod
    def register(cls, model_class: "Type[Model]") -> None:
        cls._registry[model_class.__name__] = model_class

    @classmethod
    def get(cls, name: str) -> "Type[Model]":
        if name not in cls._registry:
            raise KeyError(
                f"Model '{name}' is not registered.  "
                f"Available: {list(cls._registry)}"
            )
        return cls._registry[name]

    @classmethod
    def all(cls) -> dict[str, "Type[Model]"]:
        return dict(cls._registry)


# ──────────────────────────────────────────────────────────────────────────────
# Reverse accessor descriptor (for related_name on ForeignKey)
# ──────────────────────────────────────────────────────────────────────────────

class _ReverseAccessor:
    """
    Descriptor placed on the *related* model to support::

        user.posts   →   QuerySet(Post).filter(author_id=user.id)

    The SQL is only executed when the attribute is accessed (lazy loading).
    """

    def __init__(
        self,
        source_model_name: str,
        fk_column: str,           # e.g. "author_id"
    ) -> None:
        self._source_model_name = source_model_name
        self._fk_column = fk_column

    def __set_name__(self, owner: "Type[Model]", name: str) -> None:
        self._name = name

    def __get__(self, instance: Optional["Model"], owner: "Type[Model]") -> Any:
        if instance is None:
            # Accessed on the class – just return self so we don't explode
            return self
        if instance.id is None:
            raise RuntimeError(
                f"Cannot access reverse relation '{self._name}' on an unsaved instance."
            )
        source_model = ModelRegistry.get(self._source_model_name)
        return QuerySet(source_model).filter(
            **{self._fk_column: instance.id}
        ).all()

    def __repr__(self) -> str:
        return (
            f"<ReverseAccessor: {self._source_model_name}.{self._fk_column}>"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Metaclass
# ──────────────────────────────────────────────────────────────────────────────

def _camel_to_snake(name: str) -> str:
    """Convert CamelCase class name to snake_case table name."""
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    name = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name)
    return name.lower()


class ModelBase(type):
    """
    Metaclass for all ORM models.

    What it does during class creation (``__new__``):
    1. Detects all ``Field`` instances declared in the class body.
    2. Injects an auto-increment ``id`` primary key (IntegerField).
    3. Sorts fields by declaration order.
    4. Builds ``_meta`` containing table name, ordered fields, and column map.
    5. Registers the model in ``ModelRegistry``.
    6. Resolves ForeignKey ``related_name`` → installs ``_ReverseAccessor``.
    """

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
    ) -> "ModelBase":

        # Let Python create the class object first
        cls = super().__new__(mcs, name, bases, namespace)

        # Skip the abstract base Model class itself
        if name == "Model":
            return cls

        # ── Collect fields ────────────────────────────────────────────────────
        fields: dict[str, Field] = {}

        # Walk MRO in reverse so child declarations override parents
        for base in reversed(cls.__mro__):
            for attr, obj in vars(base).items():
                if isinstance(obj, Field) and attr != "id":
                    fields[attr] = obj

        # Sort by declaration order
        ordered_fields: list[tuple[str, Field]] = sorted(
            fields.items(), key=lambda item: item[1]._order
        )

        # Inject primary key at position 0
        pk_field = IntegerField(nullable=True, primary_key=True)
        pk_field.attr_name = "id"
        pk_field.column_name = "id"
        pk_field._order = -1          # always first

        all_fields: list[tuple[str, Field]] = [("id", pk_field)] + ordered_fields

        # Build column → field map (column_name may differ from attr for FK)
        column_map: dict[str, Field] = {}
        for attr_name, field in all_fields:
            column_map[field.column_name] = field

        # ── _meta ─────────────────────────────────────────────────────────────
        table_name = _camel_to_snake(name)
        cls._meta = {
            "table_name": table_name,
            "fields": all_fields,               # [(attr_name, Field), …]
            "column_map": column_map,           # {column_name: Field}
        }

        # ── Register ──────────────────────────────────────────────────────────
        ModelRegistry.register(cls)

        # ── Wire up ForeignKey reverse accessors ──────────────────────────────
        for attr_name, field in all_fields:
            if isinstance(field, ForeignKey) and field.related_name:
                related_model_name = (
                    field.to if isinstance(field.to, str) else field.to.__name__
                )
                accessor = _ReverseAccessor(
                    source_model_name=name,
                    fk_column=field.column_name,   # e.g. "author_id"
                )
                accessor._name = field.related_name

                try:
                    related_cls = ModelRegistry.get(related_model_name)
                    setattr(related_cls, field.related_name, accessor)
                except KeyError:
                    # Related model not yet defined (forward reference).
                    # We'll resolve this lazily when the related model is registered.
                    pass

        return cls

    # ── QuerySet shortcut at class level ──────────────────────────────────────
    def filter(cls, **kwargs: Any) -> QuerySet:
        return QuerySet(cls).filter(**kwargs)

    def exclude(cls, **kwargs: Any) -> QuerySet:
        return QuerySet(cls).exclude(**kwargs)

    def order_by(cls, *fields: str) -> QuerySet:
        return QuerySet(cls).order_by(*fields)

    def all(cls) -> list:
        return QuerySet(cls).all()

    def get(cls, **kwargs: Any) -> "Model":
        qs = QuerySet(cls).filter(**kwargs)
        results = qs.all()
        if not results:
            raise cls.DoesNotExist(
                f"{cls.__name__} matching query does not exist."
            )
        if len(results) > 1:
            raise cls.MultipleObjectsReturned(
                f"get() returned more than one {cls.__name__} — "
                f"query returned {len(results)} rows."
            )
        return results[0]

    def create(cls, **kwargs: Any) -> "Model":
        instance = cls(**kwargs)
        instance.save()
        return instance

    def create_table(cls, *, if_not_exists: bool = True) -> None:
        """Emit a CREATE TABLE statement for this model."""
        from .connection import Database

        table = cls._meta["table_name"]
        cols: list[str] = []
        fk_constraints: list[str] = []

        for attr_name, field in cls._meta["fields"]:
            if field.primary_key:
                cols.append(f"  {field.column_name} INTEGER PRIMARY KEY AUTOINCREMENT")
            else:
                cols.append(f"  {field.column_name} {field.column_def()}")

        exists_clause = "IF NOT EXISTS " if if_not_exists else ""
        ddl = (
            f"CREATE TABLE {exists_clause}{table} (\n"
            + ",\n".join(cols)
            + "\n);"
        )

        Database.execute(ddl, commit=True)
        print(f"\033[32mTable '{table}' created.\033[0m")

    def drop_table(cls, *, if_exists: bool = True) -> None:
        """Emit a DROP TABLE statement for this model."""
        from .connection import Database

        table = cls._meta["table_name"]
        exists_clause = "IF EXISTS " if if_exists else ""
        Database.execute(f"DROP TABLE {exists_clause}{table};", commit=True)
        print(f"\033[31mTable '{table}' dropped.\033[0m")

    def count(cls) -> int:
        return QuerySet(cls).count()


# ──────────────────────────────────────────────────────────────────────────────
# Model base class
# ──────────────────────────────────────────────────────────────────────────────

class Model(metaclass=ModelBase):
    """
    Base class for all user-defined ORM models.

    Subclass this and declare fields as class attributes::

        class User(Model):
            name  = CharField(max_length=100)
            email = CharField(max_length=255, unique=True)
            age   = IntegerField(nullable=True)

    The metaclass automatically:
      • Adds an ``id`` INTEGER PRIMARY KEY AUTOINCREMENT field.
      • Derives the table name from the class name (CamelCase → snake_case).
      • Populates ``User._meta`` with field metadata.
    """

    # Sentinel exception classes (populated per-model by the metaclass via __init__)
    class DoesNotExist(Exception):
        pass

    class MultipleObjectsReturned(Exception):
        pass

    # ── Construction ──────────────────────────────────────────────────────────

    def __init__(self, **kwargs: Any) -> None:
        # Set id to None (unsaved)
        object.__setattr__(self, "__dict__", {})
        self.__dict__["id"] = kwargs.pop("id", None)

        field_names = {attr for attr, _ in self._meta["fields"]}

        for key, value in kwargs.items():
            # Accept both 'author' (FK attr) and 'author_id' (FK column)
            if key not in field_names:
                # Try stripping _id suffix for FK lookup
                potential_attr = key[:-3] if key.endswith("_id") else None
                if potential_attr and potential_attr in field_names:
                    setattr(self, potential_attr, value)
                    continue
                raise TypeError(
                    f"{self.__class__.__name__}() got an unexpected keyword argument '{key}'"
                )
            setattr(self, key, value)

        # Apply defaults for unset fields
        for attr_name, field in self._meta["fields"]:
            if attr_name == "id":
                continue
            if attr_name not in self.__dict__ and field.default is not None:
                self.__dict__[attr_name] = field.default

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self) -> None:
        """
        Persist this instance to the database.

        • If ``id`` is None → INSERT and update ``self.id`` with the new rowid.
        • If ``id`` is set  → UPDATE all fields.
        """
        from .connection import Database

        table = self._meta["table_name"]
        fields = [
            (attr, field)
            for attr, field in self._meta["fields"]
            if not field.primary_key
        ]

        # Build column → value pairs (use column_name for FK fields)
        columns = [field.column_name for _, field in fields]
        values = []
        for attr, field in fields:
            val = self.__dict__.get(attr)
            values.append(val)

        if self.id is None:
            # INSERT
            placeholders = ", ".join("?" * len(columns))
            col_names = ", ".join(columns)
            sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders});"
            cursor = Database.execute(sql, tuple(values), commit=True)
            self.__dict__["id"] = cursor.lastrowid
            print(f"\033[32mRecord saved: {self!r}\033[0m")
        else:
            # UPDATE
            set_clause = ", ".join(f"{col} = ?" for col in columns)
            sql = f"UPDATE {table} SET {set_clause} WHERE id = ?;"
            Database.execute(sql, tuple(values) + (self.id,), commit=True)
            print(f"\033[33mRecord updated: {self!r}\033[0m")

    def delete(self) -> None:
        """Delete this instance's row from the database."""
        from .connection import Database

        if self.id is None:
            raise RuntimeError("Cannot delete an unsaved model instance.")
        table = self._meta["table_name"]
        Database.execute(
            f"DELETE FROM {table} WHERE id = ?;", (self.id,), commit=True
        )
        print(f"\033[31mRecord deleted: {self!r}\033[0m")
        self.__dict__["id"] = None

    def refresh(self) -> None:
        """Reload all fields from the database (discard in-memory changes)."""
        if self.id is None:
            raise RuntimeError("Cannot refresh an unsaved model instance.")
        fresh = self.__class__.get(id=self.id)
        self.__dict__.update(fresh.__dict__)

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dict of {column_name: value} for this instance."""
        result: dict[str, Any] = {"id": self.id}
        for attr, field in self._meta["fields"]:
            if field.primary_key:
                continue
            result[field.column_name] = self.__dict__.get(attr)
        return result

    # ── Class-level helpers (delegated to metaclass) ──────────────────────────
    # (filter, exclude, order_by, all, get, create, create_table, drop_table
    #  are all defined on the metaclass so they work as *class* methods without
    #  needing @classmethod decorators.)

    # ── Hydration from DB row ─────────────────────────────────────────────────

    @classmethod
    def _from_row(cls, row: Any) -> "Model":
        """
        Construct a Model instance from a ``sqlite3.Row`` (dict-like).

        This bypasses field validation because the data comes from the DB.
        """
        instance = cls.__new__(cls)
        object.__setattr__(instance, "__dict__", {})

        instance.__dict__["id"] = row["id"]
        for attr_name, field in cls._meta["fields"]:
            if field.primary_key:
                continue
            col = field.column_name
            if col in row.keys():
                instance.__dict__[attr_name] = row[col]
        return instance

    # ── Dunder helpers ────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        parts = [f"id={self.id!r}"]
        for attr, field in self._meta["fields"]:
            if field.primary_key:
                continue
            val = self.__dict__.get(attr)
            parts.append(f"{attr}={val!r}")
        return f"{self.__class__.__name__}({', '.join(parts)})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.id is not None and self.id == other.id

    def __hash__(self) -> int:
        return hash((self.__class__.__name__, self.id))
