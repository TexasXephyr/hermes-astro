"""
Tests for astro_hours planetary hour calculations.
"""
import datetime
from zoneinfo import ZoneInfo

import pytest

from astro_hours import (
    planetary_hours_for_date,
    current_planetary_hour,
    get_current_hour,
    get_sunrise_sunset,
    PLANET_ORDER,
    DAY_RULERS,
)

EUGENE_LAT = 44.0521
EUGENE_LON = -123.0868
EUGENE_ELEV = 130


def test_planetary_hours_returns_24():
    hours = planetary_hours_for_date("2025-01-01", EUGENE_LAT, EUGENE_LON, EUGENE_ELEV, "America/Los_Angeles")
    assert len(hours) == 24
    assert len([h for h in hours if h["period"] == "day"]) == 12
    assert len([h for h in hours if h["period"] == "night"]) == 12


def test_day_ruler_matches_weekday():
    # 2025-01-01 is a Wednesday -> first day hour ruler is Mercury
    hours = planetary_hours_for_date("2025-01-01", EUGENE_LAT, EUGENE_LON, EUGENE_ELEV, "America/Los_Angeles")
    day_hour_1 = hours[0]
    assert day_hour_1["planet"] == "Mercury"
    assert day_hour_1["hour_number"] == 1
    assert day_hour_1["period"] == "day"


def test_night_hours_follow_chaldean_order():
    hours = planetary_hours_for_date("2025-01-01", EUGENE_LAT, EUGENE_LON, EUGENE_ELEV, "America/Los_Angeles")
    first_day = PLANET_ORDER.index(DAY_RULERS[2])  # Wednesday -> Mercury index 5
    # Night first planet is next in Chaldean order after day 12th planet
    expected_night_first = PLANET_ORDER[(first_day + 12) % 7]
    night_hour_1 = hours[12]
    assert night_hour_1["period"] == "night"
    assert night_hour_1["planet"] == expected_night_first


def test_hours_cover_full_day():
    hours = planetary_hours_for_date("2025-01-01", EUGENE_LAT, EUGENE_LON, EUGENE_ELEV, "America/Los_Angeles")
    first_start = hours[0]["start_dt"]
    last_end = hours[-1]["end_dt"]
    assert first_start.date() == datetime.date(2025, 1, 1)
    assert last_end.date() == datetime.date(2025, 1, 2)


def test_get_current_hour_finds_container():
    hours = planetary_hours_for_date("2025-01-01", EUGENE_LAT, EUGENE_LON, EUGENE_ELEV, "America/Los_Angeles")
    target = hours[3]["start_dt"] + datetime.timedelta(minutes=5)
    found = get_current_hour(hours, target)
    assert found is hours[3]


def test_sunrise_sunset_returns_reasonable_times():
    sunrise, sunset, next_sunrise = get_sunrise_sunset("2025-06-21", EUGENE_LAT, EUGENE_LON, EUGENE_ELEV, "America/Los_Angeles")
    assert sunrise < sunset
    assert sunset < next_sunrise
    # Summer solstice sunrise early, sunset late
    assert sunrise.hour < 12
    assert sunset.hour > 18


def test_current_planetary_hour_by_coords():
    tz = ZoneInfo("America/Los_Angeles")
    when = datetime.datetime(2025, 1, 1, 12, 0, 0, tzinfo=tz)
    cur = current_planetary_hour(lat=EUGENE_LAT, lon=EUGENE_LON, elev=EUGENE_ELEV, tz=tz, when=when)
    assert cur is not None
    assert cur["start_dt"] <= when < cur["end_dt"]


def test_current_planetary_hour_from_list():
    hours = planetary_hours_for_date("2025-01-01", EUGENE_LAT, EUGENE_LON, EUGENE_ELEV, "America/Los_Angeles")
    target = hours[5]["start_dt"] + datetime.timedelta(minutes=1)
    cur = current_planetary_hour(hours=hours, when=target)
    assert cur is hours[5]


def test_all_planets_present_in_day_hours():
    hours = planetary_hours_for_date("2025-01-01", EUGENE_LAT, EUGENE_LON, EUGENE_ELEV, "America/Los_Angeles")
    day_planets = {h["planet"] for h in hours if h["period"] == "day"}
    assert len(day_planets) == 7


def test_default_tz_is_utc():
    hours = planetary_hours_for_date("2025-01-01", 0.0, 0.0)
    assert str(hours[0]["start_dt"].tzinfo) == "UTC"
