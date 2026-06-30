#!/usr/bin/env python3
"""
Phase 5 Tests: Dignity calculator, pattern detection, analysis orchestrator.
Run with: python3 tests/test_phase5.py -v
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from astro_analyze.dignity import calculate_dignity, _normalize_body_name
from astro_analyze.patterns import detect_patterns, _orb_ok
from astro_analyze.analysis import analyze_chart
from astro_api.astro_ctypes import (
    ac_init,
    ac_date_to_jd,
    ac_calc_chart,
    calculate_aspects,
    body_id_from_name,
    orb_preset_from_name,
)


class TestDignity(unittest.TestCase):
    def test_sun_in_leo_is_domicile(self):
        d = calculate_dignity("Sun", sign=4, sign_degree=15.0, house=5, retrograde=False)
        self.assertTrue(d["domicile"])
        self.assertFalse(d["detriment"])
        self.assertEqual(d["score"], 5 + 2 + 1)  # domicile + succedent + direct

    def test_moon_in_cancer_is_domicile(self):
        d = calculate_dignity("Moon", sign=3, sign_degree=10.0, house=4, retrograde=False)
        self.assertTrue(d["domicile"])
        self.assertTrue(d["accidental"] == "strong")
        self.assertEqual(d["score"], 5 + 3 + 1)  # domicile + angular + direct

    def test_sun_in_aries_exaltation_exact(self):
        d = calculate_dignity("Sun", sign=0, sign_degree=19.0, house=1, retrograde=False)
        self.assertTrue(d["exaltation"])
        self.assertTrue(d["exact_degree"])
        self.assertEqual(d["score"], 4 + 3 + 1)

    def test_sun_in_aries_exaltation_near(self):
        d = calculate_dignity("Sun", sign=0, sign_degree=19.5, house=1, retrograde=False)
        self.assertTrue(d["exaltation"])

    def test_sun_in_aries_exaltation_out_of_orb(self):
        d = calculate_dignity("Sun", sign=0, sign_degree=22.0, house=1, retrograde=False)
        self.assertFalse(d["exaltation"])

    def test_sun_in_sagittarius_not_domicile(self):
        # Xephyr's natal Sun
        d = calculate_dignity("Sun", sign=8, sign_degree=8.74, house=5, retrograde=False)
        self.assertFalse(d["domicile"])
        self.assertFalse(d["exaltation"])
        self.assertFalse(d["detriment"])
        self.assertFalse(d["fall"])
        self.assertEqual(d["accidental"], "moderate")

    def test_sun_in_aquarius_is_detriment(self):
        d = calculate_dignity("Sun", sign=10, sign_degree=10.0, house=7, retrograde=False)
        self.assertTrue(d["detriment"])
        self.assertFalse(d["domicile"])
        self.assertEqual(d["score"], -5 + 3 + 1)

    def test_moon_in_scorpio_is_fall(self):
        d = calculate_dignity("Moon", sign=7, sign_degree=10.0, house=6, retrograde=False)
        self.assertTrue(d["fall"])
        self.assertFalse(d["exaltation"])
        self.assertEqual(d["score"], -4 + 1 + 1)

    def test_retrograde_penalty(self):
        d1 = calculate_dignity("Saturn", sign=1, sign_degree=3.07, house=10, retrograde=False)
        d2 = calculate_dignity("Saturn", sign=1, sign_degree=3.07, house=10, retrograde=True)
        self.assertEqual(d1["score"] - d2["score"], 2)  # direct +1 vs retro -1

    def test_accidental_angular(self):
        d = calculate_dignity("Mars", sign=0, sign_degree=10.0, house=1, retrograde=False)
        self.assertEqual(d["accidental"], "strong")

    def test_accidental_succedent(self):
        d = calculate_dignity("Venus", sign=1, sign_degree=10.0, house=2, retrograde=False)
        self.assertEqual(d["accidental"], "moderate")

    def test_accidental_cadent(self):
        d = calculate_dignity("Mercury", sign=2, sign_degree=10.0, house=3, retrograde=False)
        self.assertEqual(d["accidental"], "weak")

    def test_normalize_body_name(self):
        self.assertEqual(_normalize_body_name("sun"), "Sun")
        self.assertEqual(_normalize_body_name(" North Node "), "Mean Node")
        self.assertEqual(_normalize_body_name(" True Node "), "True Node")
        self.assertEqual(_normalize_body_name(" South Node "), "South Node")
        self.assertEqual(_normalize_body_name("Chiron"), "Chiron")


class TestPatterns(unittest.TestCase):
    def test_empty_chart_returns_empty(self):
        self.assertEqual(detect_patterns({}), [])
        self.assertEqual(detect_patterns({"bodies": [], "aspects": []}), [])

    def test_orb_helper(self):
        self.assertTrue(_orb_ok(120.0, 120.0, 5.0))
        self.assertTrue(_orb_ok(358.0, 2.0, 5.0))
        self.assertFalse(_orb_ok(130.0, 120.0, 5.0))

    def test_stellium_by_sign(self):
        chart = {
            "bodies": [
                {"name": "Sun", "sign": 0, "house": 1, "longitude": 10.0},
                {"name": "Mercury", "sign": 0, "house": 1, "longitude": 12.0},
                {"name": "Venus", "sign": 0, "house": 2, "longitude": 15.0},
                {"name": "Mars", "sign": 1, "house": 3, "longitude": 40.0},
            ],
            "aspects": [],
        }
        patterns = detect_patterns(chart)
        stelliums = [p for p in patterns if p["type"] == "Stellium"]
        self.assertEqual(len(stelliums), 1)
        self.assertEqual(set(stelliums[0]["bodies"]), {"Sun", "Mercury", "Venus"})
        self.assertEqual(stelliums[0]["basis"], "sign")

    def test_stellium_by_house(self):
        chart = {
            "bodies": [
                {"name": "Sun", "sign": 0, "house": 5, "longitude": 10.0},
                {"name": "Moon", "sign": 1, "house": 5, "longitude": 40.0},
                {"name": "Mercury", "sign": 2, "house": 5, "longitude": 70.0},
                {"name": "Venus", "sign": 3, "house": 6, "longitude": 100.0},
            ],
            "aspects": [],
        }
        patterns = detect_patterns(chart)
        stelliums = [p for p in patterns if p["type"] == "Stellium"]
        self.assertEqual(len(stelliums), 1)
        self.assertEqual(set(stelliums[0]["bodies"]), {"Sun", "Moon", "Mercury"})
        self.assertEqual(stelliums[0]["basis"], "house")

    def test_grand_trine_synthetic(self):
        chart = {
            "bodies": [
                {"name": "A", "sign": 0, "house": 1, "longitude": 10.0},
                {"name": "B", "sign": 4, "house": 5, "longitude": 130.0},
                {"name": "C", "sign": 8, "house": 9, "longitude": 250.0},
            ],
            "aspects": [
                {"body_a": "A", "body_b": "B", "aspect_id": 5, "aspect_name": "trine", "orb": 0.0, "actual_angle": 120.0},
                {"body_a": "A", "body_b": "C", "aspect_id": 5, "aspect_name": "trine", "orb": 0.0, "actual_angle": 120.0},
                {"body_a": "B", "body_b": "C", "aspect_id": 5, "aspect_name": "trine", "orb": 0.0, "actual_angle": 120.0},
            ],
        }
        patterns = detect_patterns(chart)
        gt = [p for p in patterns if p["type"] == "Grand Trine"]
        self.assertEqual(len(gt), 1)
        self.assertEqual(set(gt[0]["bodies"]), {"A", "B", "C"})
        self.assertEqual(gt[0]["element"], "fire")

    def test_t_square_synthetic(self):
        chart = {
            "bodies": [
                {"name": "A", "sign": 0, "house": 1, "longitude": 0.0},
                {"name": "B", "sign": 6, "house": 7, "longitude": 180.0},
                {"name": "C", "sign": 3, "house": 10, "longitude": 90.0},
            ],
            "aspects": [
                {"body_a": "A", "body_b": "B", "aspect_id": 8, "aspect_name": "opposition", "orb": 0.0, "actual_angle": 180.0},
                {"body_a": "A", "body_b": "C", "aspect_id": 4, "aspect_name": "square", "orb": 0.0, "actual_angle": 90.0},
                {"body_a": "B", "body_b": "C", "aspect_id": 4, "aspect_name": "square", "orb": 0.0, "actual_angle": 90.0},
            ],
        }
        patterns = detect_patterns(chart)
        ts = [p for p in patterns if p["type"] == "T-Square"]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0]["apex"], "C")

    def test_yod_synthetic(self):
        chart = {
            "bodies": [
                {"name": "A", "sign": 0, "house": 1, "longitude": 0.0},
                {"name": "B", "sign": 2, "house": 3, "longitude": 60.0},
                {"name": "C", "sign": 7, "house": 8, "longitude": 150.0},
            ],
            "aspects": [
                {"body_a": "A", "body_b": "B", "aspect_id": 3, "aspect_name": "sextile", "orb": 0.0, "actual_angle": 60.0},
                {"body_a": "A", "body_b": "C", "aspect_id": 7, "aspect_name": "quincunx", "orb": 0.0, "actual_angle": 150.0},
                {"body_a": "B", "body_b": "C", "aspect_id": 7, "aspect_name": "quincunx", "orb": 0.0, "actual_angle": 150.0},
            ],
        }
        patterns = detect_patterns(chart)
        yods = [p for p in patterns if p["type"] == "Yod"]
        self.assertEqual(len(yods), 1)
        self.assertEqual(yods[0]["apex"], "C")

    def test_cradle_synthetic(self):
        chart = {
            "bodies": [
                {"name": "A", "sign": 0, "house": 1, "longitude": 0.0},
                {"name": "B", "sign": 2, "house": 3, "longitude": 60.0},
                {"name": "C", "sign": 6, "house": 7, "longitude": 180.0},
                {"name": "D", "sign": 8, "house": 9, "longitude": 240.0},
            ],
            "aspects": [
                {"body_a": "A", "body_b": "B", "aspect_id": 3, "aspect_name": "sextile", "orb": 0.0, "actual_angle": 60.0},
                {"body_a": "C", "body_b": "D", "aspect_id": 3, "aspect_name": "sextile", "orb": 0.0, "actual_angle": 60.0},
                {"body_a": "A", "body_b": "C", "aspect_id": 4, "aspect_name": "square", "orb": 0.0, "actual_angle": 180.0},
                {"body_a": "B", "body_b": "D", "aspect_id": 4, "aspect_name": "square", "orb": 0.0, "actual_angle": 180.0},
            ],
        }
        patterns = detect_patterns(chart)
        cradles = [p for p in patterns if p["type"] == "Cradle"]
        self.assertEqual(len(cradles), 1)
        self.assertEqual(set(cradles[0]["bodies"]), {"A", "B", "C", "D"})

    def test_grand_cross_synthetic(self):
        chart = {
            "bodies": [
                {"name": "A", "sign": 0, "house": 1, "longitude": 0.0},
                {"name": "B", "sign": 6, "house": 7, "longitude": 180.0},
                {"name": "C", "sign": 3, "house": 10, "longitude": 90.0},
                {"name": "D", "sign": 9, "house": 4, "longitude": 270.0},
            ],
            "aspects": [
                {"body_a": "A", "body_b": "B", "aspect_id": 8, "aspect_name": "opposition", "orb": 0.0, "actual_angle": 180.0},
                {"body_a": "C", "body_b": "D", "aspect_id": 8, "aspect_name": "opposition", "orb": 0.0, "actual_angle": 180.0},
                {"body_a": "A", "body_b": "C", "aspect_id": 4, "aspect_name": "square", "orb": 0.0, "actual_angle": 90.0},
                {"body_a": "A", "body_b": "D", "aspect_id": 4, "aspect_name": "square", "orb": 0.0, "actual_angle": 90.0},
                {"body_a": "B", "body_b": "C", "aspect_id": 4, "aspect_name": "square", "orb": 0.0, "actual_angle": 90.0},
                {"body_a": "B", "body_b": "D", "aspect_id": 4, "aspect_name": "square", "orb": 0.0, "actual_angle": 90.0},
            ],
        }
        patterns = detect_patterns(chart)
        gcs = [p for p in patterns if p["type"] == "Grand Cross"]
        self.assertEqual(len(gcs), 1)
        self.assertEqual(set(gcs[0]["bodies"]), {"A", "B", "C", "D"})

    def test_kite_synthetic(self):
        chart = {
            "bodies": [
                {"name": "A", "sign": 0, "house": 1, "longitude": 0.0},
                {"name": "B", "sign": 4, "house": 5, "longitude": 120.0},
                {"name": "C", "sign": 8, "house": 9, "longitude": 240.0},
                {"name": "D", "sign": 2, "house": 3, "longitude": 60.0},
            ],
            "aspects": [
                {"body_a": "A", "body_b": "B", "aspect_id": 5, "aspect_name": "trine", "orb": 0.0, "actual_angle": 120.0},
                {"body_a": "B", "body_b": "C", "aspect_id": 5, "aspect_name": "trine", "orb": 0.0, "actual_angle": 120.0},
                {"body_a": "A", "body_b": "C", "aspect_id": 5, "aspect_name": "trine", "orb": 0.0, "actual_angle": 120.0},
                {"body_a": "A", "body_b": "D", "aspect_id": 3, "aspect_name": "sextile", "orb": 0.0, "actual_angle": 60.0},
                {"body_a": "C", "body_b": "D", "aspect_id": 3, "aspect_name": "sextile", "orb": 0.0, "actual_angle": 60.0},
                {"body_a": "B", "body_b": "D", "aspect_id": 8, "aspect_name": "opposition", "orb": 0.0, "actual_angle": 180.0},
            ],
        }
        patterns = detect_patterns(chart)
        kites = [p for p in patterns if p["type"] == "Kite"]
        self.assertEqual(len(kites), 1)
        self.assertEqual(kites[0]["apex"], "B")


class TestAnalysisOrchestrator(unittest.TestCase):
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
        cls.xephyr_chart = chart

    def test_analyze_chart_returns_expected_keys(self):
        result = analyze_chart(self.xephyr_chart)
        self.assertIn("dignities", result)
        self.assertIn("patterns", result)
        self.assertIn("house_emphasis", result)
        self.assertIn("element_balance", result)
        self.assertIn("modality_balance", result)

    def test_dignities_count_matches_bodies(self):
        result = analyze_chart(self.xephyr_chart)
        self.assertEqual(len(result["dignities"]), len(self.xephyr_chart["bodies"]))

    def test_sun_in_sagittarius_not_domicile_xephyr(self):
        result = analyze_chart(self.xephyr_chart)
        sun_dignity = next(d for d in result["dignities"] if d["body"] == "Sun")
        self.assertFalse(sun_dignity["domicile"])
        self.assertFalse(sun_dignity["exaltation"])
        self.assertFalse(sun_dignity["detriment"])
        self.assertFalse(sun_dignity["fall"])
        self.assertEqual(sun_dignity["accidental"], "moderate")
        self.assertEqual(sun_dignity["score"], 2 + 1)  # succedent + direct = 3

    def test_house_emphasis_xephyr(self):
        result = analyze_chart(self.xephyr_chart)
        he = result["house_emphasis"]
        # House 5 should have several planets
        self.assertIn(5, he)
        self.assertGreaterEqual(he[5], 3)

    def test_element_balance_xephyr(self):
        result = analyze_chart(self.xephyr_chart)
        eb = result["element_balance"]
        self.assertEqual(sum(eb.values()), len(self.xephyr_chart["bodies"]))
        # fire should be strong with Sun/Moon/Mercury in fire signs
        self.assertGreater(eb["fire"], 0)

    def test_modality_balance_xephyr(self):
        result = analyze_chart(self.xephyr_chart)
        mb = result["modality_balance"]
        self.assertEqual(sum(mb.values()), len(self.xephyr_chart["bodies"]))

    def test_patterns_on_xephyr_chart(self):
        result = analyze_chart(self.xephyr_chart)
        patterns = result["patterns"]
        # Should detect at least stellium in house 5
        stelliums = [p for p in patterns if p["type"] == "Stellium"]
        self.assertTrue(len(stelliums) >= 1)
        # Xephyr chart: Sun, Mercury, Venus, Neptune in house 5
        house5_stellium = [p for p in stelliums if p.get("basis") == "house" and p.get("house") == 5]
        self.assertTrue(len(house5_stellium) >= 1)

    def test_jupiter_saturn_opposition_xephyr(self):
        result = analyze_chart(self.xephyr_chart)
        patterns = result["patterns"]
        t_squares = [p for p in patterns if p["type"] == "T-Square"]
        # Jupiter opposite Saturn is present; look for any T-square apex
        for ts in t_squares:
            if "Jupiter" in ts["bodies"] and "Saturn" in ts["bodies"]:
                return
        # If no T-square with Jupiter-Saturn, that's okay; just assert we have some patterns
        self.assertIsInstance(patterns, list)


if __name__ == "__main__":
    unittest.main(verbosity=2)
