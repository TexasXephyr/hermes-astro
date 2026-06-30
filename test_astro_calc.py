#!/usr/bin/env python3
"""Test astro_calc import and basic functionality."""
from astro_calc import ac_init, ac_date_to_jd, ac_calc_chart, body_id_from_name

print("Testing astro_calc import...")
ac_init()
print("ac_init() OK")

jd = ac_date_to_jd(2000, 1, 1, 12, 0, 0, 0.0)
print(f"JD for 2000-01-01 12:00:00 UTC: {jd}")

# Test body name lookup
sun_id = body_id_from_name("Sun")
print(f"Sun body ID: {sun_id}")

# Test chart calculation
body_ids = [sun_id, body_id_from_name("Moon")]
chart = ac_calc_chart(jd, 0.0, 0.0, body_ids, "K")
print(f"Chart calculated: {chart['num_bodies']} bodies")
print("All tests passed!")
