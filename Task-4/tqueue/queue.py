"""
tqueue/queue.py
───────────────
High-level producer API  —  the only class most users need to import.

    from tqueue import TaskQueue

    q = TaskQueue()             # SQLite broker, in-process workers
    q.start_workers(n=3)

    task = q.enqueue(my_func, arg1, arg2, kwarg=value)
    result = q.wait_for(task.id, timeout=30)

    q.stop_workers()
"""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

from .broker import Broker, SQLiteBroker, create_broker
from .result_backend import ResultBackend, SQLiteResultBackend, create_result_backend
from .task import Task, TaskStatus
from .worker import WorkerPool


class TaskQueue:
    """
    Facade that wires together broker + result backend + worker pool.

    Parameters
    ----------
    broker : Broker | None
        Explicit broker.  Auto-created (SQLite) if None.
    result_backend : ResultBackend | None
        Explicit result backend.  Auto-created (SQLite) if None.
    queue_name : str
        Logical queue name used for all operations.
    db_path : str
        SQLite database path (used when auto-creating backends).
    redis_url : str | None
        Redis URL; if provided and Redis is reachable, used as broker.
    """

    def __init__(
        self,
        broker:         Optional[Broker]        = None,
        result_backend: Optional[ResultBackend] = None,
        queue_name:     str                     = "default",
        db_path:        str                     = "tqueue.db",
        redis_url:      Optional[str]           = None,
    ) -> None:
        self.queue_name = queue_name
        self._db_path = db_path

        self.broker = broker or create_broker(redis_url=redis_url, db_path=db_path)
        self.result_backend = result_backend or create_result_backend(
            redis_url=redis_url, db_path=db_path
        )
        self._pool: Optional[WorkerPool] = None

    # ── Worker pool management ────────────────────────────────────────────────

    def start_workers(
        self,
        n: int = 2,
        poll_timeout: float = 1.0,
    ) -> None:
        """Spawn *n* worker processes consuming from this queue."""
        self._pool = WorkerPool(
            broker_kwargs  = {"db_path": self._db_path},
            backend_kwargs = {"db_path": self._db_path},
            num_workers    = n,
            queue_name     = self.queue_name,
            poll_timeout   = poll_timeout,
        )
        self._pool.start()

    def stop_workers(self, timeout: float = 5.0) -> None:
        """Gracefully shut down all worker processes."""
        if self._pool:
            self._pool.stop(timeout=timeout)
            self._pool = None

    # ── Producer API ──────────────────────────────────────────────────────────

    def enqueue(
        self,
        func:        Callable,
        *args:       Any,
        max_retries: int            = 3,
        timeout:     Optional[float]= None,
        **kwargs:    Any,
    ) -> Task:
        """
        Enqueue *func* for execution by a worker.

        Parameters
        ----------
        func : Callable
            The Python callable to execute.
        *args
            Positional arguments passed to *func*.
        max_retries : int
            Maximum retry count before moving to DLQ.
        timeout : float | None
            Execution timeout in seconds (None = unlimited).
        **kwargs
            Keyword arguments passed to *func*.

        Returns
        -------
        Task
            The enqueued task (status=PENDING, id already set).
        """
        task = Task(
            func        = func,
            args        = args,
            kwargs      = kwargs,
            queue_name  = self.queue_name,
            max_retries = max_retries,
            timeout     = timeout,
        )
        self.broker.enqueue(task)
        self.result_backend.store(task)
        print(f"Task queued: {task!r}")
        return task

    # ── Result retrieval ──────────────────────────────────────────────────────

    def get_result(self, task_id: str) -> Optional[dict]:
        """Return the stored result record for *task_id*, or None."""
        return self.result_backend.fetch(task_id)

    def wait_for(
        self,
        task_id: str,
        timeout: float = 60.0,
        poll_interval: float = 0.25,
    ) -> Optional[dict]:
        """
        Block until the task reaches a terminal state or *timeout* elapses.

        Terminal states: SUCCESS, DEAD_LETTER.

        Returns
        -------
        dict | None
            The result record, or None on timeout.
        """
        _terminal = {TaskStatus.SUCCESS.value, TaskStatus.DEAD_LETTER.value}
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            rec = self.result_backend.fetch(task_id)
            if rec and rec.get("status") in _terminal:
                return rec
            time.sleep(poll_interval)

        return None   # timed out

    # ── Introspection ─────────────────────────────────────────────────────────

    def pending_count(self) -> int:
        return self.broker.queue_length(self.queue_name)

    def dlq_count(self) -> int:
        return self.broker.dlq_length(self.queue_name)

    def all_results(self) -> list[dict]:
        return self.result_backend.all_records()

    def flush(self) -> None:
        """Clear queue and all results (useful between tests)."""
        self.broker.flush(self.queue_name)
        self.result_backend.clear()
