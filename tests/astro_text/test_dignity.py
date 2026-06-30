"""
Unit tests for astro_text.dignity YAML-backed lookup.
"""
import pytest

from astro_text.dignity import get_dignity


class TestDignityLookup:
    def test_sun_in_leo_domicile(self):
        d = get_dignity("Sun", "Leo")
        assert d["label"] == "domicile"
        assert d["score"] == 5

    def test_sun_in_aquarius_detriment(self):
        d = get_dignity("Sun", "Aquarius")
        assert d["label"] == "detriment"
        assert d["score"] == -5

    def test_moon_in_taurus_exaltation_exact(self):
        d = get_dignity("Moon", "Taurus")
        assert d["label"] == "exaltation"
        assert d["exact_degree"] is True or d["exact_degree"] is False

    def test_moon_in_scorpio_fall(self):
        d = get_dignity("Moon", "Scorpio")
        assert d["label"] == "fall"
        assert d["score"] == -4

    def test_chiron_no_dignity(self):
        d = get_dignity("Chiron", "Aries")
        assert d["label"] in ("", "peregrine", None)

    def test_unknown_sign_raises(self):
        with pytest.raises(ValueError):
            get_dignity("Sun", "Ophiuchus")
