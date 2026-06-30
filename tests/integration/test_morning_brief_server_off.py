"""
Integration tests: morning-brief producers run server-off.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

MORNING_BRIEF_PRODUCER = Path.home() / ".hermes" / "scripts" / "morning_brief_producer.py"
MORNING_BRIEF_CONSOLIDATED = Path.home() / ".hermes" / "scripts" / "morning_brief_consolidated.py"
CANONICAL_PRODUCER = Path.home() / ".hermes" / "skill_library" / "executive-transit-report" / "scripts" / "canonical_astro_producer.py"
BASELINE = Path(__file__).parent.parent / "fixtures" / "morning_brief_baseline.txt"


class TestMorningBriefServerOff:
    @pytest.mark.skipif(not MORNING_BRIEF_PRODUCER.exists(), reason="producer not present")
    def test_morning_brief_producer_runs_server_off(self):
        result = subprocess.run(
            [sys.executable, str(MORNING_BRIEF_PRODUCER), "--dry-run", "--date", "2026-06-02"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert "localhost:8081" not in result.stderr, "producer still calls HTTP server"
        assert "urllib.error.URLError" not in result.stderr

    @pytest.mark.skipif(not MORNING_BRIEF_PRODUCER.exists(), reason="producer not present")
    def test_no_hardcoded_symbol_tables(self):
        src = MORNING_BRIEF_PRODUCER.read_text()
        hardcoded = [
            "TRADITIONAL_RULERSHIP",
            "MODERN_RULERSHIP",
            "PLANET_SYM",
            "SYM =",
            "DIGNITY =",
        ]
        for token in hardcoded:
            assert token not in src, f"producer still contains hardcoded table: {token}"
        assert "from astro_text" in src or "import astro_text" in src

    @pytest.mark.skipif(not CANONICAL_PRODUCER.exists(), reason="canonical producer not present")
    def test_canonical_astro_producer_runs_server_off(self):
        result = subprocess.run(
            [sys.executable, str(CANONICAL_PRODUCER), "--dry-run"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert "localhost:8081" not in result.stderr

    @pytest.mark.skipif(not MORNING_BRIEF_CONSOLIDATED.exists(), reason="consolidated not present")
    def test_consolidated_fetches_astrology_state(self):
        result = subprocess.run(
            [sys.executable, str(MORNING_BRIEF_CONSOLIDATED), "--dry-run"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert "localhost:8081" not in result.stderr

    @pytest.mark.skipif(not BASELINE.exists(), reason="baseline not captured")
    def test_output_matches_baseline(self, tmp_path):
        # Run producer capturing output.
        result = subprocess.run(
            [sys.executable, str(MORNING_BRIEF_PRODUCER), "--dry-run", "--date", "2026-06-02", "--output", str(tmp_path / "brief.md")],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0
        produced = Path(tmp_path / "brief.md").read_text()
        baseline = BASELINE.read_text()
        # Tolerant: normalize whitespace and ignore line-specific date/moon degrees.
        a = re.sub(r"\d{4}-\d{2}-\d{2}", "DATE", produced)
        b = re.sub(r"\d{4}-\d{2}-\d{2}", "DATE", baseline)
        assert a == b
