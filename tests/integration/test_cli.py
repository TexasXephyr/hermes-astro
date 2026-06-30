"""
Integration tests for `python -m astro` CLI.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest


class TestAstroCli:
    def run(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "astro", *args],
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_cli_help_lists_commands(self):
        result = self.run("--help")
        assert result.returncode == 0
        for cmd in ("natal", "transit", "synastry", "period-impact", "luminaries", "planetary-hours", "wheel", "table", "bodies"):
            assert cmd in result.stdout

    def test_cli_natal_output(self):
        result = self.run(
            "natal",
            "--name", "Test",
            "--date", "2000-01-01",
            "--time", "12:00:00",
            "--tz", "UTC",
            "--lat", "0",
            "--lon", "0",
            "--json",
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "ok"

    def test_cli_lat_range(self):
        for lat in ("91", "-91"):
            result = self.run("natal", "--name", "T", "--date", "2000-01-01", "--time", "12:00:00", "--tz", "UTC", "--lat", lat, "--lon", "0")
            assert result.returncode != 0

    def test_cli_lon_range(self):
        for lon in ("181", "-181"):
            result = self.run("natal", "--name", "T", "--date", "2000-01-01", "--time", "12:00:00", "--tz", "UTC", "--lat", "0", "--lon", lon)
            assert result.returncode != 0

    def test_cli_invalid_timezone(self):
        result = self.run("natal", "--name", "T", "--date", "2000-01-01", "--time", "12:00:00", "--tz", "Mars/Phobos", "--lat", "0", "--lon", "0")
        assert result.returncode != 0

    def test_cli_invalid_date(self):
        result = self.run("natal", "--name", "T", "--date", "2026-13-01", "--time", "12:00:00", "--tz", "UTC", "--lat", "0", "--lon", "0")
        assert result.returncode != 0

    def test_cli_output_path_traversal_rejected(self):
        result = self.run("natal", "--name", "T", "--date", "2000-01-01", "--time", "12:00:00", "--tz", "UTC", "--lat", "0", "--lon", "0", "--output", "../escape.txt")
        assert result.returncode != 0

    def test_cli_empty_points_defaults(self):
        result = self.run("natal", "--name", "T", "--date", "2000-01-01", "--time", "12:00:00", "--tz", "UTC", "--lat", "0", "--lon", "0", "--points", "", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data["bodies"]) > 0

    def test_cli_bodies_lists_bodies(self):
        result = self.run("bodies")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert "Sun" in data
        assert "Moon" in data

    def test_cli_planetary_hours(self):
        result = self.run("planetary-hours", "--date", "2026-06-28")
        assert result.returncode == 0
        assert "Saturn" in result.stdout

    def test_cli_luminaries(self):
        # Requires a chart id; create one inline.
        natal = self.run("natal", "--name", "T", "--date", "2000-01-01", "--time", "12:00:00", "--tz", "UTC", "--lat", "0", "--lon", "0", "--json")
        chart_id = json.loads(natal.stdout)["chart_id"]
        result = self.run("luminaries", "--chart-id", chart_id)
        assert result.returncode == 0

    def test_cli_synastry(self):
        natal_a = self.run("natal", "--name", "A", "--date", "2000-01-01", "--time", "12:00:00", "--tz", "UTC", "--lat", "0", "--lon", "0", "--json")
        natal_b = self.run("natal", "--name", "B", "--date", "2000-06-15", "--time", "12:00:00", "--tz", "UTC", "--lat", "0", "--lon", "0", "--json")
        chart_a = json.loads(natal_a.stdout)["chart_id"]
        chart_b = json.loads(natal_b.stdout)["chart_id"]
        result = self.run("synastry", "--person-a", chart_a, "--person-b", chart_b)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"

    def test_cli_period_impact(self):
        natal = self.run("natal", "--name", "T", "--date", "2000-01-01", "--time", "12:00:00", "--tz", "UTC", "--lat", "0", "--lon", "0", "--json")
        chart_id = json.loads(natal.stdout)["chart_id"]
        result = self.run("period-impact", "--chart-id", chart_id, "--date", "2026-06-28")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "impact" in data

    def test_cli_transit(self):
        natal = self.run("natal", "--name", "T", "--date", "2000-01-01", "--time", "12:00:00", "--tz", "UTC", "--lat", "0", "--lon", "0", "--json")
        chart_id = json.loads(natal.stdout)["chart_id"]
        result = self.run("transit", "--chart-id", chart_id, "--date", "2026-06-28")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"

    def test_cli_wheel_writes_svg(self, tmp_path):
        natal = self.run("natal", "--name", "T", "--date", "2000-01-01", "--time", "12:00:00", "--tz", "UTC", "--lat", "0", "--lon", "0", "--json")
        chart_id = json.loads(natal.stdout)["chart_id"]
        out = tmp_path / "wheel.svg"
        result = self.run("wheel", "--chart-id", chart_id, "--output", str(out))
        assert result.returncode == 0
        assert out.exists()
        text = out.read_text()
        assert text.startswith("<?xml") or "<svg" in text

    def test_cli_table_writes_text(self, tmp_path):
        natal = self.run("natal", "--name", "T", "--date", "2000-01-01", "--time", "12:00:00", "--tz", "UTC", "--lat", "0", "--lon", "0", "--json")
        chart_id = json.loads(natal.stdout)["chart_id"]
        out = tmp_path / "table.txt"
        result = self.run("table", "--chart-id", chart_id, "--output", str(out))
        assert result.returncode == 0
        assert out.exists()
        text = out.read_text()
        assert "Chart Table" in text
        assert "Sun" in text
        assert "Moon" in text
