#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/xephyr/astro/src')

import astro_api_client
print("Import OK")

client = astro_api_client.AstroClient()
print(f"Backend: {client.backend}")

# Test natal calculation
result = client.natal(
    name="Test",
    date="2000-01-01",
    time="12:00:00",
    timezone="UTC",
    latitude=0.0,
    longitude=0.0,
)
print(f"Natal status: {result['status']}")
print(f"Chart ID: {result['chart_id']}")
print(f"Bodies count: {len(result['bodies'])}")
print(f"Houses count: {len(result['houses'])}")
