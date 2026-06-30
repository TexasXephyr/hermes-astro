"""test_sprint3.py — Headless verification of transit + synastry SVG generation."""

import sys
import importlib.util

def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

# Load modules bypassing astro_gui/__init__.py which imports gi
api_client = _load_module("astro_gui.api_client", "/home/xephyr/astro/src/astro_gui/api_client.py")
wheel_renderer = _load_module("astro_gui.renderers.wheel_renderer", "/home/xephyr/astro/src/astro_gui/renderers/wheel_renderer.py")

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
# 1. Verify new api_client method exists
# ------------------------------------------------------------------
check("AstroApiClient has get_natal_chart_for_person",
      lambda: getattr(api_client.AstroApiClient, "get_natal_chart_for_person"))

# ------------------------------------------------------------------
# 2. Verify wheel_renderer has synastry method
# ------------------------------------------------------------------
check("WheelRenderer has render_synastry",
      lambda: getattr(wheel_renderer.WheelRenderer, "render_synastry"))

check("WheelRenderer has _render_cross_aspects",
      lambda: getattr(wheel_renderer.WheelRenderer, "_render_cross_aspects"))

# ------------------------------------------------------------------
# 3. Headless SVG generation: transit
# ------------------------------------------------------------------
def _test_transit_svg():
    import json, urllib.request
    BASE = "http://localhost:8081"
    # Get Xephyr's chart
    req = urllib.request.Request(BASE + "/v1/people/5/natal-chart")
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    chart = data["natal_chart"]
    chart_id = chart["chart_id"]

    # Get transit data
    payload = {"natal_chart_id": chart_id, "date": "2026-06-13", "time": "18:00:00"}
    req = urllib.request.Request(
        BASE + "/v1/chart/transit",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    resp = urllib.request.urlopen(req)
    transit = json.loads(resp.read())
    assert transit["status"] == "ok", f"Transit API failed: {transit.get('message')}"

    natal_data = {
        "angles": chart["positions"]["angles"],
        "houses": chart["positions"]["houses"],
        "bodies": transit["bodies"],
        "aspects": chart.get("aspects", []),
    }
    transit_data = {"bodies": transit["transiting_bodies"]}

    renderer = wheel_renderer.WheelRenderer(width=600, height=600)
    svg = renderer.render_transit(natal_data, transit_data)
    assert "<svg" in svg, "Transit SVG missing root element"
    assert "<circle" in svg, "Transit SVG missing circles"
    assert len(svg) > 5000, f"Transit SVG too small: {len(svg)} bytes"
    # Save for inspection
    with open("/tmp/test_transit_wheel.svg", "w") as f:
        f.write(svg)

check("Transit SVG generated (headless)", _test_transit_svg)

# ------------------------------------------------------------------
# 4. Headless SVG generation: synastry
# ------------------------------------------------------------------
def _test_synastry_svg():
    import json, urllib.request
    BASE = "http://localhost:8081"
    # Get both charts
    req_a = urllib.request.Request(BASE + "/v1/people/5/natal-chart")
    req_b = urllib.request.Request(BASE + "/v1/people/6/natal-chart")
    chart_a = json.loads(urllib.request.urlopen(req_a).read())["natal_chart"]
    chart_b = json.loads(urllib.request.urlopen(req_b).read())["natal_chart"]

    # Get synastry
    payload = {"person_a": chart_a["chart_id"], "person_b": chart_b["chart_id"]}
    req = urllib.request.Request(
        BASE + "/v1/chart/synastry",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    syn = json.loads(urllib.request.urlopen(req).read())
    assert syn["status"] == "ok", f"Synastry API failed: {syn.get('message')}"

    a_data = {
        "angles": chart_a["positions"]["angles"],
        "houses": chart_a["positions"]["houses"],
        "bodies": chart_a["positions"]["bodies"],
    }
    b_data = {
        "bodies": chart_b["positions"]["bodies"],
    }
    renderer = wheel_renderer.WheelRenderer(width=600, height=600)
    svg = renderer.render_synastry(a_data, b_data, syn["cross_aspects"])
    assert "<svg" in svg, "Synastry SVG missing root element"
    assert "<circle" in svg, "Synastry SVG missing circles"
    assert len(svg) > 5000, f"Synastry SVG too small: {len(svg)} bytes"
    # Save for inspection
    with open("/tmp/test_synastry_wheel.svg", "w") as f:
        f.write(svg)

check("Synastry SVG generated (headless)", _test_synastry_svg)

# ------------------------------------------------------------------
# 5. Check saved SVG files exist and are non-trivial
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
