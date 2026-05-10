"""
tqueue/dashboard.py
────────────────────
Terminal dashboard rendering.

Produces a formatted table of all task results — no external dependencies
(uses only the standard library).

    from tqueue.dashboard import Dashboard

    dash = Dashboard(result_backend)
    dash.print_table()          # one-shot snapshot
    dash.watch(refresh=2.0)     # live-updating loop (Ctrl-C to exit)
"""

from __future__ import annotations

import os
import time
from typing import Optional

from .result_backend import ResultBackend
from .task import TaskStatus


# ──────────────────────────────────────────────────────────────────────────────
# ANSI colour helpers
# ──────────────────────────────────────────────────────────────────────────────

_ANSI_RESET  = "\033[0m"
_ANSI_BOLD   = "\033[1m"
_ANSI_DIM    = "\033[2m"

_STATUS_COLOURS = {
    TaskStatus.PENDING.value:     "\033[33m",   # yellow
    TaskStatus.RUNNING.value:     "\033[36m",   # cyan
    TaskStatus.RETRYING.value:    "\033[35m",   # magenta
    TaskStatus.SUCCESS.value:     "\033[32m",   # green
    TaskStatus.FAILED.value:      "\033[31m",   # red
    TaskStatus.DEAD_LETTER.value: "\033[91m",   # bright red
}


def _colour(status: str, text: str) -> str:
    c = _STATUS_COLOURS.get(status, "")
    return f"{c}{text}{_ANSI_RESET}"


def _fmt_duration(duration) -> str:
    if duration is None:
        return "—"
    return f"{float(duration):.2f}s"


def _fmt_result(result, status: str) -> str:
    if status == TaskStatus.DEAD_LETTER.value:
        return "—"
    if result is None:
        return ""
    s = repr(result)
    return s[:40] + "…" if len(s) > 40 else s


# ──────────────────────────────────────────────────────────────────────────────
# Dashboard
# ──────────────────────────────────────────────────────────────────────────────

class Dashboard:
    """
    Renders a live-updating terminal table of task records.

    Parameters
    ----------
    result_backend : ResultBackend
        Source of task records.
    queue_name : str | None
        Filter to a specific queue; None shows all queues.
    """

    _COLS = [
        ("Task ID",  8),
        ("Function", 22),
        ("Queue",    10),
        ("Status",   12),
        ("Retries",   8),
        ("Duration",  9),
        ("Result",   42),
    ]

    def __init__(
        self,
        result_backend: ResultBackend,
        queue_name: Optional[str] = None,
    ) -> None:
        self.backend    = result_backend
        self.queue_name = queue_name

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _records(self) -> list[dict]:
        recs = self.backend.all_records()
        if self.queue_name:
            recs = [r for r in recs if r.get("queue_name") == self.queue_name]
        return recs

    def _header(self) -> str:
        parts = [f"{_ANSI_BOLD}{name:<{w}}{_ANSI_RESET}" for name, w in self._COLS]
        sep   = "-+-".join("-" * w for _, w in self._COLS)
        return " | ".join(parts) + "\n" + sep

    def _row(self, rec: dict) -> str:
        status   = rec.get("status", "")
        retries  = rec.get("retry_count", 0)
        max_r    = rec.get("max_retries", 3)
        duration = _fmt_duration(rec.get("duration"))
        result   = _fmt_result(rec.get("result"), status)

        cells = [
            rec.get("id", "")[:8],
            rec.get("func_name", "")[:22],
            rec.get("queue_name", "")[:10],
            _colour(status, f"{status:<12}"),
            f"{retries}/{max_r}",
            duration,
            result,
        ]
        widths = [w for _, w in self._COLS]

        # Status cell already has ANSI codes — pad raw width
        plain_status = f"{status:<12}"
        padded = []
        for i, (cell, w) in enumerate(zip(cells, widths)):
            if i == 3:   # status column — already coloured
                padded.append(cell + " " * max(0, w - len(plain_status)))
            else:
                padded.append(f"{str(cell):<{w}}"[:w])
        return " | ".join(padded)

    def _summary(self, recs: list[dict]) -> str:
        counts = {}
        for r in recs:
            s = r.get("status", "?")
            counts[s] = counts.get(s, 0) + 1
        parts = [f"{s}={n}" for s, n in sorted(counts.items())]
        return "  ".join(parts)

    def render(self) -> str:
        """Return the full dashboard as a string."""
        recs = self._records()
        lines = [
            f"\n{_ANSI_BOLD}=== Task Queue Dashboard ==={_ANSI_RESET}",
            f"  {len(recs)} tasks  |  {self._summary(recs)}",
            "",
            self._header(),
        ]
        if not recs:
            lines.append(f"{'(no tasks yet)':<{sum(w for _,w in self._COLS)}}")
        else:
            for rec in recs:
                lines.append(self._row(rec))

        sep = "-+-".join("-" * w for _, w in self._COLS)
        lines.append(sep)
        return "\n".join(lines) + "\n"

    def print_table(self) -> None:
        """Print a one-shot snapshot of the dashboard."""
        print(self.render())

    def watch(self, refresh: float = 2.0) -> None:
        """
        Print a continuously-updating dashboard.

        Clears the terminal on each refresh.  Press Ctrl-C to exit.
        """
        try:
            while True:
                # Clear terminal — 'cls' on Windows, 'clear' on Unix
                os.system("cls" if os.name == "nt" else "clear")
                print(self.render())
                print(f"  Refreshing every {refresh}s — Ctrl-C to exit")
                time.sleep(refresh)
        except KeyboardInterrupt:
            print("\nDashboard stopped.")
