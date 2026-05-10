"""
tqueue/result_backend.py
─────────────────────────
Result storage backends.

After a task finishes (success, failure, or dead-letter) the worker writes
a ``TaskRecord`` to the result backend.  The producer/caller can later
retrieve the result by task id.

Two implementations:

    SQLiteResultBackend  — default, no external dependencies
    RedisResultBackend   — for Redis-native deployments

Both implement the ``ResultBackend`` ABC.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from .task import Task, TaskStatus


# ──────────────────────────────────────────────────────────────────────────────
# Shared record dict type
# ──────────────────────────────────────────────────────────────────────────────

def _task_to_record(task: Task) -> dict:
    """Convert a Task to a plain dict for storage."""
    return {
        "id":           task.id,
        "func_name":    task.func_name,
        "queue_name":   task.queue_name,
        "status":       task.status.value,
        "retry_count":  task.retry_count,
        "max_retries":  task.max_retries,
        "result":       task._safe_json(task.result),
        "error":        task.error,
        "created_at":   task.created_at,
        "started_at":   task.started_at,
        "completed_at": task.completed_at,
        "duration":     task.duration,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Abstract backend
# ──────────────────────────────────────────────────────────────────────────────

class ResultBackend(ABC):

    @abstractmethod
    def store(self, task: Task) -> None:
        """Persist the task record (upsert by task id)."""

    @abstractmethod
    def fetch(self, task_id: str) -> Optional[dict]:
        """Return the record dict for *task_id*, or None if not found."""

    @abstractmethod
    def all_records(self) -> list[dict]:
        """Return all stored records (for the dashboard)."""

    @abstractmethod
    def clear(self) -> None:
        """Delete all records."""


# ──────────────────────────────────────────────────────────────────────────────
# SQLite Result Backend
# ──────────────────────────────────────────────────────────────────────────────

_RESULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS tq_results (
    id           TEXT PRIMARY KEY,
    func_name    TEXT,
    queue_name   TEXT,
    status       TEXT,
    retry_count  INTEGER,
    max_retries  INTEGER,
    result       TEXT,           -- JSON-encoded
    error        TEXT,
    created_at   REAL,
    started_at   REAL,
    completed_at REAL,
    duration     REAL,
    updated_at   REAL
);
"""


class SQLiteResultBackend(ResultBackend):
    """
    Stores task results in a SQLite database.

    Safe for multi-process access via WAL mode + busy-timeout.

    Parameters
    ----------
    db_path : str
        Path to the SQLite file. Defaults to the same file as the broker.
    """

    def __init__(self, db_path: str = "tqueue.db") -> None:
        self.db_path = db_path
        self._local = threading.local()
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        if not getattr(self._local, "conn", None):
            conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            self._local.conn = conn
        return self._local.conn

    def _init_schema(self) -> None:
        conn = self._conn()
        conn.executescript(_RESULT_SCHEMA)
        conn.commit()

    def store(self, task: Task) -> None:
        rec = _task_to_record(task)
        conn = self._conn()
        conn.execute(
            """
            INSERT INTO tq_results
                (id, func_name, queue_name, status, retry_count, max_retries,
                 result, error, created_at, started_at, completed_at, duration, updated_at)
            VALUES
                (:id, :func_name, :queue_name, :status, :retry_count, :max_retries,
                 :result, :error, :created_at, :started_at, :completed_at, :duration, :updated_at)
            ON CONFLICT(id) DO UPDATE SET
                status       = excluded.status,
                retry_count  = excluded.retry_count,
                result       = excluded.result,
                error        = excluded.error,
                started_at   = excluded.started_at,
                completed_at = excluded.completed_at,
                duration     = excluded.duration,
                updated_at   = excluded.updated_at
            """,
            {**rec, "result": json.dumps(rec["result"]), "updated_at": time.time()},
        )
        conn.commit()

    def fetch(self, task_id: str) -> Optional[dict]:
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM tq_results WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def all_records(self) -> list[dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM tq_results ORDER BY created_at ASC"
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def clear(self) -> None:
        conn = self._conn()
        conn.execute("DELETE FROM tq_results")
        conn.commit()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        try:
            d["result"] = json.loads(d["result"]) if d["result"] else None
        except (json.JSONDecodeError, TypeError):
            pass
        return d


# ──────────────────────────────────────────────────────────────────────────────
# Redis Result Backend
# ──────────────────────────────────────────────────────────────────────────────

class RedisResultBackend(ResultBackend):
    """
    Stores task results as JSON hashes in Redis.

    Key pattern: ``tq:result:<task_id>``

    Parameters
    ----------
    url : str
        Redis connection URL.
    ttl : int
        Result expiry in seconds (default 24 h).
    """

    def __init__(self, url: str = "redis://localhost:6379/0", ttl: int = 86400) -> None:
        import redis
        self._r = redis.from_url(url, decode_responses=True)
        self._ttl = ttl

    def _key(self, task_id: str) -> str:
        return f"tq:result:{task_id}"

    def _index_key(self) -> str:
        return "tq:result:_index"

    def store(self, task: Task) -> None:
        rec = _task_to_record(task)
        key = self._key(task.id)
        # Encode non-string fields
        flat = {k: ("" if v is None else json.dumps(v)) for k, v in rec.items()}
        self._r.hset(key, mapping=flat)
        self._r.expire(key, self._ttl)
        self._r.sadd(self._index_key(), task.id)

    def fetch(self, task_id: str) -> Optional[dict]:
        key = self._key(task_id)
        data = self._r.hgetall(key)
        if not data:
            return None
        return {k: (json.loads(v) if v else None) for k, v in data.items()}

    def all_records(self) -> list[dict]:
        ids = self._r.smembers(self._index_key())
        records = []
        for tid in ids:
            rec = self.fetch(tid)
            if rec:
                records.append(rec)
        return sorted(records, key=lambda r: r.get("created_at") or 0)

    def clear(self) -> None:
        ids = self._r.smembers(self._index_key())
        for tid in ids:
            self._r.delete(self._key(tid))
        self._r.delete(self._index_key())


# ──────────────────────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────────────────────

def create_result_backend(
    redis_url: Optional[str] = None,
    db_path: str = "tqueue.db",
) -> ResultBackend:
    """Return a Redis backend if reachable, else SQLite."""
    if redis_url:
        try:
            backend = RedisResultBackend(redis_url)
            backend._r.ping()
            return backend
        except Exception:
            pass
    return SQLiteResultBackend(db_path)
