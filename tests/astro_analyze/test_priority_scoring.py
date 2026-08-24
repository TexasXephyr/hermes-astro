"""Tests for astro_analyze.scoring — composite transit priority scoring."""

import math

import pytest

from astro_analyze.scoring import (
    aspect_value,
    aspect_priority,
    compute_planetary_grid_weights,
    planet_relative_values,
    score_active_transits,
    MAJOR_ASPECTS,
)


def test_aspect_weights_from_yaml():
    """Weights come from scoring.yaml, not hard-coded."""
    from astro_data.loaders import yaml_loader

    weights = yaml_loader("scoring")["aspect_weights"]
    assert weights["conjunction"] == 36
    assert weights["quincunx"] == 10


def test_aspect_value_orb_decay():
    """Tighter orb → higher score; zero orb gives the max."""
    tight = aspect_value("conjunction", 0.0)
    wide = aspect_value("conjunction", 5.0)
    assert tight > wide
    assert tight > 0


def test_aspect_value_unknown_aspect_zero():
    assert aspect_value("nonexistent", 1.0) == 0


def test_grid_weights_two_pass():
    chart = {
        "bodies": [],
        "aspects": [
            {"body_a": "Sun", "body_b": "Moon", "aspect_name": "Conjunction", "orb": 0.0},
            {"body_a": "Sun", "body_b": "Mars", "aspect_name": "Square", "orb": 1.0},
        ],
    }
    weights = compute_planetary_grid_weights(chart)
    assert weights["Sun"] > 1.0
    assert weights["Moon"] > 1.0
    assert weights["Sun"] > weights["Moon"]  # Sun has two aspects


def test_aspect_priority_luminary_bonus():
    """Sun/Moon involvement raises priority."""
    with_lum = aspect_priority("Sun", "Virgo", "Moon", "Leo", 1.0, 0, "conjunction")
    without = aspect_priority("Saturn", "Aries", "Pluto", "Capricorn", 1.0, 0, "conjunction")
    assert with_lum > without


def test_aspect_priority_applying_bonus():
    applying = aspect_priority("Saturn", "Aries", "Sun", "Sagittarius", 1.0, 3, "square")
    separating = aspect_priority("Saturn", "Aries", "Sun", "Sagittarius", 1.0, -3, "square")
    assert applying > separating


def test_aspect_priority_distance_penalty():
    exact = aspect_priority("Saturn", "Aries", "Sun", "Sagittarius", 1.0, 0, "square")
    far = aspect_priority("Saturn", "Aries", "Sun", "Sagittarius", 1.0, 10, "square")
    assert exact > far


def test_score_active_transits_sorts_and_filters():
    natal = {"bodies": [{"name": "Sun", "sign_name": "Sagittarius"}]}
    transit = {
        "bodies": [{"name": "Saturn", "sign_name": "Aries"}],
        "aspects": [],
    }
    active = [
        {"transiting_body": "Saturn", "natal_body": "Sun", "aspect": "square",
         "orb": 1.0, "days_to_exact": 0, "in_effect": True},
        {"transiting_body": "Saturn", "natal_body": "Sun", "aspect": "semisextile",
         "orb": 0.5, "days_to_exact": 0, "in_effect": True},
    ]
    scored = score_active_transits(active, natal, transit)
    assert len(scored) == 1  # minor aspect filtered out
    assert scored[0]["priority"] > 0
    assert scored[0]["aspect"] == "square"


def test_planet_relative_values_aggregates():
    natal = {"bodies": [{"name": "Sun", "sign_name": "Sagittarius"}]}
    transit = {
        "bodies": [{"name": "Saturn", "sign_name": "Aries"}, {"name": "Mars", "sign_name": "Cancer"}],
        "aspects": [],
    }
    active = [
        {"transiting_body": "Saturn", "natal_body": "Sun", "aspect": "square",
         "orb": 1.0, "days_to_exact": 0},
        {"transiting_body": "Saturn", "natal_body": "Sun", "aspect": "trine",
         "orb": 2.0, "days_to_exact": 1},
        {"transiting_body": "Mars", "natal_body": "Sun", "aspect": "conjunction",
         "orb": 0.5, "days_to_exact": 0},
    ]
    rows = planet_relative_values(active, natal, transit)
    assert rows[0]["body"] == "Saturn"  # two transits beat one
    assert rows[0]["transit_count"] == 2
    assert rows[1]["body"] == "Mars"
    assert rows[1]["transit_count"] == 1
    assert rows[0]["total_priority"] > rows[1]["total_priority"]


def test_major_aspects_constant():
    assert MAJOR_ASPECTS == {"conjunction", "opposition", "trine", "square", "sextile", "quincunx"}
