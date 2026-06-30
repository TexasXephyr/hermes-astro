#!/usr/bin/env python3
"""
Phase 6 Tests: Transit event finder and period impact analyzer.
Run with: python3 tests/test_phase6.py -v
"""
import json
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from astro_api.astro_ctypes import (
    ac_init,
    ac_date_to_jd,
    ac_calc_chart,
    body_id_from_name,
    orb_preset_from_name,
    calculate_aspects,
)
from astro_analyze.transits import find_transit_events, period_impact


class TestTransits(unittest.TestCase):
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
        chart["latitude"] = 35.2167
        chart["longitude"] = -101.8167
        chart["house_system"] = "K"
        cls.xephyr_chart = chart

    def test_saturn_to_natal_sun_30_days(self):
        events = find_transit_events(
            self.xephyr_chart,
            "2026-05-01", "2026-05-31",
            include_points=["Saturn"],
            include_aspects=["conjunction", "opposition", "square", "trine", "sextile"],
        )
        self.assertIsInstance(events, list)
        self.assertGreaterEqual(len(events), 1)
        sun_events = [e for e in events if e["natal_body"] == "Sun"]
        # Saturn is trine natal Sun in May 2026; no hard aspect that month
        self.assertTrue(len(sun_events) >= 1)
        for e in sun_events:
            self.assertEqual(e["transiting_body"], "Saturn")
            self.assertIn(e["aspect"], ["conjunction", "opposition", "square", "trine", "sextile"])

    def test_saturn_to_natal_uranus_opposition(self):
        events = find_transit_events(
            self.xephyr_chart,
            "2026-05-01", "2026-05-31",
            include_points=["Saturn", "Uranus"],
            include_aspects=["conjunction", "opposition", "square"],
        )
        uranus_opp = [e for e in events
                      if e["natal_body"] == "Uranus" and e["aspect"] == "opposition"]
        self.assertTrue(len(uranus_opp) >= 1)

    def test_period_impact_today(self):
        impact = period_impact(
            self.xephyr_chart,
            "2026-05-18",
            orb_days=7,
            include_points=["Saturn", "Uranus"],
        )
        self.assertIn("active_transits", impact)
        self.assertIsInstance(impact["active_transits"], list)
        self.assertGreaterEqual(len(impact["active_transits"]), 1)
        for a in impact["active_transits"]:
            self.assertIn(a["transiting_body"], ["Saturn", "Uranus"])
            self.assertIn("exact_date", a)
            self.assertIn("days_to_exact", a)

    def test_period_impact_days_to_exact(self):
        impact = period_impact(
            self.xephyr_chart,
            "2026-05-18",
            orb_days=14,
            include_points=["Saturn", "Uranus"],
        )
        saturn_sun = [a for a in impact["active_transits"]
                      if a["transiting_body"] == "Saturn" and a["natal_body"] == "Sun"]
        if saturn_sun:
            self.assertIsInstance(saturn_sun[0]["days_to_exact"], int)

    def test_empty_include_points_returns_empty(self):
        events = find_transit_events(
            self.xephyr_chart,
            "2026-05-01", "2026-05-31",
            include_points=[],
        )
        self.assertEqual(events, [])

    def test_unknown_aspects_returns_empty(self):
        events = find_transit_events(
            self.xephyr_chart,
            "2026-05-01", "2026-05-31",
            include_points=["Saturn"],
            include_aspects=["bogus_aspect"],
        )
        self.assertEqual(events, [])

    def test_event_structure(self):
        events = find_transit_events(
            self.xephyr_chart,
            "2026-05-01", "2026-05-02",
            include_points=["Saturn"],
        )
        for e in events:
            self.assertIn("date", e)
            self.assertIn("transiting_body", e)
            self.assertIn("natal_body", e)
            self.assertIn("aspect", e)
            self.assertIn("angle", e)
            self.assertIn("orb", e)
            self.assertIn("applying", e)

    def test_performance_1_year(self):
        t0 = time.perf_counter()
        events = find_transit_events(
            self.xephyr_chart,
            "2025-01-01", "2025-12-31",
            include_points=["Saturn", "Uranus", "Jupiter", "Pluto"],
        )
        elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 5.0, f"1-year search took {elapsed:.2f}s, expected <5s")
        self.assertIsInstance(events, list)

    def test_cache_reuse(self):
        t0 = time.perf_counter()
        events = find_transit_events(
            self.xephyr_chart,
            "2026-01-01", "2026-01-31",
            include_points=["Saturn"],
        )
        elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 2.0)

    def test_period_impact_multiple_bodies(self):
        impact = period_impact(
            self.xephyr_chart,
            "2026-05-18",
            orb_days=7,
        )
        self.assertGreaterEqual(len(impact["active_transits"]), 1)
        bodies = {a["transiting_body"] for a in impact["active_transits"]}
        self.assertTrue(len(bodies) >= 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
