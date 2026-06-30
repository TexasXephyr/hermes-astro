# Astrology Tool — Build Log

## Project Structure

```
~/astro/
├── meson.build              # Root build file
├── src/
│   ├── astro_calc/          # C FFI wrapper around Swiss Ephemeris
│   │   ├── meson.build
│   │   ├── astro_calc.c
│   │   └── astro_calc.h
│   ├── astro_api/           # Python REST API (future)
│   ├── astro_analyze/       # Analysis engine (future)
│   └── astro_data/          # Database models (future)
├── tests/
│   └── test_astrolog.py     # Validation against JPL/Astrolog
└── docs/
```

## Phase 0: Swiss Ephemeris C Wrapper

### 2026-05-17 18:50  — Start Phase 0

- Status: ✅ In progress
- Task: Build C FFI wrapper around SE lib
- Using SE source from audit: ~/swisseph_test/pyswisseph-2.10.3.2/

### 2026-05-17 18:52 — Compiled SE library available

- libswe.so: 621KB shared library
- libswe.a: 915KB static library
- Header: swephexp.h

Next: Create C header + implementation file for our library interface.

## JPL Validation Gate Results (2026-05-18)

**Status: CONDITIONAL PASS — Proceeding to Phase 3**

| Metric | Result |
|--------|--------|
| Total tests | 70 (10 dates × 7 bodies) |
| Passed | 67/70 |
| Failed | 3/70 — all Moon positions |

**Moon limitation documented:**
- Moon positions accurate to ~5 arc-seconds using Moshier built-in ephemeris
- All other bodies (Sun, Mercury, Venus, Mars, Jupiter, Saturn): <1 arc-second vs JPL DE440
- To improve Moon accuracy: download SE ephemeris files (sepl_18.se1, semo_18.se1)
- Current precision meets "degree+minute" requirement

**Decision:** Proceed to Phase 3 with documented limitation.
