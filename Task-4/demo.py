"""
Task-4/demo.py
==============
End-to-end demonstration of the distributed task queue.

Sections
--------
  1. Simulated task functions
  2. Broker and result backend setup
  3. Producer: enqueue tasks
  4. Worker pool: spawn consumer processes
  5. Wait for completion
  6. Dashboard: view results

All state is stored in 'demo_queue.db' (SQLite) — deleted before each run.
No Redis required.

Run with:
    python demo.py
"""

from __future__ import annotations

# ── Guard: multiprocessing requires __main__ guard on Windows ─────────────────
import multiprocessing
multiprocessing.freeze_support()

import os
import sys
import time

# Ensure UTF-8 output on Windows
import io
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ── Helpers ───────────────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(__file__), "demo_queue.db")

def banner(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)

def sub(title: str) -> None:
    print(f"\n-- {title} {'-' * max(0, 62 - len(title))}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Simulated task functions
#    (must be module-level so pickle can serialise them)
# ─────────────────────────────────────────────────────────────────────────────

import random

def generate_thumbnail(image_id: int, size: tuple) -> str:
    """Simulate image resizing — always succeeds."""
    time.sleep(random.uniform(0.3, 0.8))
    return f"/thumbs/{image_id}_{size[0]}x{size[1]}.jpg"


_send_email_call_counts: dict = {}   # track per-task retries via a module-level dict

def send_email(to: str, template: str) -> str:
    """Simulate sending email — fails the first 2 attempts."""
    key = f"{to}:{template}"
    _send_email_call_counts[key] = _send_email_call_counts.get(key, 0) + 1
    attempt = _send_email_call_counts[key]

    if attempt <= 2:
        raise ConnectionError(f"SMTPConnectionError (simulated attempt {attempt})")

    time.sleep(0.4)
    return "email_sent"


_report_call_count = 0

def generate_report(report_type: str) -> str:
    """Simulate a task that ALWAYS fails (will end up in DLQ)."""
    global _report_call_count
    _report_call_count += 1
    raise RuntimeError(f"ReportGenerationError: service unavailable (attempt {_report_call_count})")


def add_numbers(a: int, b: int) -> int:
    """Simple arithmetic — always succeeds instantly."""
    time.sleep(0.05)
    return a + b


def slow_task(duration: float) -> str:
    """Task that will exceed its timeout."""
    time.sleep(duration)
    return "done"


def fetch_data(url: str) -> dict:
    """Simulate a data-fetch task."""
    time.sleep(random.uniform(0.1, 0.3))
    return {"url": url, "status": 200, "bytes": random.randint(1000, 50000)}


# ─────────────────────────────────────────────────────────────────────────────
# Main demo
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    from tqueue import TaskQueue, Dashboard

    # Clean slate
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    # ── Setup ─────────────────────────────────────────────────────────────────

    banner("Setup — Broker + Result Backend (SQLite)")

    queue = TaskQueue(
        db_path        = DB_PATH,
        queue_name     = "default",
    )
    print(f"Broker:         {queue.broker!r}")
    print(f"Result backend: {queue.result_backend!r}")
    print(f"Queue name:     '{queue.queue_name}'")

    # Convenience aliases for the demo
    broker  = queue.broker
    backend = queue.result_backend

    # ── Producer ──────────────────────────────────────────────────────────────

    banner("Producer — Enqueuing Tasks")

    sub("Always-success tasks")
    t_thumb = queue.enqueue(generate_thumbnail, 4521, (256, 256))
    t_add   = queue.enqueue(add_numbers, 17, 25)
    t_fetch = queue.enqueue(fetch_data, "https://api.example.com/data")

    sub("Flaky task — will retry twice, then succeed (max_retries=3)")
    t_email = queue.enqueue(send_email, template="welcome", to="bob@co.com", max_retries=3)

    sub("Always-failing task — will exhaust retries and go to DLQ (max_retries=3)")
    t_report = queue.enqueue(generate_report, "quarterly", max_retries=3)

    sub("Timeout task — will time out and retry")
    t_slow = queue.enqueue(slow_task, 10.0, timeout=0.5, max_retries=2)

    all_tasks = [t_thumb, t_add, t_fetch, t_email, t_report, t_slow]

    print(f"\nEnqueued {len(all_tasks)} tasks")
    print(f"Pending in broker: {queue.pending_count()}")

    # ── Workers ───────────────────────────────────────────────────────────────

    banner("Workers — Starting Worker Pool (3 processes)")

    queue.start_workers(n=3, poll_timeout=1.0)
    print(f"Worker pool alive")

    # ── Wait for completion ───────────────────────────────────────────────────

    banner("Waiting for All Tasks to Complete")

    terminal_statuses = {"SUCCESS", "DEAD_LETTER"}
    max_wait = 60          # seconds
    start    = time.time()

    print("Polling results ...")
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        elapsed = time.time() - start

        records = backend.all_records()
        done    = sum(1 for r in records if r.get("status") in terminal_statuses)
        total   = len(all_tasks)

        # Print progress bar
        bar_len = 30
        filled  = int(bar_len * done / max(total, 1))
        bar     = "#" * filled + "." * (bar_len - filled)
        print(
            f"\r  [{bar}] {done}/{total} done  ({elapsed:.1f}s elapsed)",
            end="", flush=True
        )

        if done >= total:
            print()
            break

        time.sleep(0.5)
    else:
        print(f"\n[!] Timeout after {max_wait}s")

    # Extra wait to let result backend writes settle
    time.sleep(0.5)

    # ── Stop workers ──────────────────────────────────────────────────────────

    banner("Stopping Worker Pool")
    queue.stop_workers(timeout=4.0)

    # ── Dashboard ─────────────────────────────────────────────────────────────

    banner("Dashboard — Final Task Status")
    dash = Dashboard(backend)
    dash.print_table()

    # ── Detailed results ──────────────────────────────────────────────────────

    banner("Detailed Results per Task")

    labels = {
        t_thumb.id:  "generate_thumbnail",
        t_add.id:    "add_numbers",
        t_fetch.id:  "fetch_data",
        t_email.id:  "send_email (flaky)",
        t_report.id: "generate_report (DLQ)",
        t_slow.id:   "slow_task (timeout)",
    }

    for task_id, label in labels.items():
        rec = backend.fetch(task_id)
        if rec is None:
            print(f"\n  [{task_id}] {label}  →  (no record found)")
            continue

        status   = rec.get("status", "?")
        retries  = rec.get("retry_count", 0)
        max_r    = rec.get("max_retries", "?")
        duration = rec.get("duration")
        result   = rec.get("result")
        error    = rec.get("error")

        print(f"\n  [{task_id}] {label}")
        print(f"    Status:   {status}")
        print(f"    Retries:  {retries}/{max_r}")
        print(f"    Duration: {f'{duration:.3f}s' if duration else '—'}")
        if result is not None:
            print(f"    Result:   {result!r}")
        if error and status == "DEAD_LETTER":
            # Print just the last line of the traceback
            last_line = [l for l in error.splitlines() if l.strip()]
            print(f"    Error:    {last_line[-1] if last_line else error[:80]}")

    # ── Broker stats ──────────────────────────────────────────────────────────

    banner("Broker Statistics")
    print(f"  Pending in main queue : {queue.pending_count()}")
    print(f"  Items in DLQ          : {queue.dlq_count()}")

    # ── Exponential backoff demo ───────────────────────────────────────────────

    banner("Exponential Backoff Illustration")
    from tqueue.task import exponential_backoff

    print("  attempt | delay (with jitter=False)")
    print("  --------+----------------------------")
    for i in range(6):
        d = exponential_backoff(i, jitter=False)
        bar = "#" * int(d / 2)
        print(f"  {i:7d} | {d:5.1f}s  {bar}")

    # ── Serialisation round-trip ───────────────────────────────────────────────

    banner("Task Serialisation Round-Trip (pickle)")
    original = t_thumb
    raw      = original.to_bytes()
    restored = type(original).from_bytes(raw)

    print(f"  Original : {original!r}")
    print(f"  Restored : {restored!r}")
    print(f"  id match : {original.id == restored.id}")
    print(f"  func match: {original.func_name == restored.func_name}")
    print(f"  Wire size: {len(raw)} bytes")

    print()
    print("=" * 70)
    print("  [OK] Demo complete.")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
