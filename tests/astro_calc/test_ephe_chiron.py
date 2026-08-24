"""test_ephe_chiron.py — Chiron/minor-body ephemeris regression (pytest).

The 2026-08-24 bug: ac_init() fell back to Moshier's built-in ephemeris,
which cannot compute minor bodies (Chiron, Lilith, Ceres...). The C
wrapper zero-filled the failed body, and the client rendered it as a
bogus "0.00 Aries" planet regardless of date.

Fixes under test:
1. ac_init() resolves a full Swiss Ephemeris data dir by default.
2. ac_calc_chart drops zero-filled failed bodies instead of emitting them.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from astro_calc.astro_ctypes import (
    ac_init,
    ac_calc_chart,
    ac_date_to_jd,
    AC_CHIRON,
    _default_ephe_path,
)


def test_default_ephe_path_resolves():
    path = _default_ephe_path()
    assert path, "expected a full ephemeris directory on this machine"
    assert Path(path).is_dir()


def test_chiron_computes_with_full_ephe():
    # Chiron around 2026-08-24 is ~30.7° Taurus (retrograde), NOT 0 Aries
    jd = ac_date_to_jd(2026, 8, 24, 12, 0, 0, 0.0)
    chart = ac_calc_chart(jd, 44.05, -123.08, [AC_CHIRON], "K")
    bodies = chart["bodies"]
    assert len(bodies) == 1, f"expected 1 body, got {len(bodies)}"
    chiron = bodies[0]
    assert chiron["longitude"] > 0, f"Chiron still zero: {chiron}"
    assert chiron["distance"] > 0, "Chiron has zero distance (fake body)"
    assert 20 < chiron["longitude"] < 45, f"unexpected Chiron lon {chiron['longitude']}"


def test_chiron_moves_across_dates():
    dates = [(1980, 6, 15), (1999, 1, 1), (2026, 8, 24)]
    lons = []
    for y, m, d in dates:
        jd = ac_date_to_jd(y, m, d, 12, 0, 0, 0.0)
        chart = ac_calc_chart(jd, 44.05, -123.08, [AC_CHIRON], "K")
        bodies = chart["bodies"]
        assert bodies, f"Chiron missing for {y}-{m}-{d}"
        lons.append(bodies[0]["longitude"])
    assert len(set(round(v, 1) for v in lons)) >= 2, "Chiron did not move between dates"


def test_zero_filled_bodies_dropped(monkeypatch):
    # Force a failing ephemeris so the C layer zero-fills.
    original = _default_ephe_path()
    monkeypatch.setattr("astro_calc.astro_ctypes._default_ephe_path", lambda: None)
    ac_init(None)  # Moshier fallback: Chiron unsupported
    try:
        jd = ac_date_to_jd(2026, 8, 24, 12, 0, 0, 0.0)
        chart = ac_calc_chart(jd, 44.05, -123.08, [AC_CHIRON], "K")
        # With the guard, a failed body is dropped, not served as 0.00 Aries.
        assert chart["bodies"] == [], f"zero-filled body leaked: {chart['bodies']}"
    finally:
        # Restore the full ephemeris for the rest of the test process —
        # the C-level swe_set_ephe_path state survives monkeypatch teardown.
        ac_init(original)
