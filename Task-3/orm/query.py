"""
orm/query.py
────────────
Lazy QuerySet – supports filter, exclude, order_by, limit, offset, and all().

All methods return *self* (a new QuerySet clone) to enable method chaining:

    User.filter(age__gte=25).order_by("-name").limit(10).all()

Lookup suffixes
---------------
    __eq   (default) – equality:            col = ?
    __ne               not-equal:           col != ?
    __lt               less-than:           col < ?
    __lte              less-or-equal:       col <= ?
    __gt               greater-than:        col > ?
    __gte              greater-or-equal:    col >= ?
    __like             LIKE:                col LIKE ?
    __ilike            case-insensitive:    LOWER(col) LIKE LOWER(?)
    __in               IN (...):            col IN (?,?,?)
    __isnull           IS NULL / IS NOT NULL
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Generic, Iterator, List, Optional, Type, TypeVar

if TYPE_CHECKING:
    from .model import Model

M = TypeVar("M", bound="Model")

# Map of ORM lookup suffix → SQL operator template
_LOOKUP_MAP: dict[str, str] = {
    "eq":     "= ?",
    "ne":     "!= ?",
    "lt":     "< ?",
    "lte":    "<= ?",
    "gt":     "> ?",
    "gte":    ">= ?",
    "like":   "LIKE ?",
    "ilike":  "LIKE ?",          # handled specially below
    "in":     "IN",              # handled specially below
    "isnull": "IS NULL",         # handled specially below
}


def _parse_lookup(key: str, value: Any) -> tuple[str, list[Any]]:
    """
    Parse a single filter keyword into an SQL fragment + bound parameters.

    Parameters
    ----------
    key : str
        Filter keyword, e.g. ``"age__gte"`` or ``"name"``.
    value : Any
        The filter value.

    Returns
    -------
    tuple[str, list[Any]]
        (sql_fragment, params)
    """
    parts = key.rsplit("__", 1)
    if len(parts) == 1:
        column, lookup = parts[0], "eq"
    else:
        column, lookup = parts

    if lookup not in _LOOKUP_MAP:
        # Treat unknown suffix as part of the column name with equality
        column = key
        lookup = "eq"

    if lookup == "isnull":
        if value:
            return f"{column} IS NULL", []
        else:
            return f"{column} IS NOT NULL", []

    if lookup == "in":
        if not value:
            return "1 = 0", []          # empty IN → always false
        placeholders = ", ".join("?" * len(value))
        return f"{column} IN ({placeholders})", list(value)

    if lookup == "ilike":
        return f"LOWER({column}) LIKE LOWER(?)", [str(value)]

    operator = _LOOKUP_MAP[lookup]
    return f"{column} {operator}", [value]


class QuerySet(Generic[M]):
    """
    Lazy, chainable query builder.

    Queries are not executed until you call one of the *terminal* methods:
      • ``.all()``    – return a list of model instances
      • ``.first()``  – return the first result or None
      • ``.last()``   – return the last result or None
      • ``.count()``  – return the count of matching rows
      • ``.exists()`` – return True if any row matches
      • ``.__iter__`` – iterating also triggers evaluation

    All other methods return a *cloned* QuerySet so the original is unchanged.
    """

    def __init__(self, model_class: Type[M]) -> None:
        self._model = model_class
        self._filters: list[tuple[str, list[Any]]] = []   # [(fragment, params), …]
        self._excludes: list[tuple[str, list[Any]]] = []  # excluded conditions
        self._order_by_cols: list[str] = []
        self._limit_val: Optional[int] = None
        self._offset_val: Optional[int] = None
        self._evaluated: Optional[list[M]] = None         # cache after evaluation

    # ── Cloning ──────────────────────────────────────────────────────────────

    def _clone(self) -> "QuerySet[M]":
        clone = QuerySet(self._model)
        clone._filters = list(self._filters)
        clone._excludes = list(self._excludes)
        clone._order_by_cols = list(self._order_by_cols)
        clone._limit_val = self._limit_val
        clone._offset_val = self._offset_val
        # Never carry over the evaluated cache to the clone
        return clone

    # ── Filter API ───────────────────────────────────────────────────────────

    def filter(self, **kwargs: Any) -> "QuerySet[M]":
        """Narrow results to rows matching all supplied keyword arguments."""
        clone = self._clone()
        for key, value in kwargs.items():
            fragment, params = _parse_lookup(key, value)
            clone._filters.append((fragment, params))
        return clone

    def exclude(self, **kwargs: Any) -> "QuerySet[M]":
        """Exclude rows matching the supplied keyword arguments (NOT …)."""
        clone = self._clone()
        for key, value in kwargs.items():
            fragment, params = _parse_lookup(key, value)
            clone._excludes.append((fragment, params))
        return clone

    def order_by(self, *fields: str) -> "QuerySet[M]":
        """
        Set the ORDER BY clause.

        Prefix a field name with ``-`` for descending order:
            ``.order_by("-name", "age")``  →  ``ORDER BY name DESC, age ASC``
        """
        clone = self._clone()
        cols: list[str] = []
        for field in fields:
            if field.startswith("-"):
                cols.append(f"{field[1:]} DESC")
            else:
                cols.append(f"{field} ASC")
        clone._order_by_cols = cols
        return clone

    def limit(self, n: int) -> "QuerySet[M]":
        """Limit the number of rows returned."""
        clone = self._clone()
        clone._limit_val = n
        return clone

    def offset(self, n: int) -> "QuerySet[M]":
        """Skip the first *n* rows."""
        clone = self._clone()
        clone._offset_val = n
        return clone

    # ── SQL construction ─────────────────────────────────────────────────────

    def _build_sql(self) -> tuple[str, list[Any]]:
        """Build the SELECT SQL string and the flat list of bound parameters."""
        table = self._model._meta["table_name"]
        sql = f"SELECT * FROM {table}"
        params: list[Any] = []

        where_parts: list[str] = []

        # Positive filters
        for fragment, fparams in self._filters:
            where_parts.append(fragment)
            params.extend(fparams)

        # Exclusions (wrapped in NOT (…))
        for fragment, fparams in self._excludes:
            where_parts.append(f"NOT ({fragment})")
            params.extend(fparams)

        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)

        if self._order_by_cols:
            sql += " ORDER BY " + ", ".join(self._order_by_cols)

        if self._limit_val is not None:
            sql += f" LIMIT {self._limit_val}"
        elif self._offset_val is not None:
            # SQLite requires LIMIT before OFFSET; use -1 to mean "all rows"
            sql += " LIMIT -1"

        if self._offset_val is not None:
            sql += f" OFFSET {self._offset_val}"

        sql += ";"
        return sql, params

    # ── SQL string for display ───────────────────────────────────────────────

    def sql(self) -> str:
        """Return the SQL string that *would* be executed (without running it)."""
        from .connection import Database
        sql, params = self._build_sql()
        return Database._format_sql(sql, tuple(params))

    # ── Terminal methods ─────────────────────────────────────────────────────

    def _evaluate(self) -> list[M]:
        """Execute the query and hydrate model instances."""
        if self._evaluated is not None:
            return self._evaluated

        from .connection import Database

        sql, params = self._build_sql()
        cursor = Database.execute(sql, tuple(params))
        rows = cursor.fetchall()
        self._evaluated = [self._model._from_row(row) for row in rows]
        return self._evaluated

    def all(self) -> list[M]:
        """Execute and return all matching model instances as a list."""
        return self._evaluate()

    def first(self) -> Optional[M]:
        """Return the first matching instance, or None."""
        results = self.limit(1)._evaluate()
        return results[0] if results else None

    def last(self) -> Optional[M]:
        """Return the last matching instance (reverses all order_by dirs)."""
        # Flip ASC ↔ DESC on each order column
        flipped: list[str] = []
        for col in self._order_by_cols:
            if col.endswith(" DESC"):
                flipped.append(col[:-5] + " ASC")
            else:
                flipped.append(col[:-4] + " DESC")

        clone = self._clone()
        clone._order_by_cols = flipped if flipped else self._order_by_cols
        results = clone.limit(1)._evaluate()
        return results[0] if results else None

    def count(self) -> int:
        """Return the number of rows matching the current filters."""
        from .connection import Database

        table = self._model._meta["table_name"]
        sql = f"SELECT COUNT(*) FROM {table}"
        params: list[Any] = []

        where_parts: list[str] = []
        for fragment, fparams in self._filters:
            where_parts.append(fragment)
            params.extend(fparams)
        for fragment, fparams in self._excludes:
            where_parts.append(f"NOT ({fragment})")
            params.extend(fparams)

        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)
        sql += ";"

        cursor = Database.execute(sql, tuple(params))
        return cursor.fetchone()[0]

    def exists(self) -> bool:
        """Return True if at least one row matches."""
        return self.count() > 0

    def delete(self) -> int:
        """
        Delete all rows matching the current filters.

        Returns
        -------
        int
            Number of deleted rows.
        """
        from .connection import Database

        table = self._model._meta["table_name"]
        sql = f"DELETE FROM {table}"
        params: list[Any] = []

        where_parts: list[str] = []
        for fragment, fparams in self._filters:
            where_parts.append(fragment)
            params.extend(fparams)
        for fragment, fparams in self._excludes:
            where_parts.append(f"NOT ({fragment})")
            params.extend(fparams)

        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)
        sql += ";"

        cursor = Database.execute(sql, tuple(params), commit=True)
        return cursor.rowcount

    def update(self, **kwargs: Any) -> int:
        """
        Bulk-update fields for all matching rows.

        Returns
        -------
        int
            Number of updated rows.
        """
        from .connection import Database

        if not kwargs:
            return 0

        table = self._model._meta["table_name"]
        set_parts = [f"{col} = ?" for col in kwargs]
        set_params = list(kwargs.values())

        sql = f"UPDATE {table} SET {', '.join(set_parts)}"
        params: list[Any] = list(set_params)

        where_parts: list[str] = []
        for fragment, fparams in self._filters:
            where_parts.append(fragment)
            params.extend(fparams)
        for fragment, fparams in self._excludes:
            where_parts.append(f"NOT ({fragment})")
            params.extend(fparams)

        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)
        sql += ";"

        cursor = Database.execute(sql, tuple(params), commit=True)
        return cursor.rowcount

    # ── Iteration / repr ─────────────────────────────────────────────────────

    def __iter__(self) -> Iterator[M]:
        return iter(self._evaluate())

    def __len__(self) -> int:
        return len(self._evaluate())

    def __getitem__(self, index: int) -> M:
        return self._evaluate()[index]

    def __repr__(self) -> str:
        try:
            results = self._evaluate()
            return f"<QuerySet {results!r}>"
        except Exception as exc:
            return f"<QuerySet (unevaluated) [{exc}]>"
