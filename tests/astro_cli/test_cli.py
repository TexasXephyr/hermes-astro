"""Tests for `python -m astro` CLI."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


class TestAstroCli:
    @staticmethod
    def _run(*args, env=None):
        if env is None:
            env = os.environ.copy()
            env.setdefault("PYTHONPATH", str(Path(__file__).parent.parent.parent / "src"))
        return subprocess.run(
            [sys.executable, "-m", "astro", *args],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )

    def test_cli_natal_writes_json(self):
        result = self._run(
            "natal",
            "--name", "Test",
            "--date", "2000-01-01",
            "--time", "12:00:00",
            "--timezone", "UTC",
            "--latitude", "0",
            "--longitude", "0",
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert "chart_id" in data
        assert "bodies" in data

    def test_cli_invalid_latitude(self):
        result = self._run(
            "natal",
            "--name", "T",
            "--date", "2000-01-01",
            "--time", "12:00:00",
            "--timezone", "UTC",
            "--latitude", "91",
            "--longitude", "0",
        )
        assert result.returncode == 1
        assert "latitude" in result.stderr.lower()

    def test_cli_invalid_timezone(self):
        result = self._run(
            "natal",
            "--name", "T",
            "--date", "2000-01-01",
            "--time", "12:00:00",
            "--timezone", "Mars/Phobos",
            "--latitude", "0",
            "--longitude", "0",
        )
        assert result.returncode == 1

    def test_cli_output_path_traversal_rejected(self):
        result = self._run(
            "natal",
            "--name", "T",
            "--date", "2000-01-01",
            "--time", "12:00:00",
            "--timezone", "UTC",
            "--latitude", "0",
            "--longitude", "0",
            "--output", "../escape.txt",
        )
        assert result.returncode == 1

    def test_cli_planetary_hours(self):
        result = self._run(
            "planetary-hours",
            "--date", "2026-06-29",
            "--timezone", "UTC",
            "--latitude", "0",
            "--longitude", "0",
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 24

    def test_cli_wheel_renders_svg(self):
        result = self._run(
            "wheel",
            "--name", "T",
            "--date", "2000-01-01",
            "--time", "12:00:00",
            "--timezone", "UTC",
            "--latitude", "0",
            "--longitude", "0",
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip().startswith("<svg")

    def test_cli_table(self):
        result = self._run(
            "table",
            "--name", "T",
            "--date", "2000-01-01",
            "--time", "12:00:00",
            "--timezone", "UTC",
            "--latitude", "0",
            "--longitude", "0",
        )
        assert result.returncode == 0, result.stderr
        assert "Sun" in result.stdout

    def test_cli_luminaries_json(self):
        result = self._run(
            "luminaries",
            "--date", "2026-06-29",
            "--time", "12:00:00",
            "--timezone", "UTC",
            "--latitude", "0",
            "--longitude", "0",
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert "sun" in data
        assert "moon" in data
        assert "moon_phase" in data

    def test_cli_transit_by_chart_id(self):
        natal = self._run(
            "natal",
            "--name", "T",
            "--date", "2000-01-01",
            "--time", "12:00:00",
            "--timezone", "UTC",
            "--latitude", "0",
            "--longitude", "0",
        )
        chart_id = json.loads(natal.stdout)["chart_id"]
        result = self._run("transit", "--chart-id", chart_id, "--date", "2026-06-29")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "ok"

    def test_cli_period_impact_by_chart_id(self):
        natal = self._run(
            "natal",
            "--name", "T",
            "--date", "2000-01-01",
            "--time", "12:00:00",
            "--timezone", "UTC",
            "--latitude", "0",
            "--longitude", "0",
        )
        chart_id = json.loads(natal.stdout)["chart_id"]
        result = self._run("period-impact", "--chart-id", chart_id, "--date", "2026-06-29")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert "impact" in data

    def test_cli_synastry_by_chart_id(self):
        natal_a = self._run(
            "natal",
            "--name", "A",
            "--date", "2000-01-01",
            "--time", "12:00:00",
            "--timezone", "UTC",
            "--latitude", "0",
            "--longitude", "0",
        )
        natal_b = self._run(
            "natal",
            "--name", "B",
            "--date", "2000-06-15",
            "--time", "12:00:00",
            "--timezone", "UTC",
            "--latitude", "0",
            "--longitude", "0",
        )
        chart_a = json.loads(natal_a.stdout)["chart_id"]
        chart_b = json.loads(natal_b.stdout)["chart_id"]
        result = self._run("synastry", "--chart-id-a", chart_a, "--chart-id-b", chart_b)
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert "cross_aspects" in data
