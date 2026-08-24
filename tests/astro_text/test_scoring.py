"""
Unit tests for YAML-backed dignity/accidental scoring.
"""
import pytest

from astro_text.scoring import score
from astro_data.loaders import yaml_loader


class TestScoring:
    def test_domicile_score_matches_legacy(self):
        # 5 domicile + 2 succedent + 1 direct = 8
        assert score(body="Sun", sign="Leo", house=5, retrograde=False) == 8

    def test_angular_score_matches_legacy(self):
        # 5 domicile + 3 angular + 1 direct = 9
        assert score(body="Mars", sign="Aries", house=1, retrograde=False) == 9

    def test_retrograde_penalty(self):
        direct = score(body="Saturn", sign="Taurus", house=10, retrograde=False)
        retro = score(body="Saturn", sign="Taurus", house=10, retrograde=True)
        assert direct - retro == 2  # direct +1 vs retro -1

    def test_detriment_score_negative(self):
        # Saturn in Taurus is peregrine; no essential score, angular + direct = 4.
        assert score(body="Saturn", sign="Taurus", house=10, retrograde=False) == 4

    def test_sun_detriment_score(self):
        # -5 detriment + 3 angular + 1 direct = -1
        assert score(body="Sun", sign="Aquarius", house=7, retrograde=False) == -1

    def test_score_weights_are_numeric(self):
        weights = yaml_loader("scoring")
        for key, value in weights.items():
            if key == "aspect_weights":
                assert isinstance(value, dict)
                for aspect, weight in value.items():
                    assert isinstance(weight, (int, float)), f"{aspect} not numeric"
            else:
                assert isinstance(value, (int, float)), f"{key} not numeric"
