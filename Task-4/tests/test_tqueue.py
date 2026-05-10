"""
Task-4/tests/test_tqueue.py
============================
Unit + integration tests for the distributed task queue.

Tests use the SQLite broker and SQLite result backend with in-memory
databases where safe (single-process tests) and file-based databases
where multiprocessing is involved.

Run:
    pytest tests/ -v --tb=short
"""

from __future__ import annotations

import os
import tempfile
import time

import pytest

from tqueue.broker import SQLiteBroker
from tqueue.dashboard import Dashboard
from tqueue.queue import TaskQueue
from tqueue.result_backend import SQLiteResultBackend
from tqueue.task import Task, TaskStatus, exponential_backoff


# ──────────────────────────────────────────────────────────────────────────────
# Shared task functions (module-level for pickle)
# ──────────────────────────────────────────────────────────────────────────────

def _ok(x: int = 1) -> int:
    return x * 2


def _fail_always() -> None:
    raise ValueError("always fails")


_flaky_count: dict = {}

def _flaky(key: str = "default") -> str:
    _flaky_count[key] = _flaky_count.get(key, 0) + 1
    if _flaky_count[key] < 3:
        raise RuntimeError(f"attempt {_flaky_count[key]}")
    return "success"


def _slow(duration: float = 5.0) -> str:
    time.sleep(duration)
    return "done"


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_db(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture()
def broker(tmp_db):
    return SQLiteBroker(db_path=tmp_db)


@pytest.fixture()
def backend(tmp_db):
    return SQLiteResultBackend(db_path=tmp_db)


@pytest.fixture()
def queue(tmp_db):
    return TaskQueue(db_path=tmp_db)


# ──────────────────────────────────────────────────────────────────────────────
# 1. Task model & serialisation
# ──────────────────────────────────────────────────────────────────────────────

class TestTask:
    def test_id_auto_generated(self):
        t = Task(func=_ok)
        assert len(t.id) == 8

    def test_ids_unique(self):
        ids = {Task(func=_ok).id for _ in range(100)}
        assert len(ids) == 100

    def test_func_name(self):
        t = Task(func=_ok)
        assert t.func_name == "_ok"

    def test_default_status(self):
        t = Task(func=_ok)
        assert t.status == TaskStatus.PENDING

    def test_duration_none_when_not_started(self):
        t = Task(func=_ok)
        assert t.duration is None

    def test_duration_computed(self):
        t = Task(func=_ok)
        t.started_at   = 0.0
        t.completed_at = 1.5
        assert t.duration == 1.5

    def test_repr_contains_id(self):
        t = Task(func=_ok)
        assert t.id in repr(t)

    # ── Serialisation ─────────────────────────────────────────────────────────

    def test_round_trip_basic(self):
        t = Task(func=_ok, args=(3,), kwargs={}, max_retries=5)
        restored = Task.from_bytes(t.to_bytes())
        assert restored.id          == t.id
        assert restored.func_name   == t.func_name
        assert restored.max_retries == 5
        assert restored.args        == (3,)

    def test_round_trip_status(self):
        t = Task(func=_ok)
        t.status = TaskStatus.RETRYING
        restored = Task.from_bytes(t.to_bytes())
        assert restored.status == TaskStatus.RETRYING

    def test_round_trip_result(self):
        t = Task(func=_ok)
        t.result = {"key": "value", "num": 42}
        restored = Task.from_bytes(t.to_bytes())
        assert restored.result == {"key": "value", "num": 42}

    def test_to_bytes_type(self):
        assert isinstance(Task(func=_ok).to_bytes(), bytes)

    def test_round_trip_error(self):
        t = Task(func=_fail_always)
        t.error = "Traceback...\nValueError: always fails"
        restored = Task.from_bytes(t.to_bytes())
        assert "ValueError" in restored.error


# ──────────────────────────────────────────────────────────────────────────────
# 2. Exponential backoff
# ──────────────────────────────────────────────────────────────────────────────

class TestExponentialBackoff:
    def test_monotone_increase(self):
        delays = [exponential_backoff(i, jitter=False) for i in range(5)]
        assert delays == sorted(delays)

    def test_attempt_0(self):
        assert exponential_backoff(0, base=2.0, jitter=False) == 2.0

    def test_attempt_1(self):
        assert exponential_backoff(1, base=2.0, jitter=False) == 4.0

    def test_cap_respected(self):
        assert exponential_backoff(100, base=2.0, cap=10.0, jitter=False) == 10.0

    def test_jitter_within_range(self):
        # With jitter, delay should be < the deterministic value
        for _ in range(20):
            with_jitter    = exponential_backoff(3, base=2.0, cap=60.0, jitter=True)
            without_jitter = exponential_backoff(3, base=2.0, cap=60.0, jitter=False)
            assert with_jitter <= without_jitter


# ──────────────────────────────────────────────────────────────────────────────
# 3. SQLite Broker
# ──────────────────────────────────────────────────────────────────────────────

class TestSQLiteBroker:
    def test_enqueue_increases_length(self, broker):
        assert broker.queue_length() == 0
        broker.enqueue(Task(func=_ok, queue_name="default"))
        assert broker.queue_length() == 1

    def test_dequeue_returns_task(self, broker):
        task = Task(func=_ok, queue_name="default")
        broker.enqueue(task)
        fetched = broker.dequeue("default", timeout=2.0)
        assert fetched is not None
        assert fetched.id == task.id

    def test_dequeue_empty_returns_none(self, broker):
        result = broker.dequeue("default", timeout=0.1)
        assert result is None

    def test_dequeue_fifo_order(self, broker):
        tasks = [Task(func=_ok, queue_name="default") for _ in range(5)]
        for t in tasks:
            broker.enqueue(t)
        ids_out = []
        for _ in range(5):
            t = broker.dequeue("default", timeout=1.0)
            ids_out.append(t.id)
        assert ids_out == [t.id for t in tasks]

    def test_dlq_enqueue(self, broker):
        task = Task(func=_ok, queue_name="default")
        broker.enqueue_dlq(task)
        assert broker.dlq_length() == 1
        assert broker.queue_length() == 0

    def test_requeue_with_delay(self, broker):
        task = Task(func=_ok, queue_name="default")
        # No delay — immediately available
        broker.requeue(task, delay=0)
        assert broker.queue_length() == 1

    def test_flush_clears_queue(self, broker):
        broker.enqueue(Task(func=_ok, queue_name="default"))
        broker.flush("default")
        assert broker.queue_length() == 0

    def test_separate_queue_names(self, broker):
        broker.enqueue(Task(func=_ok, queue_name="alpha"))
        broker.enqueue(Task(func=_ok, queue_name="beta"))
        assert broker.queue_length("alpha") == 1
        assert broker.queue_length("beta")  == 1
        fetched = broker.dequeue("alpha", timeout=1.0)
        assert fetched.queue_name == "alpha"

    def test_delayed_requeue_not_visible_immediately(self, broker):
        task = Task(func=_ok, queue_name="default")
        broker.requeue(task, delay=10.0)   # 10 s delay
        # Should not be dequeued yet
        fetched = broker.dequeue("default", timeout=0.1)
        assert fetched is None


# ──────────────────────────────────────────────────────────────────────────────
# 4. SQLite Result Backend
# ──────────────────────────────────────────────────────────────────────────────

class TestSQLiteResultBackend:
    def test_store_and_fetch(self, backend):
        task = Task(func=_ok)
        task.status = TaskStatus.SUCCESS
        task.result = 42
        backend.store(task)
        rec = backend.fetch(task.id)
        assert rec is not None
        assert rec["id"] == task.id
        assert rec["status"] == "SUCCESS"

    def test_fetch_missing_returns_none(self, backend):
        assert backend.fetch("nonexistent") is None

    def test_upsert_updates_status(self, backend):
        task = Task(func=_ok)
        backend.store(task)
        task.status = TaskStatus.SUCCESS
        task.result = 99
        backend.store(task)
        rec = backend.fetch(task.id)
        assert rec["status"] == "SUCCESS"
        assert rec["result"] == 99

    def test_all_records_ordered(self, backend):
        tasks = [Task(func=_ok) for _ in range(3)]
        for t in tasks:
            backend.store(t)
        recs = backend.all_records()
        assert len(recs) == 3
        # created_at should be monotonically non-decreasing
        times = [r["created_at"] for r in recs]
        assert times == sorted(times)

    def test_clear(self, backend):
        backend.store(Task(func=_ok))
        backend.clear()
        assert backend.all_records() == []

    def test_result_json_roundtrip(self, backend):
        task = Task(func=_ok)
        task.result = {"nested": [1, 2, 3], "ok": True}
        task.status = TaskStatus.SUCCESS
        backend.store(task)
        rec = backend.fetch(task.id)
        assert rec["result"] == {"nested": [1, 2, 3], "ok": True}


# ──────────────────────────────────────────────────────────────────────────────
# 5. TaskQueue producer API (no workers)
# ──────────────────────────────────────────────────────────────────────────────

class TestTaskQueueProducer:
    def test_enqueue_returns_task(self, queue):
        task = queue.enqueue(_ok, 5)
        assert isinstance(task, Task)
        assert task.id is not None

    def test_enqueue_stores_in_backend(self, queue):
        task = queue.enqueue(_ok, 5)
        rec = queue.get_result(task.id)
        assert rec is not None
        assert rec["status"] == "PENDING"

    def test_enqueue_increments_pending(self, queue):
        assert queue.pending_count() == 0
        queue.enqueue(_ok)
        queue.enqueue(_ok)
        assert queue.pending_count() == 2

    def test_enqueue_max_retries(self, queue):
        task = queue.enqueue(_ok, max_retries=7)
        rec = queue.get_result(task.id)
        assert rec["max_retries"] == 7

    def test_flush_clears(self, queue):
        queue.enqueue(_ok)
        queue.flush()
        assert queue.pending_count() == 0
        assert queue.all_results() == []


# ──────────────────────────────────────────────────────────────────────────────
# 6. End-to-end: worker execution (multiprocessing)
# ──────────────────────────────────────────────────────────────────────────────

class TestWorkerExecution:
    """
    These tests spawn real worker processes, so they take a few seconds.
    They are marked 'integration' and can be skipped with -m 'not integration'.
    """

    def _run_queue(self, tmp_db, n_workers=2, poll=0.5):
        q = TaskQueue(db_path=tmp_db)
        q.start_workers(n=n_workers, poll_timeout=poll)
        return q

    def test_simple_success(self, tmp_db):
        q = self._run_queue(tmp_db)
        task = q.enqueue(_ok, 21)
        rec = q.wait_for(task.id, timeout=20)
        q.stop_workers()
        assert rec is not None
        assert rec["status"] == "SUCCESS"
        assert rec["result"] == 42

    def test_multiple_tasks_complete(self, tmp_db):
        q = self._run_queue(tmp_db)
        tasks = [q.enqueue(_ok, i) for i in range(1, 6)]
        results = [q.wait_for(t.id, timeout=20) for t in tasks]
        q.stop_workers()
        assert all(r and r["status"] == "SUCCESS" for r in results)

    def test_dead_letter_after_exhausted_retries(self, tmp_db):
        q = self._run_queue(tmp_db)
        task = q.enqueue(_fail_always, max_retries=2)
        rec = q.wait_for(task.id, timeout=40)
        q.stop_workers()
        assert rec is not None
        assert rec["status"] == "DEAD_LETTER"
        assert rec["retry_count"] == 2

    def test_retry_count_increments(self, tmp_db):
        q = self._run_queue(tmp_db)
        task = q.enqueue(_fail_always, max_retries=2)
        rec = q.wait_for(task.id, timeout=40)
        q.stop_workers()
        assert rec["retry_count"] == 2

    def test_dlq_count_after_failure(self, tmp_db):
        q = self._run_queue(tmp_db)
        q.enqueue(_fail_always, max_retries=1)
        # Wait enough time for retries + DLQ routing
        time.sleep(10)
        q.stop_workers()
        assert q.dlq_count() >= 1

    def test_timeout_causes_retry(self, tmp_db):
        q = self._run_queue(tmp_db, n_workers=1)
        # timeout=0.2s but task sleeps 5s → should fail and retry
        task = q.enqueue(_slow, 5.0, timeout=0.2, max_retries=1)
        rec = q.wait_for(task.id, timeout=30)
        q.stop_workers()
        # After 1 retry it'll go to DLQ or still retry — either way retried
        assert rec is not None
        assert rec["retry_count"] >= 1

    def test_flaky_task_eventually_succeeds(self, tmp_db):
        # Reset the flaky counter for this test key
        key = "flaky_test_key"
        _flaky_count[key] = 0

        q = self._run_queue(tmp_db, n_workers=1)
        task = q.enqueue(_flaky, key, max_retries=3)
        rec = q.wait_for(task.id, timeout=40)
        q.stop_workers()
        assert rec is not None
        assert rec["status"] == "SUCCESS"
        assert rec["result"] == "success"
        assert rec["retry_count"] == 2   # failed twice, succeeded on 3rd attempt

    def test_worker_pool_alive_after_start(self, tmp_db):
        q = self._run_queue(tmp_db, n_workers=3)
        time.sleep(0.5)
        assert q._pool is not None
        assert q._pool.alive_count == 3
        q.stop_workers()

    def test_multiple_queues(self, tmp_db):
        q_alpha = TaskQueue(db_path=tmp_db, queue_name="alpha")
        q_beta  = TaskQueue(db_path=tmp_db, queue_name="beta")

        q_alpha.start_workers(n=1, poll_timeout=0.5)
        q_beta.start_workers(n=1, poll_timeout=0.5)

        t1 = q_alpha.enqueue(_ok, 10)
        t2 = q_beta.enqueue(_ok, 20)

        r1 = q_alpha.wait_for(t1.id, timeout=15)
        r2 = q_beta.wait_for(t2.id, timeout=15)

        q_alpha.stop_workers()
        q_beta.stop_workers()

        assert r1 and r1["result"] == 20
        assert r2 and r2["result"] == 40


# ──────────────────────────────────────────────────────────────────────────────
# 7. Dashboard rendering
# ──────────────────────────────────────────────────────────────────────────────

class TestDashboard:
    def test_render_returns_string(self, backend):
        dash = Dashboard(backend)
        output = dash.render()
        assert isinstance(output, str)

    def test_render_shows_no_tasks(self, backend):
        dash = Dashboard(backend)
        output = dash.render()
        assert "no tasks" in output.lower()

    def test_render_shows_task_id(self, backend):
        task = Task(func=_ok)
        task.status = TaskStatus.SUCCESS
        backend.store(task)
        output = Dashboard(backend).render()
        assert task.id[:6] in output

    def test_render_shows_status(self, backend):
        task = Task(func=_ok)
        task.status = TaskStatus.DEAD_LETTER
        backend.store(task)
        output = Dashboard(backend).render()
        assert "DEAD_LETTER" in output

    def test_render_shows_func_name(self, backend):
        task = Task(func=_ok)
        backend.store(task)
        output = Dashboard(backend).render()
        assert "_ok" in output

    def test_queue_filter(self, backend):
        t1 = Task(func=_ok, queue_name="alpha")
        t2 = Task(func=_ok, queue_name="beta")
        backend.store(t1)
        backend.store(t2)

        dash_alpha = Dashboard(backend, queue_name="alpha")
        output = dash_alpha.render()
        assert "alpha" in output
        # beta task should NOT appear
        assert t2.id[:6] not in output

    def test_summary_counts(self, backend):
        for status in [TaskStatus.SUCCESS, TaskStatus.SUCCESS, TaskStatus.DEAD_LETTER]:
            t = Task(func=_ok)
            t.status = status
            backend.store(t)
        output = Dashboard(backend).render()
        assert "SUCCESS=2" in output
        assert "DEAD_LETTER=1" in output
