"""
Unit tests for astro_text.houses helpers.
"""
import pytest

from astro_text.houses import find_house, day_of_sign, day_of_house


def _make_houses(longitudes):
    return [{"house_num": i + 1, "longitude": lon} for i, lon in enumerate(longitudes)]


class TestHouseHelpers:
    def test_find_house_basic(self):
        houses = _make_houses([0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330])
        assert find_house(15.0, houses) == 1
        assert find_house(45.0, houses) == 2

    def test_find_house_wrap_aries(self):
        houses = _make_houses([350, 20, 50, 80, 110, 140, 170, 200, 230, 260, 290, 320])
        assert find_house(355.0, houses) == 1
        assert find_house(5.0, houses) == 1

    def test_day_of_sign_ranges(self):
        assert day_of_sign(0.0) == 1
        assert day_of_sign(14.9) == 15
        assert day_of_sign(29.9) == 30

    def test_day_of_house_basic(self):
        assert day_of_house(15.0, cusp_longitude=0.0, house_span=30.0) == 16

    def test_empty_houses_raises(self):
        with pytest.raises(ValueError):
            find_house(10.0, [])

    def test_longitude_out_of_range_normalized(self):
        houses = _make_houses([0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330])
        assert find_house(390.0, houses) == 2
        assert find_house(-30.0, houses) == 12
