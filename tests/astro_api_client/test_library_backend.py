"""
Unit tests for the library-first AstroClient facade.
These tests must pass with no localhost:8081 server running.
"""
import os
from unittest.mock import patch

import pytest

from astro_api_client import AstroClient


class TestAstroClientLibraryBackend:
    def test_default_backend_is_library(self):
        client = AstroClient()
        assert client.backend == "library"

    def test_env_var_selects_http(self):
        with patch.dict(os.environ, {"ASTRO_API_URL": "http://localhost:8081"}):
            client = AstroClient()
            assert client.backend == "http"

    def test_explicit_http_backend(self):
        client = AstroClient(backend="http", base_url="http://localhost:8081")
        assert client.backend == "http"

    def test_natal_computes_without_server(self):
        client = AstroClient()
        result = client.natal(
            name="Test",
            date="2000-01-01",
            time="12:00:00",
            timezone="UTC",
            latitude=0.0,
            longitude=0.0,
        )
        assert result["status"] == "ok"
        assert "chart_id" in result
        assert "bodies" in result
        assert "houses" in result
        assert "angles" in result
        assert "aspects" in result

    def test_transit_computes_without_server(self):
        client = AstroClient()
        natal = client.natal(
            name="Test",
            date="2000-01-01",
            time="12:00:00",
            timezone="UTC",
            latitude=0.0,
            longitude=0.0,
        )
        chart_id = natal["chart_id"]
        transit = client.transit(chart_id, "2026-06-28")
        assert transit["status"] == "ok"
        assert "bodies" in transit

    def test_period_impact_computes_without_server(self):
        client = AstroClient()
        natal = client.natal(
            name="Test",
            date="2000-01-01",
            time="12:00:00",
            timezone="UTC",
            latitude=0.0,
            longitude=0.0,
        )
        impact = client.period_impact(natal["chart_id"], "2026-06-28", orb_days=7)
        assert "impact" in impact
        assert "active_transits" in impact["impact"]

    def test_invalid_lat_raises(self):
        client = AstroClient()
        with pytest.raises(ValueError):
            client.natal(name="Test", date="2000-01-01", time="12:00:00", timezone="UTC", latitude=91.0, longitude=0.0)

    def test_invalid_lon_raises(self):
        client = AstroClient()
        with pytest.raises(ValueError):
            client.natal(name="Test", date="2000-01-01", time="12:00:00", timezone="UTC", latitude=0.0, longitude=181.0)

    def test_invalid_timezone_raises(self):
        client = AstroClient()
        with pytest.raises(ValueError):
            client.natal(name="Test", date="2000-01-01", time="12:00:00", timezone="Mars/Phobos", latitude=0.0, longitude=0.0)

    def test_missing_chart_id_raises(self):
        client = AstroClient()
        with pytest.raises((KeyError, ValueError)):
            client.get_chart("nonexistent-uuid-1234")

    def test_invalid_uuid_raises(self):
        client = AstroClient()
        with pytest.raises(ValueError):
            client.get_chart("not-a-uuid")
