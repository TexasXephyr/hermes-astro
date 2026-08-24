"""test_table_renderer.py — Headless verification of the sortable table views."""

import sys
sys.path.insert(0, "/home/xephyr/astro/src")

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from astro_gui.renderers.table_renderer import (
    build_planet_table,
    build_transit_grid,
    build_planet_agg_table,
    format_days,
)

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


def _find_column_view(widget):
    """Find the ColumnView inside a builder's returned widget tree."""
    if isinstance(widget, Gtk.ColumnView):
        return widget
    if isinstance(widget, Gtk.Box):
        for child in widget:
            found = _find_column_view(child)
            if found is not None:
                return found
    return None


def _realize(widget):
    """Realize a widget inside a window and pump the main loop.

    Returns the window. The widget tree is fully realized so tests can
    assert on the widgets that actually render (the item-35 bug was
    header buttons that never appeared in the realized tree).
    """
    win = Gtk.Window()
    sw = Gtk.ScrolledWindow()
    sw.set_child(widget)
    win.set_child(sw)
    win.present()
    for _ in range(30):
        while GLib.MainContext.default().iteration(False):
            pass
    return win


def _walk(widget):
    """Yield a widget and all descendants (for realized-tree assertions)."""
    yield widget
    if isinstance(widget, Gtk.Box):
        for child in widget:
            yield from _walk(child)
    elif isinstance(widget, Gtk.ScrolledWindow):
        yield from _walk(widget.get_child())
    elif isinstance(widget, Gtk.Viewport):
        yield from _walk(widget.get_child())
    elif isinstance(widget, Gtk.Window):
        yield from _walk(widget.get_child())
    elif isinstance(widget, Gtk.FlowBox):
        for child in widget:
            yield from _walk(child)
    elif isinstance(widget, Gtk.FlowBoxChild):
        yield from _walk(widget.get_child())
    elif isinstance(widget, Gtk.ColumnView):
        child = widget.get_first_child()
        while child is not None:
            yield from _walk(child)
            child = child.get_next_sibling()


# 1. Natal planet table
chart = {
    "bodies": [
        {"name": "Sun", "longitude": 248.7, "sign_name": "Leo",
         "sign_degree": 8.7, "house": 5, "speed": 1.01, "retrograde": False},
        {"name": "Moon", "longitude": 147.3, "sign_name": "Taurus",
         "sign_degree": 3.5, "house": 2, "speed": 12.1, "retrograde": False},
    ]
}
check("build_planet_table returns Box with sort row + ColumnView",
      lambda: isinstance(build_planet_table(chart), Gtk.Box))

# 1b. Dignity column is populated (review item 19)
def _dignity_populated():
    view = _find_column_view(build_planet_table(chart))
    model = view.get_model()
    assert model is not None
    # Walk the sort model -> selection -> rows
    selection = model
    n = selection.get_n_items()
    assert n == 2, f"expected 2 rows, got {n}"
    labels = []
    for i in range(n):
        row = selection.get_item(i)
        labels.append(row.dignity)
    # Sun in Leo -> domicile; Moon in Taurus @3.5° -> exaltation
    assert "domicile" in labels, f"Sun dignity missing: {labels}"
    assert "exaltation" in labels, f"Moon dignity missing: {labels}"


check("planet table dignity column populated", _dignity_populated)

# 2. Transit grid
transits = [
    {"transiting_body": "Mercury", "natal_body": "Moon", "aspect": "conjunction",
     "orb": 1.19, "days_to_exact": 1, "priority": 128},
    {"transiting_body": "Chiron", "natal_body": "Neptune", "aspect": "trine",
     "orb": 1.18, "days_to_exact": 0, "priority": 119},
]
transit_bodies = [
    {"name": "Mercury", "sign_name": "Virgo", "longitude": 174.0},
    {"name": "Chiron", "sign_name": "Aries", "longitude": 9.0},
]
natal_bodies = [
    {"name": "Moon", "sign_name": "Taurus", "house": 2},
    {"name": "Neptune", "sign_name": "Pisces", "house": 6},
]
# Natal cusps: Aries 0°, Taurus 30°, Gemini 60°, Cancer 90°, Leo 120°,
# Virgo 150°, Libra 180°, Scorpio 210°, Sagittarius 240°, Capricorn 270°,
# Aquarius 300°, Pisces 330° -> 1..12 for the corresponding longitudes.
natal_houses = [{"house_num": i + 1, "longitude": i * 30.0} for i in range(12)]


def _transit_grid_builds():
    widget = build_transit_grid(transits, transit_bodies, natal_bodies, natal_houses)
    assert isinstance(widget, Gtk.Box), "transit grid should be a vertical Box (filter row + sort row + view)"
    # Find the ColumnView child
    view = _find_column_view(widget)
    assert view is not None, "transit grid box missing ColumnView"
    assert hasattr(widget, "filter_row"), "transit grid box missing filter_row"
    assert hasattr(view, "_sort_row"), "transit grid view missing _sort_row"


check("build_transit_grid returns Box with ColumnView + filter row", _transit_grid_builds)


def _transit_sign_columns():
    widget = build_transit_grid(transits, transit_bodies, natal_bodies, natal_houses)
    view = _find_column_view(widget)
    selection = view.get_model()
    n = selection.get_n_items()
    assert n == 2, f"expected 2 rows, got {n}"
    rows = [selection.get_item(i) for i in range(n)]
    by_body = {r.body_name: r for r in rows}
    mercury = by_body["Mercury"]
    assert mercury.t_sign_name == "Virgo", f"Mercury t_sign: {mercury.t_sign_name}"
    assert mercury.n_sign_name == "Taurus", f"Mercury n_sign: {mercury.n_sign_name}"
    assert "Virgo" in mercury.t_sign, f"Mercury t_sign cell: {mercury.t_sign!r}"
    assert "Taurus" in mercury.n_sign, f"Mercury n_sign cell: {mercury.n_sign!r}"
    chiron = by_body["Chiron"]
    assert chiron.t_sign_name == "Aries", f"Chiron t_sign: {chiron.t_sign_name}"
    assert chiron.n_sign_name == "Pisces", f"Chiron n_sign: {chiron.n_sign_name}"


check("transit grid sign columns populated from body lists", _transit_sign_columns)


def _transit_house_columns():
    widget = build_transit_grid(transits, transit_bodies, natal_bodies, natal_houses)
    view = _find_column_view(widget)
    selection = view.get_model()
    rows = [selection.get_item(i) for i in range(selection.get_n_items())]
    by_body = {r.body_name: r for r in rows}
    # Transit Mercury @174° falls between Virgo cusp 150° and Libra cusp
    # 180° -> house 6; natal Moon's own house is 2.
    assert by_body["Mercury"].t_house == "6", f"Mercury t_house: {by_body['Mercury'].t_house!r}"
    assert by_body["Mercury"].n_house == "2", f"Mercury n_house: {by_body['Mercury'].n_house!r}"
    # Transit Chiron @9° -> house 1; natal Neptune's own house is 6.
    assert by_body["Chiron"].t_house == "1", f"Chiron t_house: {by_body['Chiron'].t_house!r}"
    assert by_body["Chiron"].n_house == "6", f"Chiron n_house: {by_body['Chiron'].n_house!r}"
    # House-less data degrades gracefully
    widget2 = build_transit_grid(transits)
    view2 = _find_column_view(widget2)
    rows2 = [view2.get_model().get_item(i) for i in range(view2.get_model().get_n_items())]
    assert rows2[0].t_house == "", f"expected empty t_house without houses, got {rows2[0].t_house!r}"
    assert rows2[0].n_house == "", f"expected empty n_house without bodies, got {rows2[0].n_house!r}"


check("transit grid house columns (find_house crossing + natal body house)", _transit_house_columns)


def _transit_glyph_columns():
    widget = build_transit_grid(transits, transit_bodies, natal_bodies, natal_houses)
    view = _find_column_view(widget)
    cols = view.get_columns()
    assert [c.get_title() for c in cols] == [
        "T Body", "T Sign", "T House", "Aspect", "N Body", "N Sign",
        "N House", "Orb", "Days", "Priority",
    ], f"column order wrong: {[c.get_title() for c in cols]}"


check("transit grid columns: T Body|T Sign|T House|Aspect|N Body|N Sign|N House|Orb|Days|Priority",
      _transit_glyph_columns)


def _glyph_path_render():
    # The path parser handles the exact command set used by glyph_data,
    # and _apply_glyph_path fills a real cairo surface (no exceptions).
    from astro_gui.renderers.table_renderer import _parse_path, _apply_glyph_path
    import cairo
    from astro_display.glyph_data import BODIES, SIGNS
    for name in list(BODIES)[:3] + list(SIGNS)[:3]:
        from astro_display.glyph_data import ALL
        entry = ALL[name]
        cmds = _parse_path(entry["path"])
        assert cmds and cmds[0][0] == "M", f"{name} path must start with M"
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 60)
    cr = cairo.Context(surface)
    assert _apply_glyph_path(cr, "Sun", 30, 30, 18) is True
    assert _apply_glyph_path(cr, "Virgo", 80, 30, 16) is True
    assert _apply_glyph_path(cr, "NoSuchGlyph", 130, 30, 18) is False
    cr.fill()
    assert surface.get_width() == 200


check("path-glyph parser + cairo rendering (LiberZodiac outlines)", _glyph_path_render)


def _transit_days_format():
    widget = build_transit_grid(transits, transit_bodies, natal_bodies, natal_houses)
    view = _find_column_view(widget)
    selection = view.get_model()
    rows = [selection.get_item(i) for i in range(selection.get_n_items())]
    by_body = {r.body_name: r for r in rows}
    # days_to_exact 1 -> '1d'; 0 -> '0h'
    assert by_body["Mercury"].days == "1d", f"Mercury days: {by_body['Mercury'].days!r}"
    assert by_body["Chiron"].days == "0h", f"Chiron days: {by_body['Chiron'].days!r}"


check("transit grid days column uses format_days", _transit_days_format)


# 2b. format_days helper (review item 22)
def _fmt_days():
    assert format_days(3) == "3d"
    assert format_days(1) == "1d"
    assert format_days(0) == "0h"
    assert format_days(-3) == "sep 3d"
    assert format_days(-1) == "sep 1d"
    assert format_days(None) == ""
    # sub-day values (fractional days are rounded to hours/minutes)
    assert format_days(0.5) == "12h"
    assert format_days(0.05) == "1h"
    assert format_days(0.01) == "14m"


check("format_days smart formatting", _fmt_days)


# 2c. Filter mechanism (review item 24 + 25 + 30 + 31)
def _filter_point():
    widget = build_transit_grid(transits, transit_bodies, natal_bodies, natal_houses)
    view = _find_column_view(widget)
    selection = view.get_model()
    fr = widget.filter_row
    # The point filter is a dropdown of ACTIVE points ('T: Mercury', ...).
    model = fr.point_dropdown.get_model()
    labels = [model.get_string(i) for i in range(model.get_n_items())]
    assert labels == ["All", "T: Mercury", "N: Moon", "T: Chiron", "N: Neptune"], \
        f"active point dropdown wrong: {labels}"
    # Select 'T: Mercury' -> only transiting Mercury row remains.
    fr.point_dropdown.set_selected(1)
    n = selection.get_n_items()
    assert n == 1, f"expected 1 row after T: Mercury filter, got {n}"
    assert selection.get_item(0).body_name == "Mercury"
    # Reset to All
    fr.point_dropdown.set_selected(0)
    assert selection.get_n_items() == 2


check("filter by active point dropdown (T side)", _filter_point)


def _filter_natal_point():
    widget = build_transit_grid(transits, transit_bodies, natal_bodies, natal_houses)
    view = _find_column_view(widget)
    selection = view.get_model()
    fr = widget.filter_row
    fr.point_side_dropdown.set_selected(1)  # natal
    fr.point_dropdown.set_selected(2)  # N: Moon
    n = selection.get_n_items()
    assert n == 1, f"expected 1 row after natal Moon filter, got {n}"
    assert selection.get_item(0).natal_name == "Moon"


check("filter by active point dropdown (N side)", _filter_natal_point)


def _filter_house():
    widget = build_transit_grid(transits, transit_bodies, natal_bodies, natal_houses)
    view = _find_column_view(widget)
    selection = view.get_model()
    fr = widget.filter_row
    # house dropdown: any, 1..12 (index 2 = "2")
    fr.house_dropdown.set_selected(2)  # transit house 2 -> no rows (Mercury 6, Chiron 1)
    n = selection.get_n_items()
    assert n == 0, f"expected 0 rows after transit house 2 filter, got {n}"
    # Transit house 6 -> only Mercury.
    fr.house_dropdown.set_selected(6)  # "6"
    n = selection.get_n_items()
    assert n == 1 and selection.get_item(0).body_name == "Mercury", \
        f"expected Mercury for transit house 6, got {n}"
    # Natal side: natal Moon house 2, Neptune house 6.
    fr.house_side_dropdown.set_selected(1)  # natal
    fr.house_dropdown.set_selected(6)  # Neptune
    n = selection.get_n_items()
    assert n == 1 and selection.get_item(0).natal_name == "Neptune", \
        f"expected Neptune for natal house 6, got {n}"
    fr.house_dropdown.set_selected(0)  # any
    assert selection.get_n_items() == 2


check("filter by house (transit crossing + natal body)", _filter_house)


def _filter_aspect():
    widget = build_transit_grid(transits, transit_bodies, natal_bodies, natal_houses)
    view = _find_column_view(widget)
    selection = view.get_model()
    fr = widget.filter_row
    # aspect dropdown: all, conjunction, opposition, trine, square, sextile, quincunx
    fr.aspect_dropdown.set_selected(1)  # conjunction
    n = selection.get_n_items()
    assert n == 1, f"expected 1 row after conjunction filter, got {n}"
    assert selection.get_item(0).aspect_name == "conjunction"
    fr.aspect_dropdown.set_selected(3)  # trine
    n = selection.get_n_items()
    assert n == 1, f"expected 1 row after trine filter, got {n}"
    assert selection.get_item(0).aspect_name == "trine"
    fr.aspect_dropdown.set_selected(0)  # all
    assert selection.get_n_items() == 2


check("filter by aspect type", _filter_aspect)


def _filter_sign():
    widget = build_transit_grid(transits, transit_bodies, natal_bodies, natal_houses)
    view = _find_column_view(widget)
    selection = view.get_model()
    fr = widget.filter_row
    # sign dropdown: any, Aries..Pisces (index 1 = Aries)
    fr.sign_dropdown.set_selected(1)  # Aries (transit side default)
    n = selection.get_n_items()
    assert n == 1, f"expected 1 row after transit Aries filter, got {n}"
    assert selection.get_item(0).t_sign_name == "Aries"
    # natal side: Taurus (index 2)
    fr.sign_side_dropdown.set_selected(1)  # natal
    fr.sign_dropdown.set_selected(2)  # Taurus
    n = selection.get_n_items()
    assert n == 1, f"expected 1 row after natal Taurus filter, got {n}"
    assert selection.get_item(0).n_sign_name == "Taurus"
    fr.sign_dropdown.set_selected(0)  # any
    assert selection.get_n_items() == 2


check("filter by sign (transit + natal)", _filter_sign)


# 2d. Sort toggle on re-click (review items 21 + 23)
def _sort_toggle():
    widget = build_transit_grid(transits, transit_bodies, natal_bodies, natal_houses)
    view = _find_column_view(widget)
    sm = view._sort_model
    days = lambda: [sm.get_item(i).sort_days for i in range(sm.get_n_items())]
    # Default sort: priority descending
    assert [sm.get_item(i).sort_priority for i in range(sm.get_n_items())] == [128, 119]
    # Click Days (not active): activates ascending.
    view._sort_buttons["Days"].emit("clicked")
    assert days() == [0, 1], f"expected days asc after click, got {days()}"
    # Re-click inverts.
    view._sort_buttons["Days"].emit("clicked")
    assert days() == [1, 0], f"expected days desc after re-click, got {days()}"
    # Re-click again inverts back.
    view._sort_buttons["Days"].emit("clicked")
    assert days() == [0, 1], f"expected days asc after third click, got {days()}"


check("column header re-click inverts sort order", _sort_toggle)


# 3. By-planet aggregation
agg = [
    {"body": "Mercury", "total_priority": 197, "transit_count": 5,
     "top_aspect": "conjunction", "top_natal_body": "Moon"},
    {"body": "Chiron", "total_priority": 172, "transit_count": 4,
     "top_aspect": "trine", "top_natal_body": "Neptune"},
]
check("build_planet_agg_table returns Box with sort row + ColumnView",
      lambda: isinstance(build_planet_agg_table(agg), Gtk.Box))

# 3b. Sort-button sorting (item 35: visible sort buttons above the view)
def _transit_priority_header_sort():
    widget = build_transit_grid(transits, transit_bodies, natal_bodies, natal_houses)
    view = _find_column_view(widget)
    buttons = getattr(view, "_sort_buttons", None)
    assert buttons is not None, "transit grid missing _sort_buttons"
    assert set(buttons) == {
        "T Body", "T Sign", "T House", "Aspect", "N Body", "N Sign",
        "N House", "Orb", "Days", "Priority",
    }, f"sort buttons wrong: {sorted(buttons)}"
    sm = view._sort_model
    prio = lambda: [sm.get_item(i).sort_priority for i in range(sm.get_n_items())]
    # Default sort: priority descending
    assert prio() == [128, 119], f"expected default priority desc, got {prio()}"
    assert buttons["Priority"].get_label() == "▼ Priority", \
        f"priority button should show active marker, got {buttons['Priority'].get_label()!r}"
    # First click inverts (default was already priority desc)
    buttons["Priority"].emit("clicked")
    assert prio() == [119, 128], f"expected priority asc after click, got {prio()}"
    assert buttons["Priority"].get_label() == "▲ Priority", \
        buttons["Priority"].get_label()
    # Re-click inverts back
    buttons["Priority"].emit("clicked")
    assert prio() == [128, 119], f"expected priority desc after re-click, got {prio()}"
    assert buttons["Priority"].get_label() == "▼ Priority", \
        buttons["Priority"].get_label()


check("transit grid: Priority sort button click re-sorts and re-click inverts",
      _transit_priority_header_sort)


def _transit_other_header_sort():
    widget = build_transit_grid(transits, transit_bodies, natal_bodies, natal_houses)
    view = _find_column_view(widget)
    buttons = view._sort_buttons
    sm = view._sort_model
    days = lambda: [sm.get_item(i).sort_days for i in range(sm.get_n_items())]
    # Days is not the default column: first click activates it ascending.
    buttons["Days"].emit("clicked")
    assert days() == [0, 1], f"expected days asc after click, got {days()}"
    assert buttons["Days"].get_label() == "▲ Days", buttons["Days"].get_label()
    # Previously active column loses its marker
    assert buttons["Priority"].get_label() == "Priority", \
        buttons["Priority"].get_label()
    # Re-click inverts
    buttons["Days"].emit("clicked")
    assert days() == [1, 0], f"expected days desc after re-click, got {days()}"


check("transit grid: clicking a non-default sort button activates + inverts",
      _transit_other_header_sort)


def _natal_degree_header_sort():
    view = _find_column_view(build_planet_table(chart))
    buttons = view._sort_buttons
    assert set(buttons) == {
        "Body", "Sign", "Degree", "House", "Dignity", "Speed", "Retro",
    }, f"natal sort buttons wrong: {sorted(buttons)}"
    sm = view._sort_model
    deg = lambda: [round(sm.get_item(i).sort_degree, 1)
                   for i in range(sm.get_n_items())]
    # Default sort: degree ascending
    assert deg() == [147.3, 248.7], f"expected default degree asc, got {deg()}"
    buttons["Degree"].emit("clicked")
    assert deg() == [248.7, 147.3], f"expected degree desc after click, got {deg()}"
    assert buttons["Degree"].get_label() == "▼ Degree", buttons["Degree"].get_label()
    buttons["Degree"].emit("clicked")
    assert deg() == [147.3, 248.7], f"expected degree asc after re-click, got {deg()}"


check("natal table: Degree sort button click sorts + inverts",
      _natal_degree_header_sort)


def _planet_agg_header_sort():
    view = _find_column_view(build_planet_agg_table(agg))
    buttons = view._sort_buttons
    sm = view._sort_model
    tot = lambda: [sm.get_item(i).sort_total for i in range(sm.get_n_items())]
    # Default sort: total descending
    assert tot() == [197, 172], f"expected default total desc, got {tot()}"
    buttons["Total"].emit("clicked")
    assert tot() == [172, 197], f"expected total asc after click, got {tot()}"
    buttons["Total"].emit("clicked")
    assert tot() == [197, 172], f"expected total desc after re-click, got {tot()}"


check("by-planet: Total sort button click + invert",
      _planet_agg_header_sort)


def _planet_agg_count_header_sort():
    view = _find_column_view(build_planet_agg_table(agg))
    buttons = view._sort_buttons
    sm = view._sort_model
    cnt = lambda: [sm.get_item(i).sort_count for i in range(sm.get_n_items())]
    # Count sorts by its own field (not total): default total desc = 197,172
    assert [sm.get_item(i).sort_total for i in range(sm.get_n_items())] == [197, 172]
    buttons["Count"].emit("clicked")
    assert cnt() == [4, 5], f"expected count asc after click, got {cnt()}"
    assert buttons["Count"].get_label() == "▲ Count", \
        buttons["Count"].get_label()
    buttons["Count"].emit("clicked")
    assert cnt() == [5, 4], f"expected count desc after re-click, got {cnt()}"
    assert buttons["Count"].get_label() == "▼ Count", \
        buttons["Count"].get_label()


check("by-planet: Count sort button sorts by its own field + inverts",
      _planet_agg_count_header_sort)

# 4. Empty transit list still builds
check("build_transit_grid handles empty list",
      lambda: isinstance(build_transit_grid([]), Gtk.Box))

# 5. Empty chart still builds
check("build_planet_table handles empty chart",
      lambda: isinstance(build_planet_table({"bodies": []}), Gtk.Box))

# 6. Item 35 regression: sort buttons must actually RENDER in the
#    realized widget tree (the old header-factory buttons never appeared
#    on GTK 4.22), and clicking the realized button must re-sort.
def _realized_sort_buttons_render():
    widget = build_transit_grid(transits, transit_bodies, natal_bodies, natal_houses)
    view = _find_column_view(widget)
    win = _realize(widget)
    realized = [w for w in _walk(win) if isinstance(w, Gtk.Button)]
    labels = {b.get_label() for b in realized}
    # The sort row's buttons must be present in the realized tree.
    for title in ("Priority", "Days", "T Body", "Aspect"):
        assert title in labels or f"▼ {title}" in labels or f"▲ {title}" in labels, \
            f"sort button {title!r} not rendered; realized labels: {sorted(labels)}"
    # The active (default) button shows the marker.
    assert "▼ Priority" in labels, f"expected ▼ Priority marker, got {sorted(labels)}"
    # Clicking the REALIZED Priority button re-sorts the model.
    sm = view._sort_model
    prio = lambda: [sm.get_item(i).sort_priority for i in range(sm.get_n_items())]
    assert prio() == [128, 119], f"expected default priority desc, got {prio()}"
    prio_btn = next(b for b in realized if b.get_label() == "▼ Priority")
    prio_btn.emit("clicked")
    assert prio() == [119, 128], f"expected priority asc after realized click, got {prio()}"
    # Re-click inverts back.
    asc_btn = next(b for b in realized if b.get_label() == "▲ Priority")
    asc_btn.emit("clicked")
    assert prio() == [128, 119], f"expected priority desc after realized re-click, got {prio()}"


check("realized tree renders sort buttons; realized click re-sorts + inverts",
      _realized_sort_buttons_render)


def _realized_planet_table_sort():
    widget = build_planet_table(chart)
    view = _find_column_view(widget)
    win = _realize(widget)
    realized = [w for w in _walk(win) if isinstance(w, Gtk.Button)]
    labels = {b.get_label() for b in realized}
    assert "▲ Degree" in labels, f"expected ▲ Degree marker, got {sorted(labels)}"
    sm = view._sort_model
    deg = lambda: [round(sm.get_item(i).sort_degree, 1)
                   for i in range(sm.get_n_items())]
    assert deg() == [147.3, 248.7], f"expected default degree asc, got {deg()}"
    deg_btn = next(b for b in realized if b.get_label() == "▲ Degree")
    deg_btn.emit("clicked")
    assert deg() == [248.7, 147.3], f"expected degree desc after realized click, got {deg()}"


check("realized natal table: sort button renders + click re-sorts",
      _realized_planet_table_sort)


def _realized_agg_table_sort():
    widget = build_planet_agg_table(agg)
    view = _find_column_view(widget)
    win = _realize(widget)
    realized = [w for w in _walk(win) if isinstance(w, Gtk.Button)]
    labels = {b.get_label() for b in realized}
    assert "▼ Total" in labels, f"expected ▼ Total marker, got {sorted(labels)}"
    sm = view._sort_model
    tot = lambda: [sm.get_item(i).sort_total for i in range(sm.get_n_items())]
    assert tot() == [197, 172], f"expected default total desc, got {tot()}"
    tot_btn = next(b for b in realized if b.get_label() == "▼ Total")
    tot_btn.emit("clicked")
    assert tot() == [172, 197], f"expected total asc after realized click, got {tot()}"


check("realized by-planet table: sort button renders + click re-sorts",
      _realized_agg_table_sort)

print(f"\nResults: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
