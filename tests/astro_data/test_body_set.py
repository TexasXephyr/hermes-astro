#!/usr/bin/env python3
"""
Unit tests for astro_data.bodies.BodySet and point selectors.
"""
import pytest
import sys
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from astro_data.bodies import BodySet, DEFAULT_POINTS, ALL_POINTS


class TestBodySet:
    def test_default_points_loads(self):
        bs = BodySet(DEFAULT_POINTS)
        assert len(bs) > 0
        assert "Sun" in bs

    def test_all_points_loads(self):
        bs = BodySet(ALL_POINTS)
        assert len(bs) >= len(BodySet(DEFAULT_POINTS))
        for name in bs:
            assert isinstance(name, str)

    def test_custom_valid_list(self):
        bs = BodySet(["Sun", "Moon", "Mercury"])
        assert list(bs) == ["Sun", "Moon", "Mercury"]

    def test_empty_list_raises(self):
        with pytest.raises(ValueError):
            BodySet([])

    def test_unknown_name_raises(self):
        with pytest.raises(ValueError) as exc:
            BodySet(["Sun", "FakeBody"])
        assert "FakeBody" in str(exc.value)
        assert "Sun" not in str(exc.value) or "valid" in str(exc.value)

    def test_case_insensitive_match(self):
        bs = BodySet(["sun", "mOOn"])
        assert "Sun" in bs
        assert "Moon" in bs

    def test_body_set_iteration(self):
        bs = BodySet(["Sun", "Moon", "Mercury"])
        assert list(bs) == ["Sun", "Moon", "Mercury"]

    def test_default_does_not_equal_all(self):
        assert set(DEFAULT_POINTS) != set(ALL_POINTS)
        assert len(ALL_POINTS) > len(DEFAULT_POINTS)
