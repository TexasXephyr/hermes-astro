#!/usr/bin/env python3
"""Verify acceptance criteria for Sprint 3: library-first AstroClient."""
from astro_api_client import AstroClient
import os

print("=" * 60)
print("Sprint 3 Acceptance Criteria Verification")
print("=" * 60)

# Test 1: Default backend is library
client = AstroClient()
assert client.backend == 'library', f'Expected library, got {client.backend}'
print('✓ Default backend is library')

# Test 2: Natal computes without server
result = client.natal('Test', '2000-01-01', '12:00:00', 'UTC', 0.0, 0.0)
assert result['status'] == 'ok'
assert 'chart_id' in result
assert 'bodies' in result
assert 'houses' in result
assert 'aspects' in result
print(f'✓ Natal computes without server (chart_id: {result["chart_id"][:8]}...)')

# Test 3: Transit computes
transit = client.transit(result['chart_id'], '2026-06-28')
assert transit['status'] == 'ok'
assert 'bodies' in transit
print('✓ Transit computes without server')

# Test 4: Period impact computes
impact = client.period_impact(result['chart_id'], '2026-06-28', orb_days=7)
assert 'impact' in impact
assert 'active_transits' in impact['impact']
print('✓ Period impact computes without server')

# Test 5: HTTP backend via env var
os.environ['ASTRO_API_URL'] = 'http://localhost:8081'
client_http = AstroClient()
assert client_http.backend == 'http'
print('✓ ASTRO_API_URL env var selects HTTP backend')

# Test 6: Validation works
try:
    client.natal('Test', '2000-01-01', '12:00:00', 'UTC', 91.0, 0.0)
    assert False, 'Should have raised ValueError for invalid lat'
except ValueError as e:
    print(f'✓ Invalid latitude raises ValueError: {e}')

try:
    client.natal('Test', '2000-01-01', '12:00:00', 'UTC', 0.0, 181.0)
    assert False, 'Should have raised ValueError for invalid lon'
except ValueError as e:
    print(f'✓ Invalid longitude raises ValueError: {e}')

try:
    client.natal('Test', '2000-01-01', '12:00:00', 'Mars/Phobos', 0.0, 0.0)
    assert False, 'Should have raised ValueError for invalid timezone'
except ValueError as e:
    print(f'✓ Invalid timezone raises ValueError: {e}')

print()
print("=" * 60)
print("ALL ACCEPTANCE CRITERIA VERIFIED")
print("=" * 60)
