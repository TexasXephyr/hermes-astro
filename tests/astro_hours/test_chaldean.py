"""
Unit tests for astro_hours planetary hours.
"""
import datetime

import pytest
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from astro_hours import (
    planetary_hours_for_date,
    compute_planetary_hours,
    PLANET_ORDER,
    DAY_RULERS,
)


EUGENE_LAT = 44.0521
EUGENE_LON = -123.0868
EUGENE_TZ = "America/Los_Angeles"


class TestChaldeanHours:
    def test_day_rulers_match_weekdays(self):
        # DAY_RULERS is a list indexed by Python weekday (Monday=0...Sunday=6)
        # Monday=Moon, Tuesday=Mars, Wednesday=Mercury, Thursday=Jupiter, Friday=Venus, Saturday=Saturn, Sunday=Sun
        assert DAY_RULERS[0] == "Moon"    # Monday
        assert DAY_RULERS[1] == "Mars"    # Tuesday
        assert DAY_RULERS[2] == "Mercury" # Wednesday
        assert DAY_RULERS[3] == "Jupiter" # Thursday
        assert DAY_RULERS[4] == "Venus"   # Friday
        assert DAY_RULERS[5] == "Saturn"  # Saturday
        assert DAY_RULERS[6] == "Sun"     # Sunday

    def test_first_day_hour_is_day_ruler(self):
        # 2026-06-28 is a Sunday (Python weekday 6)
        # DAY_RULERS[6] = "Sun"
        date = datetime.date(2026, 6, 28)
        hours = compute_planetary_hours(date, EUGENE_LAT, EUGENE_LON, tz=EUGENE_TZ)
        day_hours = [h for h in hours if h["period"] == "day"]
        assert day_hours[0]["planet"] == DAY_RULERS[6]  # Sunday ruler

    def test_first_night_hour_follows_chaldean_order(self):
        date = datetime.date(2026, 6, 28)
        hours = compute_planetary_hours(date, EUGENE_LAT, EUGENE_LON, tz=EUGENE_TZ)
        day_hours = [h for h in hours if h["period"] == "day"]
        night_hours = [h for h in hours if h["period"] == "night"]
        last_day_idx = PLANET_ORDER.index(day_hours[-1]["planet"])
        first_night_idx = PLANET_ORDER.index(night_hours[0]["planet"])
        assert first_night_idx == (last_day_idx + 1) % 7

    def test_24_hours_total(self):
        date = datetime.date(2026, 6, 28)
        hours = compute_planetary_hours(date, EUGENE_LAT, EUGENE_LON, tz=EUGENE_TZ)
        assert len(hours) == 24

    def test_day_hours_divided_by_12(self):
        date = datetime.date(2026, 6, 28)
        hours = compute_planetary_hours(date, EUGENE_LAT, EUGENE_LON, tz=EUGENE_TZ)
        # Use the datetime objects for accurate duration calculation
        sunrise = hours[0]["start_dt"]
        sunset = hours[11]["end_dt"]
        day_length = (sunset - sunrise).total_seconds()
        first_day = hours[0]
        hour_length = (first_day["end_dt"] - first_day["start_dt"]).total_seconds()
        assert abs(hour_length * 12 - day_length) < 1

    def test_night_hours_divided_by_12(self):
        date = datetime.date(2026, 6, 28)
        hours = compute_planetary_hours(date, EUGENE_LAT, EUGENE_LON, tz=EUGENE_TZ)
        sunset = hours[11]["end_dt"]
        next_sunrise = hours[23]["end_dt"]
        night_length = (next_sunrise - sunset).total_seconds()
        night_hour = hours[12]
        hour_length = (night_hour["end_dt"] - night_hour["start_dt"]).total_seconds()
        assert abs(hour_length * 12 - night_length) < 1

    def test_unknown_timezone_raises(self):
        with pytest.raises(ZoneInfoNotFoundError):
            compute_planetary_hours(datetime.date(2026, 6, 28), EUGENE_LAT, EUGENE_LON, tz="Mars/Phobos")

    def test_dst_transition(self):
        # Day with DST fallback in November still yields 24 contiguous hours.
        date = datetime.date(2026, 11, 1)
        hours = compute_planetary_hours(date, EUGENE_LAT, EUGENE_LON, tz=EUGENE_TZ)
        assert len(hours) == 24
        for i in range(len(hours) - 1):
            # Allow 1 second tolerance for floating point rounding in time division
            diff = abs((hours[i]["end_dt"] - hours[i + 1]["start_dt"]).total_seconds())
            assert diff < 1
