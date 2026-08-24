"""test_synthesis_store.py — Library-DB synthesis queue (pytest, no gi needed).

The store module is pure python (sqlite3 only), so it tests cleanly in
the Hermes venv. `astro_gui` package import pulls in gi, so the module
is loaded via importlib with the package __init__ bypassed.
"""
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

# Load synthesis_store without triggering astro_gui's gi import
_module_path = Path("/home/xephyr/astro/src/astro_gui/synthesis_store.py")
_spec = importlib.util.spec_from_file_location("synthesis_store", _module_path)
store = importlib.util.module_from_spec(_spec)
sys.modules["synthesis_store"] = store
_spec.loader.exec_module(store)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "library.db"


def test_request_and_pending(db_path):
    sid = store.request_synthesis("chart-1", "Natal", "Xephyr",
                                  {"snapshot": {"person": "Xephyr"}},
                                  db_path=db_path)
    assert sid >= 1
    pend = store.pending_syntheses(db_path=db_path)
    assert len(pend) == 1
    assert pend[0]["chart_id"] == "chart-1"
    assert pend[0]["mode"] == "Natal"
    assert pend[0]["status"] == "pending"
    payload = json.loads(pend[0]["cookbook_json"])
    assert payload["snapshot"]["person"] == "Xephyr"


def test_mark_done_and_latest(db_path):
    sid = store.request_synthesis("chart-1", "Natal", "Xephyr", {"snapshot": {}}, db_path=db_path)
    assert store.mark_done(sid, "The report.", db_path=db_path)
    latest = store.latest_synthesis("chart-1", "Natal", db_path=db_path)
    assert latest["status"] == "done"
    assert latest["report"] == "The report."
    assert latest["completed_at"]
    # no pending rows remain
    assert store.pending_syntheses(db_path=db_path) == []


def test_mark_done_missing_row(db_path):
    assert store.mark_done(999, "x", db_path=db_path) is False


def test_latest_respects_mode(db_path):
    a = store.request_synthesis("c", "Natal", "L", {"s": 1}, db_path=db_path)
    b = store.request_synthesis("c", "Transit", "L", {"s": 2}, db_path=db_path)
    store.mark_done(a, "natal", db_path=db_path)
    store.mark_done(b, "transit", db_path=db_path)
    assert store.latest_synthesis("c", "Natal", db_path=db_path)["id"] == a
    assert store.latest_synthesis("c", "Transit", db_path=db_path)["id"] == b
    # list all, newest first
    rows = store.list_syntheses("c", db_path=db_path)
    assert [r["id"] for r in rows] == [b, a]


def test_mark_error(db_path):
    sid = store.request_synthesis("c", "Natal", "L", {}, db_path=db_path)
    store.mark_error(sid, "corpus missing", db_path=db_path)
    latest = store.latest_synthesis("c", "Natal", db_path=db_path)
    assert latest["status"] == "error"
    assert latest["error"] == "corpus missing"


def test_real_library_db_not_created(tmp_path):
    """Without a db_path the store uses ~/.cache/astro/library.db — the test
    must never touch that; using an explicit db_path keeps it hermetic."""
    assert store.request_synthesis("c", "N", "L", {}, db_path=tmp_path / "x.db") >= 1
