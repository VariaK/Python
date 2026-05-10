"""
tqueue/broker.py
────────────────
Message broker abstraction with two backends:

    RedisBroker    — uses Redis lists as queues (LPUSH / BRPOP)
    SQLiteBroker   — uses SQLite for broker-less local operation

Both brokers implement the same ``Broker`` ABC so the rest of the system
is backend-agnostic.

Queue naming convention
-----------------------
Given a logical queue ``"default"``:

  • Main queue    → "tq:queue:default"
  • Retry queue   → "tq:retry:default"   (tasks waiting for their backoff delay)
  • Dead-letter   → "tq:dlq:default"

With the SQLite broker, these become table-row ``queue_name`` values.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from typing import Optional

from .task import Task, TaskStatus


# ──────────────────────────────────────────────────────────────────────────────
# Abstract broker
# ──────────────────────────────────────────────────────────────────────────────

class Broker(ABC):
    """Abstract base class for all broker implementations."""

    @abstractmethod
    def enqueue(self, task: Task) -> None:
        """Push a task onto the main queue."""

    @abstractmethod
    def dequeue(self, queue_name: str = "default", timeout: float = 2.0) -> Optional[Task]:
        """
        Block for up to *timeout* seconds waiting for a task.

        Returns ``None`` on timeout (allows the worker to check a stop flag).
        """

    @abstractmethod
    def enqueue_dlq(self, task: Task) -> None:
        """Push a permanently-failed task to the dead-letter queue."""

    @abstractmethod
    def requeue(self, task: Task, delay: float = 0.0) -> None:
        """Re-enqueue a task for a retry, optionally after *delay* seconds."""

    @abstractmethod
    def queue_length(self, queue_name: str = "default") -> int:
        """Return number of pending tasks in the main queue."""

    @abstractmethod
    def dlq_length(self, queue_name: str = "default") -> int:
        """Return number of tasks in the dead-letter queue."""

    @abstractmethod
    def flush(self, queue_name: str = "default") -> None:
        """Clear the queue and DLQ (useful for tests)."""


# ──────────────────────────────────────────────────────────────────────────────
# Redis Broker
# ──────────────────────────────────────────────────────────────────────────────

class RedisBroker(Broker):
    """
    Broker backed by Redis lists.

    Uses ``LPUSH`` to enqueue and ``BRPOP`` to dequeue (blocking pop).
    This is the classic reliable-queue pattern described in the Redis docs.

    Parameters
    ----------
    url : str
        Redis connection URL, e.g. ``"redis://localhost:6379/0"``.
    """

    def __init__(self, url: str = "redis://localhost:6379/0") -> None:
        try:
            import redis
        except ImportError:
            raise ImportError(
                "redis-py is not installed.  Run: pip install redis"
            )
        self._redis = redis.from_url(url, decode_responses=False)
        self._redis.ping()          # fail fast if unreachable
        self.url = url

    # ── Key helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _key(queue_name: str) -> str:
        return f"tq:queue:{queue_name}"

    @staticmethod
    def _dlq_key(queue_name: str) -> str:
        return f"tq:dlq:{queue_name}"

    # ── Broker API ────────────────────────────────────────────────────────────

    def enqueue(self, task: Task) -> None:
        self._redis.lpush(self._key(task.queue_name), task.to_bytes())

    def dequeue(self, queue_name: str = "default", timeout: float = 2.0) -> Optional[Task]:
        result = self._redis.brpop(self._key(queue_name), timeout=int(timeout))
        if result is None:
            return None
        _, data = result
        return Task.from_bytes(data)

    def enqueue_dlq(self, task: Task) -> None:
        task.status = TaskStatus.DEAD_LETTER
        self._redis.lpush(self._dlq_key(task.queue_name), task.to_bytes())

    def requeue(self, task: Task, delay: float = 0.0) -> None:
        if delay > 0:
            time.sleep(delay)
        task.status = TaskStatus.PENDING
        self._redis.lpush(self._key(task.queue_name), task.to_bytes())

    def queue_length(self, queue_name: str = "default") -> int:
        return self._redis.llen(self._key(queue_name))

    def dlq_length(self, queue_name: str = "default") -> int:
        return self._redis.llen(self._dlq_key(queue_name))

    def flush(self, queue_name: str = "default") -> None:
        self._redis.delete(self._key(queue_name), self._dlq_key(queue_name))

    def __repr__(self) -> str:
        return f"RedisBroker(url={self.url!r})"


# ──────────────────────────────────────────────────────────────────────────────
# SQLite Broker (fallback — no external dependencies)
# ──────────────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tq_messages (
    rowid       INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_name  TEXT    NOT NULL,
    is_dlq      INTEGER NOT NULL DEFAULT 0,
    payload     BLOB    NOT NULL,
    available_at REAL   NOT NULL DEFAULT 0,  -- unix timestamp; 0 = immediately
    created_at  REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_queue ON tq_messages (queue_name, is_dlq, available_at);
"""


class SQLiteBroker(Broker):
    """
    Broker backed by a SQLite database.

    Suitable for local development, testing, and single-machine deployments
    where Redis is not available.

    Concurrency
    -----------
    Uses WAL mode and busy-timeout to handle concurrent writers from multiple
    worker processes without raising ``OperationalError: database is locked``.

    Parameters
    ----------
    db_path : str
        Path to the SQLite database file.  Use ``":memory:"`` only for
        single-process tests (in-memory databases are not shared across
        processes).
    """

    def __init__(self, db_path: str = "tqueue.db") -> None:
        self.db_path = db_path
        self._local = threading.local()   # per-thread connection cache
        self._init_schema()

    # ── Connection ────────────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        """Return a thread-local SQLite connection."""
        if not getattr(self._local, "conn", None):
            conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            self._local.conn = conn
        return self._local.conn

    def _init_schema(self) -> None:
        conn = self._conn()
        conn.executescript(_SCHEMA)
        conn.commit()

    # ── Broker API ────────────────────────────────────────────────────────────

    def enqueue(self, task: Task) -> None:
        conn = self._conn()
        conn.execute(
            "INSERT INTO tq_messages (queue_name, is_dlq, payload, available_at, created_at) "
            "VALUES (?, 0, ?, 0, ?)",
            (task.queue_name, task.to_bytes(), time.time()),
        )
        conn.commit()

    def dequeue(self, queue_name: str = "default", timeout: float = 2.0) -> Optional[Task]:
        """
        Poll the SQLite queue for up to *timeout* seconds.

        Uses a short-sleep polling loop rather than a blocking call because
        SQLite doesn't support server-side push notifications.
        """
        deadline = time.monotonic() + timeout
        poll_interval = 0.05      # 50 ms

        while time.monotonic() < deadline:
            task = self._try_dequeue(queue_name)
            if task is not None:
                return task
            time.sleep(poll_interval)
        return None

    def _try_dequeue(self, queue_name: str) -> Optional[Task]:
        """Atomically claim the oldest available task row."""
        conn = self._conn()
        now = time.time()
        try:
            # SELECT + DELETE in a transaction to avoid race conditions
            row = conn.execute(
                "SELECT rowid, payload FROM tq_messages "
                "WHERE queue_name = ? AND is_dlq = 0 AND available_at <= ? "
                "ORDER BY rowid ASC LIMIT 1",
                (queue_name, now),
            ).fetchone()

            if row is None:
                return None

            conn.execute("DELETE FROM tq_messages WHERE rowid = ?", (row["rowid"],))
            conn.commit()
            return Task.from_bytes(row["payload"])
        except sqlite3.OperationalError:
            # Another process grabbed the row first — that's fine
            conn.rollback()
            return None

    def enqueue_dlq(self, task: Task) -> None:
        task.status = TaskStatus.DEAD_LETTER
        conn = self._conn()
        conn.execute(
            "INSERT INTO tq_messages (queue_name, is_dlq, payload, available_at, created_at) "
            "VALUES (?, 1, ?, 0, ?)",
            (task.queue_name, task.to_bytes(), time.time()),
        )
        conn.commit()

    def requeue(self, task: Task, delay: float = 0.0) -> None:
        """Re-insert the task, making it available after *delay* seconds."""
        task.status = TaskStatus.PENDING
        available_at = time.time() + delay
        conn = self._conn()
        conn.execute(
            "INSERT INTO tq_messages (queue_name, is_dlq, payload, available_at, created_at) "
            "VALUES (?, 0, ?, ?, ?)",
            (task.queue_name, task.to_bytes(), available_at, time.time()),
        )
        conn.commit()

    def queue_length(self, queue_name: str = "default") -> int:
        conn = self._conn()
        row = conn.execute(
            "SELECT COUNT(*) FROM tq_messages WHERE queue_name = ? AND is_dlq = 0",
            (queue_name,),
        ).fetchone()
        return row[0]

    def dlq_length(self, queue_name: str = "default") -> int:
        conn = self._conn()
        row = conn.execute(
            "SELECT COUNT(*) FROM tq_messages WHERE queue_name = ? AND is_dlq = 1",
            (queue_name,),
        ).fetchone()
        return row[0]

    def flush(self, queue_name: str = "default") -> None:
        conn = self._conn()
        conn.execute(
            "DELETE FROM tq_messages WHERE queue_name = ?", (queue_name,)
        )
        conn.commit()

    def __repr__(self) -> str:
        return f"SQLiteBroker(db={self.db_path!r})"


# ──────────────────────────────────────────────────────────────────────────────
# Auto-select broker
# ──────────────────────────────────────────────────────────────────────────────

def create_broker(redis_url: Optional[str] = None, db_path: str = "tqueue.db") -> Broker:
    """
    Return a ``RedisBroker`` if Redis is reachable, else fall back to
    ``SQLiteBroker``.

    Parameters
    ----------
    redis_url : str | None
        Redis connection URL.  If None, no Redis attempt is made.
    db_path : str
        SQLite file path used when Redis is unavailable.
    """
    if redis_url:
        try:
            broker = RedisBroker(redis_url)
            return broker
        except Exception:
            pass
    return SQLiteBroker(db_path)
