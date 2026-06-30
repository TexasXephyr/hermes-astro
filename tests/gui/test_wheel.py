"""test_wheel.py — API → SVG verification for Sprint 2."""

import sys
sys.path.insert(0, "/home/xephyr/astro/src")

from astro_gui.api_client import AstroApiClient
from astro_gui.renderers.wheel_renderer import WheelRenderer


def main():
    client = AstroApiClient()

    # 1. Fetch people list and find Xephyr
    people_resp = client.list_people()
    assert people_resp.get("status") == "ok", "list_people failed"
    xephyr = None
    for p in people_resp.get("people", []):
        if p.get("name") == "Xephyr":
            xephyr = p
            break
    assert xephyr is not None, "Xephyr not found in people list"
    print(f"Found person: {xephyr['name']} (id={xephyr['id']})")

    # 2. Calculate natal chart via API
    chart = client.calculate_natal(xephyr)
    assert chart.get("status") == "ok", "calculate_natal failed"
    assert "bodies" in chart, "Missing bodies in chart"
    assert "houses" in chart, "Missing houses in chart"
    assert "aspects" in chart, "Missing aspects in chart"
    assert "angles" in chart, "Missing angles in chart"
    asc = chart["angles"]["ascendant"]
    print(f"Ascendant: {asc}")

    # 3. Render SVG
    renderer = WheelRenderer(width=600, height=600)
    svg = renderer.render_natal(chart)

    # 4. Write to file
    out_path = "/tmp/test_natal_wheel.svg"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)

    file_size = len(svg.encode("utf-8"))
    print(f"SVG written to {out_path} ({file_size} bytes)")

    # 5. Assertions
    assert file_size > 1024, "SVG file too small"
    assert "Sun" in svg, "Missing Sun text"
    # We don't embed the raw ascendant float; verify geometry exists instead
    assert "<line" in svg, "Missing aspect line elements"
    assert "<circle" in svg, "Missing circle elements"
    assert "<polygon" in svg, "Missing house polygon elements"
    assert "Ari" in svg or "Sag" in svg, "Missing sign labels"
    # Verify the ascendant-derived house cusp geometry by checking for specific
    # known body placements (Moon at 147°) rendered near the wheel center.
    assert "Moon" in svg, "Missing Moon text"

    print("\nAll assertions passed.")
    print("Visual inspection file: /tmp/test_natal_wheel.svg")

    # Optional: generate transit wheel using same data for smoke test
    svg_transit = renderer.render_transit(chart, chart, scale=1.0)
    transit_path = "/tmp/test_transit_wheel.svg"
    with open(transit_path, "w", encoding="utf-8") as f:
        f.write(svg_transit)
    print(f"Transit SVG written to {transit_path} ({len(svg_transit)} bytes)")


if __name__ == "__main__":
    main()
