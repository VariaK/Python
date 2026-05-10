"""
orm/connection.py
─────────────────
Thread-safe SQLite connection manager.

The singleton `Database` object is the single source of truth for:
  • the active SQLite connection
  • verbose SQL logging (controlled by ``Database.echo``)

Usage
-----
    from orm.connection import Database

    # Configure once at application startup
    Database.connect("myapp.db")
    Database.echo = True        # print every SQL statement

    # Use as a context manager for auto-commit / rollback
    with Database.get_connection() as conn:
        conn.execute("INSERT INTO ...")
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from typing import Generator, Optional


class _Database:
    """
    Internal singleton that wraps a ``sqlite3.Connection``.

    Attributes
    ----------
    echo : bool
        When True, every SQL statement is printed to stdout.
    """

    def __init__(self) -> None:
        self._connection: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
        self.echo: bool = True          # default: verbose SQL logging

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def connect(self, db_path: str = ":memory:") -> None:
        """
        Open (or re-open) the SQLite database at *db_path*.

        Parameters
        ----------
        db_path : str
            Filesystem path to the .db file, or ``":memory:"`` for an
            in-memory database (useful for testing).
        """
        with self._lock:
            if self._connection is not None:
                self._connection.close()

            self._connection = sqlite3.connect(db_path, check_same_thread=False)
            # Return rows as sqlite3.Row objects so we can access columns by name
            self._connection.row_factory = sqlite3.Row
            # Enforce foreign-key constraints (disabled by default in SQLite)
            self._connection.execute("PRAGMA foreign_keys = ON;")
            self._connection.commit()

    def close(self) -> None:
        """Close the active connection."""
        with self._lock:
            if self._connection:
                self._connection.close()
                self._connection = None

    # ── Connection access ────────────────────────────────────────────────────

    def get_connection(self) -> sqlite3.Connection:
        """Return the raw connection, raising if not yet initialised."""
        if self._connection is None:
            raise RuntimeError(
                "Database is not connected.  Call Database.connect('<path>') first."
            )
        return self._connection

    # ── Query execution ──────────────────────────────────────────────────────

    def execute(
        self,
        sql: str,
        params: tuple = (),
        *,
        commit: bool = False,
    ) -> sqlite3.Cursor:
        """
        Execute *sql* with optional *params*.

        Parameters
        ----------
        sql : str
            SQL statement.
        params : tuple
            Positional parameters bound via sqlite3's ``?`` placeholders.
        commit : bool
            If True, commit immediately after execution.

        Returns
        -------
        sqlite3.Cursor
        """
        conn = self.get_connection()

        if self.echo:
            # Pretty-print the SQL with substituted values for readability
            display_sql = self._format_sql(sql, params)
            print(f"\033[36mSQL:\033[0m {display_sql}")

        with self._lock:
            cursor = conn.execute(sql, params)
            if commit:
                conn.commit()
        return cursor

    def executemany(
        self,
        sql: str,
        params_list: list[tuple],
        *,
        commit: bool = True,
    ) -> sqlite3.Cursor:
        """Batch-execute *sql* for each parameter tuple in *params_list*."""
        conn = self.get_connection()
        if self.echo:
            print(f"\033[36mSQL (batch):\033[0m {sql.strip()} — {len(params_list)} rows")
        with self._lock:
            cursor = conn.executemany(sql, params_list)
            if commit:
                conn.commit()
        return cursor

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for explicit transactions.

        Commits on success, rolls back on any exception.

        Example
        -------
            with Database.transaction() as conn:
                conn.execute("INSERT INTO ...")
        """
        conn = self.get_connection()
        try:
            yield conn
            with self._lock:
                conn.commit()
        except Exception:
            with self._lock:
                conn.rollback()
            raise

    # ── Formatting ───────────────────────────────────────────────────────────

    @staticmethod
    def _format_sql(sql: str, params: tuple) -> str:
        """Return a human-readable SQL string with params substituted in."""
        formatted = sql.strip()
        if not params:
            return formatted
        # Simple substitution for display purposes only (not for execution)
        for p in params:
            if isinstance(p, str):
                formatted = formatted.replace("?", f"'{p}'", 1)
            elif p is None:
                formatted = formatted.replace("?", "NULL", 1)
            else:
                formatted = formatted.replace("?", str(p), 1)
        return formatted


# ── Public singleton ─────────────────────────────────────────────────────────
Database = _Database()
