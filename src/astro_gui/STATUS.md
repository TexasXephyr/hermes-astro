# ASTRO_GUI Implementation Notes

> Last updated: 2026-06-13 22:30  
> Sprint 3 + post-sprint glyph rendering update + LiberZodiac font integration

## Glyph Rendering (Post-Sprint 3 Update)

### What Changed
The SPEC-astro-gui.md calls for "text labels above/below filled circles" for planets and "abbreviated zodiac names" for sign labels. After user review, the rendering was updated to use Unicode astrological glyphs and reposition the filled circle.

### Current Layout

| Element | Radius | Description |
|---------|--------|-------------|
| Outer ring | 280 px | House cusp lines end here |
| Sign glyphs | 295 px | Zodiac glyphs (♈–♓) placed just outside outer ring |
| Planet glyphs | 230 px | Body glyphs (☉ ☽ ☿ ♀ ♂ ♃ ♄ ♅ ♆ ♇) |
| Degree labels | 248 px | Degree/minute text, just beyond glyph |
| Filled circle | 100 px | Aspect convergence dot (was at planet glyph radius) |

### Planet Glyph Mapping

```
Sun      → ☉  (U+2609)
Moon     → ☽  (U+263D)
Mercury  → ☿  (U+263F)
Venus    → ♀  (U+2640)
Mars     → ♂  (U+2642)
Jupiter  → ♃  (U+2643)
Saturn   → ♄  (U+2644)
Uranus   → ♅  (U+2645)
Neptune  → ♆  (U+2646)
Pluto    → ♇  (U+2647)
Node     → ☊  (U+260A) — Mean/True Node
Chiron   → ⚷  (U+26B7)
Lilith   → ⚸  (U+26B8)
```

Retrograde bodies append ℞ (U+211E) to the glyph string.

### Zodiac Glyph Mapping

```
Aries       → ♈  (U+2648)
Taurus      → ♉  (U+2649)
Gemini      → ♊  (U+264A)
Cancer      → ♋  (U+264B)
Leo         → ♌  (U+264C)
Virgo       → ♍  (U+264D)
Libra       → ♎  (U+264E)
Scorpio     → ♏  (U+264F)
Sagittarius → ♐  (U+2650)
Capricorn   → ♑  (U+2651)
Aquarius    → ♒  (U+2652)
Pisces      → ♓  (U+2653)
```

### Font Choice

- **DejaVu Sans** is used for all glyphs (loaded via `font-family="DejaVu Sans, sans-serif"` in SVG).
- **Astronomicon.ttf** was considered but rejected because it contains only Latin characters (192 glyphs, no astrological symbols).
- **AstroPanMono-Regular.ttf** is present on the system but unused.

### Why This Differs from SPEC

| SPEC Requirement | Actual Implementation | Rationale |
|------------------|----------------------|-----------|
| "Text block above/below circle" | Glyph at R_planet, circle at R_aspect | User requested glyphs + aspect-convergence dot |
| "Abbreviated zodiac names" (e.g. "Ari") | Unicode zodiac glyphs | User requested glyphs over abbreviations |
| Font: Astronomicon | Font: DejaVu Sans | Astronomicon lacks astrological glyphs on this system |

### Test Coverage

- All 9 Sprint 3 headless SVG tests pass.
- Generated artifacts: `/tmp/test_transit_wheel.svg`, `/tmp/test_synastry_wheel.svg`
- Verified: 12 zodiac glyphs, 10 planet glyphs, 24 aspect circles, 24 degree labels present in output.

---

## LiberZodiac Font Integration (2026-06-13)

### Problem
The user created a custom astrological font (`LiberZodiac`) combining Astronomicon glyphs with Liberation Sans. However, GTK's SVG renderer (`Gdk.Texture` → librsvg) could not resolve the user-installed font via fontconfig, even though `fc-match` and `fc-list` showed it correctly. The glyphs rendered as fallback (empty/blank) in the app.

### Solution
Embedded an `@font-face` CSS declaration inside the SVG `<defs>` block, pointing directly to the font file via `file://` URI. This bypasses fontconfig entirely — librsvg loads the font explicitly.

### Changes Made

1. **Built LiberZodiac font** (`~/.local/share/fonts/LiberZodiac-Regular.ttf`)
   - Base: Liberation Sans Regular (UPM 2048)
   - Glyphs transplanted from Astronomicon.ttf (UPM 1000 → scaled 2.048× via `TransformPen`)
   - 37 standard Unicode mappings (planets, zodiac, aspects, asteroids, nodes, etc.)
   - 66 PUA mappings (U+E000+) for unmapped glyphs (dwarf planets, angles, alchemy, etc.)
   - Name table updated: "LiberZodiac", copyright attribution preserved (OFL)

2. **Patched `wheel_renderer.py`**
   - `_defs()` method now injects `@font-face` CSS rule referencing the font file directly
   - All sign labels and planet glyphs use `font-family="LiberZodiac, DejaVu Sans, sans-serif"`
   - Sign labels and planet glyphs both at `font-size="18"`
   - File: `src/astro_gui/renderers/wheel_renderer.py`

3. **Build script saved**
   - `~/second-brain/projects/liberzodiac/build_liberzodiac.py` — standalone font builder
   - `~/second-brain/projects/liberzodiac/LiberZodiac-mapping.md` — full Unicode/PUA mapping table

### GTK Font Resolution Root Cause

- `fc-match "LiberZodiac"` → works (returns the .ttf file)
- `fc-list` → shows the font
- **BUT** `Gdk.Texture.new_from_filename()` (librsvg backend) → **does not** resolve user-installed fonts through fontconfig
- Confirmed via diagnostic: an SVG with `font-family="LiberZodiac"` rendered blank via Gdk.Texture
- **Same SVG with `@font-face { src: url("file:///...") }` → renders glyphs correctly**

### Diagnostic Artifacts

| File | Purpose |
|------|---------|
| `/tmp/test_file_fontface.svg` | Minimal test: `@font-face` with `file://` URI |
| `/tmp/test_file_fontface_gtk.png` | GTK-rendered PNG — **glyphs visible** ✓ |
| `/tmp/test_embedded_font.svg` | Test with base64-embedded font (533KB, also works) |
| `/tmp/test_wheel_with_fontface.svg` | Full wheel SVG with `@font-face` injected |
| `/tmp/test_wheel_with_fontface_gtk.png` | GTK-rendered wheel — verified different from pre-fix |

### Next Step

**Restart the app.** The `@font-face` fix is in `wheel_renderer.py` but GTK needs a fresh process to pick up the changed code. The Python module may or may not hot-reload reliably.

```bash
# Find and kill the running astro_gui process, then relaunch
pkill -f astro_gui
# or
ps aux | grep astro_gui
kill <PID>
```

After restart, click **Natal** — the wheel should render with LiberZodiac glyphs for all zodiac signs and planet bodies.

### Files Involved

- `~/.local/share/fonts/LiberZodiac-Regular.ttf` — the font (399KB, UPM 2048, 2621 glyphs total, 103 transplanted)
- `src/astro_gui/renderers/wheel_renderer.py` — SVG generator (patched with `@font-face`)
- `~/second-brain/projects/liberzodiac/build_liberzodiac.py` — font build script
- `~/second-brain/projects/liberzodiac/LiberZodiac-mapping.md` — codepoint documentation
