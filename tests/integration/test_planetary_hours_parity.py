"""
Integration tests: planetary hour parity between old Gatekeeper and astro_hours.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from astro_hours.chaldean import compute_planetary_hours

OLD_SCRIPT = Path.home() / ".hermes" / "profiles" / "zen-sensei" / "scripts" / "gatekeeper" / "planetary_hours.py"


class TestPlanetaryHoursParity:
    def _cli_hours(self):
        result = subprocess.run(
            [sys.executable, "-m", "astro", "planetary-hours", "--date", "2026-06-28", "--lat", "44.0521", "--lon", "-123.0868", "--json"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    def _old_hours(self):
        result = subprocess.run(
            [sys.executable, str(OLD_SCRIPT), "--date", "2026-06-28", "--lat", "44.0521", "--lon", "-123.0868", "--json"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    def test_library_computes_24_hours(self):
        hours = compute_planetary_hours(
            __import__("datetime").date(2026, 6, 28),
            lat=44.0521,
            lon=-123.0868,
            tz="America/Los_Angeles",
        )
        assert len(hours) == 24

    @pytest.mark.skipif(not OLD_SCRIPT.exists(), reason="old gatekeeper script not present")
    def test_rulers_match_gatekeeper(self):
        new = self._cli_hours()
        old = self._old_hours()
        for n, o in zip(new, old):
            assert n["planet"] == o["planet"], f"hour {n['hour_number']} {n['period']} differs"

    @pytest.mark.skipif(not OLD_SCRIPT.exists(), reason="old gatekeeper script not present")
    def test_transitions_within_one_minute(self):
        new = self._cli_hours()
        old = self._old_hours()
        fmt = "%H:%M"
        for n, o in zip(new, old):
            def to_min(t):
                h, m = map(int, t.split(":"))
                return h * 60 + m
            for key in ("start_time", "end_time"):
                diff = abs(to_min(n[key]) - to_min(o[key]))
                assert diff <= 1, f"{key} differs by {diff} min"

    @pytest.mark.skipif(not OLD_SCRIPT.exists(), reason="old gatekeeper script not present")
    def test_no_hardcoded_chaldean_tables_in_gatekeeper(self):
        # Check that the old script imports from astro_hours rather than defining tables.
        src = OLD_SCRIPT.read_text()
        assert "from astro_hours" in src or "import astro_hours" in src
        assert "chaldean_order" not in src.lower() or "astro_hours.cardinal" in src

    def test_cli_planetary_hours_output_is_json(self):
        hours = self._cli_hours()
        assert isinstance(hours, list)
        assert len(hours) == 24
        assert all("planet" in h for h in hours)
