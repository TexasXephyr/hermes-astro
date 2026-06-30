# Gap Analysis: Python `ephem` vs. `~/astro` Calculation Engine

## What `~/astro` currently computes

The existing engine (`src/astro_calc/`) is a C FFI wrapper around **Swiss Ephemeris**
(`pyswisseph-2.10.3.2 / libswe.so`).  It is consumed by `astro_api/astro_ctypes.py`
and the REST server.

| Feature | `~/astro` capability |
|---|---|
| Core bodies | Sun, Moon, Mercury–Pluto |
| Extended bodies | Mean Node, True Node, Lilith, Chiron, Ceres, Pallas, Juno, Vesta |
| Coordinates returned | Geocentric **tropical ecliptic longitude/latitude**, distance (AU), daily speed, retrograde flag, sign, sign degree, house placement |
| House systems | 22 systems via one-letter codes: Placidus, Koch, Equal, Whole Sign, Campanus, Regiomontanus, Porphyry, Morinus, Alcabitus, etc. |
| Angles | Ascendant, MC, ARMC, Vertex |
| Aspect engine | 9 aspects (conjunction, sextile, square, trine, opposition, semisextile, semisquare, sesquiquadrate, quincunx) with 4 orb presets; applying/separating detection |
| Date range | Very wide (SE Moshier fallback; optional JPL DE files) |
| Accuracy | JPL-validation gate: Sun/inner/outer planets <1 arc-second; Moon ~5 arc-seconds with Moshier, sub-arcsecond with SE ephemeris files |
| Precession/nutation | Handled by Swiss Ephemeris (full IAU model) |
| Speed / retrograde | Native via `swe_calc_ut` with `SEFLG_SPEED` |
| Asteroids | Native via SE asteroid IDs |
| Nodes | Native mean & true lunar nodes |
| Cookbook / analysis | Higher-level Python layers on top of the engine |

---

## What PyEphem (`ephem`) natively provides

PyEphem is a Python binding to the **XEphem / libastro** C routines (VSOP87D for
planets, simplified lunar/planetary theories).  It is an **astronomical**, not
astrological, toolkit.

| Capability | PyEphem support |
|---|---|
| Built-in solar-system bodies | Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, plus many planet moons |
| User-supplied minor bodies | Yes — comets/asteroids/satellites via `ephem.readdb()` / `readtle()` with orbital elements in XEphem format |
| Coordinate outputs | Apparent/topocentric RA/Dec; geocentric RA/Dec; az/alt; heliocentric longitude/latitude (`hlon/hlat`); ecliptic longitude/latitude via `ephem.Ecliptic()` conversion |
| Precession / nutation / aberration | Applied to equatorial outputs; ecliptic output available via conversion from equatorial |
| House systems / cusps / Ascendant / MC | **Not provided** |
| Aspect engine | Only `ephem.separation()` for angular distance; no named aspects, orbs, applying/separating logic |
| Speed / retrograde | **No native daily speed attribute**. Retrograde must be inferred by finite differencing or sign of `hlon` change over time |
| Nodes | **No built-in Mean Node / True Node**. True node can only be approximated by iteratively finding Moon-Sun longitude crossings |
| Date range | Modern era is very accurate; far historical/future accuracy degrades compared with JPL DE |
| Accuracy | Planetary: VSOP87D, generally "scientific-grade" but historically a step below JPL DE406/DE440 (arc-second to sub-arc-second differences) |

---

## Feature-by-feature gap

| `~/astro` requirement | Supported by `ephem` natively? | Gap severity |
|---|---|---|
| Geocentric tropical ecliptic longitude | Partial — must convert apparent RA/Dec → Ecliptic; `hlon/hlat` is heliocentric for planets | Medium |
| Geocentric ecliptic latitude & distance | Same conversion required | Medium |
| Daily speed & retrograde flag | **No** — must finite-difference | High |
| House cusps & 22 house systems | **No** — no API at all | High |
| Ascendant / MC / Vertex / ARMC | **No** — no API at all | High |
| Aspect detection with orbs & applying/separating | **No** — only raw angular separation; would need custom implementation | High |
| Mean Node / True Node | **No** built-in True/Mean node; approximations only | High |
| Lilith (mean/apogee) | **No** built-in equivalent | High |
| Chiron, Ceres, Pallas, Juno, Vesta | User must supply orbital elements via `readdb()` for each; not built-in | Medium |
| 9 named aspect types + 4 orb presets | Custom code required | High |
| Sign, sign-degree, house assignment | Custom code required | Medium |

---

## Accuracy / performance notes

| Dimension | `~/astro` (Swiss Ephemeris) | PyEphem |
|---|---|---|
| Planetary ephemeris | JPL DE-based (DE440/441 family) | VSOP87D analytic series |
| Typical accuracy | Sub-arcsecond for current era; validated against JPL | Arc-second-level modern era, degrades outside ~3000 BCE–3000 CE |
| Moon | High precision with SE files; Moshier fallback ~5 arc-sec | Simpler lunar theory; good but generally not JPL-grade |
| Speed | Analytic, no extra cost | Requires finite differencing (slower, less exact) |
| Performance | Fast C, single call per body/date | Fast C per body, but extra conversions + finite differencing add overhead |
| Dependencies | `libswe.so`, optional `.se1` ephemeris files | Pure pip install (`ephem`) |

---

## Recommendation

**Do not replace the core engine with PyEphem.**

PyEphem lacks the astrological primitives that `~/astro` is built on:

1. **No house calculation** — houses, Ascendant, MC, Vertex are non-negotiable for
   the current chart API.
2. **No native speed/retrograde** — the engine and aspect logic rely on daily
   speed for applying/separating and retrograde detection.
3. **No native nodes / Lilith / asteroids** — would require manual element
   catalogs and custom approximations.
4. **No aspect engine / orbs** — would have to reimplement the entire aspect
   subsystem.
5. **Coordinate mismatch** — astrology requires geocentric tropical ecliptic
   longitude; PyEphem’s native outputs are equatorial/topocentric, requiring
   conversion and careful epoch handling.

**Acceptable use cases for PyEphem:**
- Standalone rise/set/phase/elongation astronomy utilities.
- Quick verification scripts where house-free ecliptic positions are sufficient.
- Situations where avoiding the SE binary dependency is more important than
  astrological completeness.

**Better alternatives if Swiss Ephemeris dependency is a concern:**
- `pyswisseph` (direct Python binding to SE; keeps all features).
- `flatlib` / `immanuel` (higher-level astrology libraries that still use SE
  under the hood and provide houses, aspects, nodes, asteroids).
- `skyfield` + custom house code (NASA JPL ephemeris, but still requires
  implementing house cusps and aspect logic).

**Verdict:** Keep the Swiss-Ephemeris-backed core engine. PyEphem could serve as
an auxiliary library for non-astrological ephemeris tasks only.
