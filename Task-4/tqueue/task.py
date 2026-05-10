"""
tqueue/task.py
──────────────
Canonical Task data model.

A Task represents a single unit of work to be executed by a worker.

Serialisation strategy
----------------------
The task is serialised in two layers:

  1. **Payload** (``pickle``) – the callable and its arguments.
     Pickle is used because callables (functions, lambdas, bound methods)
     are not JSON-serialisable.

  2. **Envelope** (``json``) – all metadata fields (id, status, timestamps,
     retry counts, etc.).  JSON is human-readable and easy to inspect in
     Redis or SQLite without a Python interpreter.

The two layers are combined into a single ``bytes`` object via
``Task.to_bytes()`` / ``Task.from_bytes()`` for transport over the broker.
"""

from __future__ import annotations

import json
import pickle
import time
import traceback
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


# ──────────────────────────────────────────────────────────────────────────────
# Status enum
# ──────────────────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING     = "PENDING"
    RUNNING     = "RUNNING"
    SUCCESS     = "SUCCESS"
    FAILED      = "FAILED"
    RETRYING    = "RETRYING"
    DEAD_LETTER = "DEAD_LETTER"


# ──────────────────────────────────────────────────────────────────────────────
# Task
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Task:
    """
    Immutable-ish envelope for a single unit of callable work.

    Attributes
    ----------
    id : str
        Unique 8-hex-char identifier (auto-generated).
    func : Callable
        The Python callable to invoke.
    args : tuple
        Positional arguments for *func*.
    kwargs : dict
        Keyword arguments for *func*.
    queue_name : str
        Name of the queue this task belongs to.
    max_retries : int
        Maximum number of retry attempts before moving to dead-letter.
    retry_count : int
        How many times this task has been retried so far.
    status : TaskStatus
        Current lifecycle state.
    result : Any
        Return value from a successful execution.
    error : str | None
        Formatted traceback of the most recent failure.
    created_at : float
        Unix timestamp of task creation.
    started_at : float | None
        Unix timestamp when a worker picked up the task.
    completed_at : float | None
        Unix timestamp when the task finished (success or dead-letter).
    timeout : float | None
        Max seconds a worker will wait before killing execution.
    """

    func:         Callable
    args:         tuple         = field(default_factory=tuple)
    kwargs:       dict          = field(default_factory=dict)
    queue_name:   str           = "default"
    max_retries:  int           = 3
    retry_count:  int           = 0
    status:       TaskStatus    = TaskStatus.PENDING
    result:       Any           = None
    error:        Optional[str] = None
    created_at:   float         = field(default_factory=time.time)
    started_at:   Optional[float] = None
    completed_at: Optional[float] = None
    timeout:      Optional[float] = None
    id:           str           = field(default_factory=lambda: uuid.uuid4().hex[:8])

    # ── Derived properties ────────────────────────────────────────────────────

    @property
    def func_name(self) -> str:
        return getattr(self.func, "__name__", repr(self.func))

    @property
    def duration(self) -> Optional[float]:
        if self.started_at is not None and self.completed_at is not None:
            return round(self.completed_at - self.started_at, 3)
        return None

    @property
    def age(self) -> float:
        return round(time.time() - self.created_at, 3)

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_bytes(self) -> bytes:
        """
        Serialise the task to a compact bytes representation.

        Format
        ------
        The output is a ``pickle`` dump of a dict that contains both the
        picklable payload *and* the JSON-serialisable metadata.  Using a
        single pickle ensures that the callable reference is preserved and
        that the wire format is a single opaque blob (simple for brokers).
        """
        payload = {
            # Picklable layer
            "func":     self.func,
            "args":     self.args,
            "kwargs":   self.kwargs,
            # JSON-friendly metadata (included for easy inspection)
            "meta": {
                "id":           self.id,
                "queue_name":   self.queue_name,
                "max_retries":  self.max_retries,
                "retry_count":  self.retry_count,
                "status":       self.status.value,
                "result":       self._safe_json(self.result),
                "error":        self.error,
                "created_at":   self.created_at,
                "started_at":   self.started_at,
                "completed_at": self.completed_at,
                "timeout":      self.timeout,
            },
        }
        return pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def from_bytes(cls, data: bytes) -> "Task":
        """Reconstruct a Task from the bytes produced by ``to_bytes()``."""
        payload = pickle.loads(data)
        meta    = payload["meta"]
        return cls(
            id           = meta["id"],
            func         = payload["func"],
            args         = payload["args"],
            kwargs       = payload["kwargs"],
            queue_name   = meta["queue_name"],
            max_retries  = meta["max_retries"],
            retry_count  = meta["retry_count"],
            status       = TaskStatus(meta["status"]),
            result       = meta["result"],
            error        = meta["error"],
            created_at   = meta["created_at"],
            started_at   = meta["started_at"],
            completed_at = meta["completed_at"],
            timeout      = meta["timeout"],
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _safe_json(value: Any) -> Any:
        """Return *value* if JSON-serialisable, else its string repr."""
        try:
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            return repr(value)

    # ── Dunder ────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"<Task id={self.id} func={self.func_name} "
            f"status={self.status.value} retries={self.retry_count}/{self.max_retries}>"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Backoff calculator
# ──────────────────────────────────────────────────────────────────────────────

def exponential_backoff(
    attempt: int,
    base: float = 2.0,
    cap: float = 60.0,
    jitter: bool = True,
) -> float:
    """
    Return the delay in seconds for the given retry *attempt* (0-indexed).

    Formula:  delay = min(base ** (attempt + 1), cap)
    With jitter: delay *= random(0.5, 1.0)

    Parameters
    ----------
    attempt : int
        Zero-indexed retry number (0 → first retry).
    base : float
        Multiplier base.  Default 2 → 2s, 4s, 8s, 16s, …
    cap : float
        Maximum delay (seconds) regardless of attempt count.
    jitter : bool
        Add randomness to avoid thundering-herd on mass failure.
    """
    import random
    delay = min(base ** (attempt + 1), cap)
    if jitter:
        delay *= random.uniform(0.5, 1.0)
    return round(delay, 2)
