#!/usr/bin/env python3
"""
Phase 7 Tests: Pluggable synthesis engine with rules-based and LLM providers.
Run with: python3 tests/test_phase7.py -v
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from astro_api.astro_ctypes import (
    ac_init,
    ac_date_to_jd,
    ac_calc_chart,
    calculate_aspects,
    body_id_from_name,
    orb_preset_from_name,
)
from astro_analyze.analysis import analyze_chart
from astro_analyze.synthesis import (
    RulesProvider,
    LLMProvider,
    SynthesisProvider,
    get_provider,
)


class TestRulesProvider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ac_init()
        jd = ac_date_to_jd(1969, 11, 30, 20, 43, 0, -6.0)
        points = [
            "Sun", "Moon", "Mercury", "Venus", "Mars",
            "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
            "Mean Node", "Chiron",
        ]
        body_ids = [body_id_from_name(p) for p in points]
        chart = ac_calc_chart(jd, 35.2167, -101.8167, body_ids, "K")
        aspects = calculate_aspects(chart["bodies"], orb_preset_from_name("Modern"))
        chart["aspects"] = aspects
        cls.xephyr_analysis = analyze_chart(chart)

    def test_generates_non_empty_text(self):
        provider = RulesProvider()
        text = provider.generate(self.xephyr_analysis)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 100)

    def test_contains_dignities_section(self):
        text = RulesProvider().generate(self.xephyr_analysis)
        self.assertIn("Dignities", text)

    def test_contains_patterns_section(self):
        text = RulesProvider().generate(self.xephyr_analysis)
        self.assertIn("Patterns", text)

    def test_contains_house_emphasis(self):
        text = RulesProvider().generate(self.xephyr_analysis)
        self.assertIn("House", text)

    def test_contains_element_balance(self):
        text = RulesProvider().generate(self.xephyr_analysis)
        self.assertIn("Elements", text)

    def test_mentions_stellium(self):
        text = RulesProvider().generate(self.xephyr_analysis)
        self.assertIn("Stellium", text)

    def test_empty_analysis_returns_text(self):
        text = RulesProvider().generate({})
        self.assertIsInstance(text, str)
        self.assertIn("planetary bodies", text)


class TestLLMProvider(unittest.TestCase):
    def test_unreachable_endpoint_fallback(self):
        provider = LLMProvider({
            "endpoint": "http://localhost:1/v1/chat/completions",
            "model": "none",
            "timeout": 1,
        })
        analysis = {"dignities": [], "patterns": [], "house_emphasis": {}}
        text = provider.generate(analysis)
        self.assertIn("LLM unavailable", text)
        self.assertIn("rules-based interpretation", text)

    def test_is_instance_of_base(self):
        self.assertTrue(isinstance(LLMProvider(), SynthesisProvider))


class TestFactory(unittest.TestCase):
    def test_default_returns_rules(self):
        p = get_provider({})
        self.assertIsInstance(p, RulesProvider)

    def test_explicit_rules(self):
        p = get_provider({"provider": "rules"})
        self.assertIsInstance(p, RulesProvider)

    def test_llm_returns_llm(self):
        p = get_provider({"provider": "llm", "llm_config": {"model": "x"}})
        self.assertIsInstance(p, LLMProvider)


class TestAPISynthesize(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ac_init()
        jd = ac_date_to_jd(1969, 11, 30, 20, 43, 0, -6.0)
        points = [
            "Sun", "Moon", "Mercury", "Venus", "Mars",
            "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
            "Mean Node", "Chiron",
        ]
        body_ids = [body_id_from_name(p) for p in points]
        chart = ac_calc_chart(jd, 35.2167, -101.8167, body_ids, "K")
        aspects = calculate_aspects(chart["bodies"], orb_preset_from_name("Modern"))
        chart["aspects"] = aspects
        cls.chart_id = "xephyr-natal"

        # Seed chart into in-memory DB by starting server logic briefly
        import sqlite3
        from astro_data import db
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.execute("PRAGMA foreign_keys = ON")
        schema_path = Path(__file__).parent.parent / "src" / "astro_data" / "schema.sql"
        with open(schema_path, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        cls.conn = conn
        db.add_chart(
            conn,
            chart_id=cls.chart_id,
            chart_type="natal",
            calc_date="2026-05-17T21:00:00+00:00",
            calc_options={"house_system": "K", "points": points, "orb_preset": "Modern"},
            positions={
                "bodies": chart["bodies"],
                "houses": chart["houses"],
                "angles": {
                    "ascendant": chart["ascendant"],
                    "mc": chart["mc"],
                    "armc": chart["armc"],
                    "vertex": chart["vertex"],
                },
                "latitude": 35.2167,
                "longitude": -101.8167,
            },
            aspects=aspects,
        )
        # Monkey-patch server get_db to use this connection
        from astro_api import server as srv
        srv._db_conn = conn
        srv._migrate_legacy_charts()

        cls.server = srv.HTTPServer(("localhost", 0), srv.AstroHandler)
        cls.port = cls.server.server_address[1]
        import threading
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.conn.close()

    def test_synthesize_rules_endpoint(self):
        req = {
            "chart_id": self.chart_id,
            "provider": "rules",
        }
        body = json.dumps(req).encode("utf-8")
        import urllib.request
        request = urllib.request.Request(
            f"http://localhost:{self.port}/v1/analysis/synthesize",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("chart_id"), self.chart_id)
        self.assertEqual(data.get("provider"), "rules")
        self.assertIn("interpretation", data)
        self.assertIsInstance(data["interpretation"], str)
        self.assertGreater(len(data["interpretation"]), 50)
        self.assertIn("Stellium", data["interpretation"])

    def test_synthesize_llm_fallback_endpoint(self):
        req = {
            "chart_id": self.chart_id,
            "provider": "llm",
            "llm_config": {
                "endpoint": "http://localhost:1/v1/chat/completions",
                "model": "none",
                "timeout": 1,
            },
        }
        body = json.dumps(req).encode("utf-8")
        import urllib.request
        request = urllib.request.Request(
            f"http://localhost:{self.port}/v1/analysis/synthesize",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("provider"), "llm")
        self.assertIn("LLM unavailable", data["interpretation"])

    def test_missing_chart_id(self):
        body = json.dumps({"provider": "rules"}).encode("utf-8")
        import urllib.request
        request = urllib.request.Request(
            f"http://localhost:{self.port}/v1/analysis/synthesize",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            data = json.loads(e.read().decode("utf-8"))
        self.assertEqual(data.get("status"), "error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
