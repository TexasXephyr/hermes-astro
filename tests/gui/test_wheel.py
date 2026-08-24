"""test_wheel.py — API → SVG verification for Sprint 2 (library-first)."""

import sys
sys.path.insert(0, "/home/xephyr/astro/src")

from astro_api_client import AstroClient
from astro_display import WheelRenderer


def main():
    client = AstroClient()  # library backend, no server needed

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

    # 2. Load natal chart from the library store
    chart = client.get_chart(xephyr["chart_id"])
    assert chart is not None, "Missing natal chart"
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
    assert "<path" in svg, "Missing glyph paths"
    assert "<line" in svg, "Missing aspect line elements"
    assert "<circle" in svg, "Missing circle elements"
    assert "<polygon" in svg, "Missing house polygon elements"

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
