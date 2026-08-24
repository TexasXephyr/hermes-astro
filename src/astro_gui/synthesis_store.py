"""synthesis_store.py — SQLite-backed chart synthesis queue (library DB).

The `syntheses` table lives in the same library DB as `charts`
(~/.cache/astro/library.db) so the GUI (system python) and the
zen-sensei cron worker (Hermes venv, stdlib-only script) can both reach
it without any server or webhook.

Flow:
  1. GUI "Synthesize" -> request_synthesis(...) inserts a row with
     status='pending' and the cookbook payload (snapshot + phrases).
  2. zen-sensei cron (scripts/synthesis_queue.py in the cookbook repo)
     fetches pending rows, the agent writes a report, mark_done() stores
     it and sets status='done'.
  3. GUI "Synthesis" -> latest_synthesis(...) shows the report.

The table schema is duplicated in the standalone worker script by
design (the worker must not import this module — it runs outside the
astro src tree).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS syntheses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    cookbook_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    report TEXT,
    error TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
)
"""


def library_db_path() -> Path:
    return Path.home() / ".cache" / "astro" / "library.db"


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or library_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def request_synthesis(chart_id: str, mode: str, label: str,
                      cookbook: dict, db_path: Path | None = None) -> int:
    """Insert a pending synthesis request; returns the new row id."""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO syntheses (chart_id, mode, label, cookbook_json, status) "
            "VALUES (?, ?, ?, ?, 'pending')",
            (chart_id, mode, label, json.dumps(cookbook, default=str)),
        )
        conn.commit()
        assert cur.lastrowid is not None  # sqlite3 always sets it after INSERT
        return cur.lastrowid
    finally:
        conn.close()


def latest_synthesis(chart_id: str, mode: str,
                     db_path: Path | None = None) -> dict | None:
    """Most recent synthesis row for a chart+mode, or None."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT id, chart_id, mode, label, cookbook_json, status, report, error, "
            "created_at, completed_at FROM syntheses "
            "WHERE chart_id = ? AND mode = ? ORDER BY id DESC LIMIT 1",
            (chart_id, mode),
        ).fetchone()
        if row is None:
            return None
        cols = ["id", "chart_id", "mode", "label", "cookbook_json",
                "status", "report", "error", "created_at", "completed_at"]
        return dict(zip(cols, row))
    finally:
        conn.close()


def list_syntheses(chart_id: str, mode: str | None = None,
                   db_path: Path | None = None) -> list[dict]:
    """All synthesis rows for a chart, newest first."""
    conn = _connect(db_path)
    try:
        if mode:
            rows = conn.execute(
                "SELECT id, chart_id, mode, label, cookbook_json, status, report, "
                "error, created_at, completed_at FROM syntheses "
                "WHERE chart_id = ? AND mode = ? ORDER BY id DESC",
                (chart_id, mode),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, chart_id, mode, label, cookbook_json, status, report, "
                "error, created_at, completed_at FROM syntheses "
                "WHERE chart_id = ? ORDER BY id DESC",
                (chart_id,),
            ).fetchall()
        cols = ["id", "chart_id", "mode", "label", "cookbook_json",
                "status", "report", "error", "created_at", "completed_at"]
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()


def pending_syntheses(db_path: Path | None = None) -> list[dict]:
    """All rows still awaiting the zen-sensei worker."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, chart_id, mode, label, cookbook_json, status, report, "
            "error, created_at FROM syntheses WHERE status = 'pending' ORDER BY id",
        ).fetchall()
        cols = ["id", "chart_id", "mode", "label", "cookbook_json",
                "status", "report", "error", "created_at"]
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()


def mark_done(synthesis_id: int, report: str, db_path: Path | None = None) -> bool:
    """Mark a row done with its report. Returns True when the row existed."""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "UPDATE syntheses SET status = 'done', report = ?, "
            "completed_at = datetime('now') WHERE id = ?",
            (report, synthesis_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def mark_error(synthesis_id: int, error: str, db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE syntheses SET status = 'error', error = ?, "
            "completed_at = datetime('now') WHERE id = ?",
            (error, synthesis_id),
        )
        conn.commit()
    finally:
        conn.close()
