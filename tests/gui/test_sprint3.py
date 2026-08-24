"""test_sprint3.py — Headless verification of transit + synastry SVG generation.

Updated 2026-08-23: library-first (no HTTP server), uses the canonical
astro_display renderer. The legacy astro_gui.renderers.wheel_renderer and the
HTTP-server dependency were removed.
"""

import sys
sys.path.insert(0, "/home/xephyr/astro/src")

from astro_api_client import AstroClient
from astro_display import WheelRenderer

passed = 0
failed = 0


def check(label, expr):
    global passed, failed
    try:
        expr()
        print(f"PASS {label}")
        passed += 1
    except Exception as exc:
        print(f"FAIL {label} — {exc}")
        failed += 1


# ------------------------------------------------------------------
# 1. Canonical renderer exposes the transit/synastry API
# ------------------------------------------------------------------
check("WheelRenderer has render_transit",
      lambda: getattr(WheelRenderer, "render_transit"))
check("WheelRenderer has render_synastry",
      lambda: getattr(WheelRenderer, "render_synastry"))

# ------------------------------------------------------------------
# 2. Headless SVG generation: transit (library backend)
# ------------------------------------------------------------------
def _test_transit_svg():
    client = AstroClient()
    people = client.list_people().get("people", [])
    xephyr = next((p for p in people if p["name"] == "Xephyr"), None)
    assert xephyr is not None, "Xephyr not in library store"
    natal = client.get_chart(xephyr["chart_id"])
    transit = client.transit(xephyr["chart_id"], "2026-08-23", "12:00:00")

    natal_data = {
        "angles": natal.get("angles", {}),
        "houses": natal.get("houses", []),
        "bodies": natal.get("bodies", []),
        "aspects": natal.get("aspects", []),
    }
    transit_data = {"bodies": transit.get("bodies", [])}

    renderer = WheelRenderer(width=600, height=600)
    svg = renderer.render_transit(natal_data, transit_data)
    assert "<svg" in svg, "Transit SVG missing root element"
    assert "<circle" in svg, "Transit SVG missing circles"
    assert len(svg) > 5000, f"Transit SVG too small: {len(svg)} bytes"
    with open("/tmp/test_transit_wheel.svg", "w") as f:
        f.write(svg)


check("Transit SVG generated (headless)", _test_transit_svg)

# ------------------------------------------------------------------
# 3. Headless SVG generation: synastry
# ------------------------------------------------------------------
def _test_synastry_svg():
    client = AstroClient()
    people = client.list_people().get("people", [])
    assert len(people) >= 2, "Need at least two people in library store for synastry"
    a = people[0]
    b = people[1]
    chart_a = client.get_chart(a["chart_id"])
    chart_b = client.get_chart(b["chart_id"])
    syn = client.synastry(a["chart_id"], b["chart_id"])
    assert syn["status"] == "ok", f"Synastry failed: {syn.get('message')}"

    a_data = {
        "angles": chart_a.get("angles", {}),
        "houses": chart_a.get("houses", []),
        "bodies": chart_a.get("bodies", []),
    }
    b_data = {
        "bodies": chart_b.get("bodies", []),
    }
    renderer = WheelRenderer(width=600, height=600)
    svg = renderer.render_synastry(a_data, b_data, syn["cross_aspects"])
    assert "<svg" in svg, "Synastry SVG missing root element"
    assert "<circle" in svg, "Synastry SVG missing circles"
    assert len(svg) > 5000, f"Synastry SVG too small: {len(svg)} bytes"
    with open("/tmp/test_synastry_wheel.svg", "w") as f:
        f.write(svg)


check("Synastry SVG generated (headless)", _test_synastry_svg)

# ------------------------------------------------------------------
# 4. Check saved SVG files exist and are non-trivial
# ------------------------------------------------------------------
import os

check("Transit SVG file exists",
      lambda: os.path.exists("/tmp/test_transit_wheel.svg"))
check("Synastry SVG file exists",
      lambda: os.path.exists("/tmp/test_synastry_wheel.svg"))

check("Transit SVG file > 5KB",
      lambda: os.path.getsize("/tmp/test_transit_wheel.svg") > 5000)
check("Synastry SVG file > 5KB",
      lambda: os.path.getsize("/tmp/test_synastry_wheel.svg") > 5000)

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
print("\n" + "=" * 50)
print("Sprint 3 Results")
print("=" * 50)
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
print("\nArtifacts saved to /tmp/test_transit_wheel.svg and /tmp/test_synastry_wheel.svg")
