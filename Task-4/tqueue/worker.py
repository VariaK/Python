"""
tqueue/worker.py
─────────────────
Worker process implementation.

Each Worker runs in its own ``multiprocessing.Process`` and loops:

    1.  Dequeue a task from the broker (blocking poll)
    2.  Mark it RUNNING in the result backend
    3.  Execute the callable with an optional timeout
    4.  On success  → store SUCCESS result
    5.  On failure  → apply exponential backoff retry, or move to DLQ

Retry Logic
-----------
    attempt 0: immediate execution
    attempt 1: delay = backoff(0)  ≈ 2 s
    attempt 2: delay = backoff(1)  ≈ 4 s
    attempt 3: delay = backoff(2)  ≈ 8 s  (if max_retries=3 → DLQ)

The delay is implemented via ``Broker.requeue(task, delay=...)`` which
inserts the task back with ``available_at = now + delay``.

Timeout
-------
Task execution is wrapped in a ``multiprocessing.Process`` if
``task.timeout`` is set, otherwise runs in the worker's own thread
using ``concurrent.futures.ThreadPoolExecutor`` with a timeout.

Graceful shutdown
-----------------
Each worker respects a ``multiprocessing.Event`` stop signal.  Calling
``worker.stop()`` sets the event; the worker finishes its current task
and exits cleanly.
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import signal
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional

from .broker import Broker
from .result_backend import ResultBackend
from .task import Task, TaskStatus, exponential_backoff

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Worker
# ──────────────────────────────────────────────────────────────────────────────

class Worker:
    """
    A single consumer process that polls the broker and executes tasks.

    Parameters
    ----------
    broker_kwargs : dict
        Keyword arguments passed to ``SQLiteBroker(**broker_kwargs)`` inside
        the child process.  Avoids pickling ``threading.local`` (Windows
        multiprocessing uses 'spawn', which pickles the Process object).
    backend_kwargs : dict
        Keyword arguments passed to ``SQLiteResultBackend(**backend_kwargs)``
        inside the child process.
    worker_id : str
        Human-readable identifier (e.g. ``"WORKER-1"``).  
    queue_name : str
        Which queue to consume from.
    poll_timeout : float
        How long to block per dequeue attempt (seconds).
    """

    def __init__(
        self,
        broker_kwargs:  dict,
        backend_kwargs: dict,
        worker_id:      str   = "WORKER-1",
        queue_name:     str   = "default",
        poll_timeout:   float = 2.0,
    ) -> None:
        self.broker_kwargs  = broker_kwargs
        self.backend_kwargs = backend_kwargs
        self.worker_id      = worker_id
        self.queue_name     = queue_name
        self.poll_timeout   = poll_timeout

        # Multiprocessing coordination
        self._stop_event = multiprocessing.Event()
        self._process: Optional[multiprocessing.Process] = None

        # Stats (in-process only, not shared across processes)
        self.tasks_processed = 0
        self.tasks_failed    = 0

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Spawn the worker as a daemon child process."""
        self._process = multiprocessing.Process(
            target=self._run,
            name=self.worker_id,
            daemon=True,
        )
        self._process.start()
        self._log(f"Started (pid={self._process.pid})")

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the worker to stop and wait for it to exit."""
        self._stop_event.set()
        if self._process and self._process.is_alive():
            self._process.join(timeout=timeout)
            if self._process.is_alive():
                self._process.terminate()
        self._log("Stopped")

    @property
    def is_alive(self) -> bool:
        return self._process is not None and self._process.is_alive()

    # ── Main loop (runs inside the child process) ─────────────────────────────

    def _run(self) -> None:
        """Entry point executed inside the child process."""
        # Re-create broker and backend here — threading.local is not picklable
        from .broker import SQLiteBroker
        from .result_backend import SQLiteResultBackend
        self.broker         = SQLiteBroker(**self.broker_kwargs)
        self.result_backend = SQLiteResultBackend(**self.backend_kwargs)

        signal.signal(signal.SIGTERM, self._handle_sigterm)

        self._log("Ready — waiting for tasks")

        while not self._stop_event.is_set():
            try:
                task = self.broker.dequeue(
                    queue_name=self.queue_name,
                    timeout=self.poll_timeout,
                )
                if task is None:
                    continue  # poll timeout → check stop flag and try again

                self._handle_task(task)
            except KeyboardInterrupt:
                break
            except Exception as exc:
                self._log(f"Unhandled error in main loop: {exc}", level="error")
                time.sleep(1)

        self._log("Exiting cleanly")

    def _handle_sigterm(self, signum, frame) -> None:
        self._stop_event.set()

    # ── Task execution ────────────────────────────────────────────────────────

    def _handle_task(self, task: Task) -> None:
        """Execute a task and manage the retry / DLQ lifecycle."""
        task.status     = TaskStatus.RUNNING
        task.started_at = time.time()
        self.result_backend.store(task)

        self._log(f"Picked up task {task.id} ({task.func_name})")

        try:
            result = self._execute(task)

            task.status       = TaskStatus.SUCCESS
            task.result       = result
            task.completed_at = time.time()
            self.result_backend.store(task)
            self.tasks_processed += 1
            self._log(
                f"Task {task.id} completed in {task.duration}s"
                + (f" — result: {result!r}" if result is not None else "")
            )

        except Exception as exc:
            self._handle_failure(task, exc)

    def _execute(self, task: Task) -> object:
        """
        Run ``task.func(*task.args, **task.kwargs)`` with optional timeout.

        Uses ``ThreadPoolExecutor`` so the worker process itself is not
        killed on timeout — instead a ``TimeoutError`` is raised.
        """
        if task.timeout:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(task.func, *task.args, **task.kwargs)
                try:
                    return future.result(timeout=task.timeout)
                except FuturesTimeoutError:
                    raise TimeoutError(
                        f"Task {task.id} timed out after {task.timeout}s"
                    )
        else:
            return task.func(*task.args, **task.kwargs)

    def _handle_failure(self, task: Task, exc: Exception) -> None:
        """Apply retry logic or move to DLQ on permanent failure."""
        task.error = traceback.format_exc()
        self.tasks_failed += 1

        if task.retry_count < task.max_retries:
            task.retry_count += 1
            delay = exponential_backoff(task.retry_count - 1, jitter=False)

            task.status = TaskStatus.RETRYING
            self.result_backend.store(task)

            self._log(
                f"Task {task.id} FAILED ({type(exc).__name__}) "
                f"— retry {task.retry_count}/{task.max_retries} in {delay}s"
            )
            self.broker.requeue(task, delay=delay)
        else:
            # Exhausted retries → dead-letter queue
            task.status       = TaskStatus.DEAD_LETTER
            task.completed_at = time.time()
            self.result_backend.store(task)
            self.broker.enqueue_dlq(task)

            self._log(
                f"Task {task.id} moved to DEAD_LETTER after "
                f"{task.retry_count} retries — {type(exc).__name__}: {exc}"
            )

    # ── Logging ───────────────────────────────────────────────────────────────

    def _log(self, msg: str, level: str = "info") -> None:
        tag = f"[{self.worker_id}]"
        full = f"{tag} {msg}"
        getattr(logger, level)(full)
        print(full)


# ──────────────────────────────────────────────────────────────────────────────
# WorkerPool
# ──────────────────────────────────────────────────────────────────────────────

class WorkerPool:
    """
    Convenience wrapper that spawns and manages N Worker processes.

    Parameters
    ----------
    broker_kwargs : dict
        Passed to SQLiteBroker inside each child process.
    backend_kwargs : dict
        Passed to SQLiteResultBackend inside each child process.
    num_workers : int
        Number of worker processes to spawn.
    queue_name : str
        Queue all workers consume from.
    poll_timeout : float
        Per-dequeue poll timeout (seconds).
    """

    def __init__(
        self,
        broker_kwargs:  dict,
        backend_kwargs: dict,
        num_workers:    int   = 2,
        queue_name:     str   = "default",
        poll_timeout:   float = 2.0,
    ) -> None:
        self.broker_kwargs  = broker_kwargs
        self.backend_kwargs = backend_kwargs
        self.num_workers    = num_workers
        self.queue_name     = queue_name
        self.poll_timeout   = poll_timeout
        self._workers: list[Worker] = []

    def start(self) -> None:
        """Spawn all workers."""
        for i in range(1, self.num_workers + 1):
            w = Worker(
                broker_kwargs  = self.broker_kwargs,
                backend_kwargs = self.backend_kwargs,
                worker_id      = f"WORKER-{i}",
                queue_name     = self.queue_name,
                poll_timeout   = self.poll_timeout,
            )
            w.start()
            self._workers.append(w)
        print(f"[WorkerPool] {self.num_workers} workers started on queue '{self.queue_name}'")

    def stop(self, timeout: float = 5.0) -> None:
        """Gracefully stop all workers."""
        for w in self._workers:
            w.stop(timeout=timeout)
        self._workers.clear()
        print("[WorkerPool] All workers stopped")

    @property
    def alive_count(self) -> int:
        return sum(1 for w in self._workers if w.is_alive)
