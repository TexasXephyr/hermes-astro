"""table_renderer.py — Sortable tabular views for the astrology GUI.

Builds Gtk.ColumnView tables (GTK4's modern sortable list) for:
  - Natal planet table: Body, Sign, Degree, House, Dignity, Speed, Retro
  - Transit grid: Body, Aspect, Natal, T Sign, N Sign, Orb, Days, Priority
    (sortable, with a filter row for point / aspect / sign)
  - By-planet aggregation: Body, Total, Count, Top Aspect, vs Natal

All views are backed by Gtk.SortListModel so clicking a column header
sorts the data; re-clicking the same header inverts the order (GTK's
built-in ColumnView header behavior). The transit grid consumes the
priority-scored output from astro_analyze.scoring (via
AstroClient.period_impact) and looks up transit/natal signs from the
body lists passed in by the caller.
"""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject, Gio, Pango

from astro_text.symbols import symbol_for_body, symbol_for_aspect, symbol_for_sign
from astro_text.format import format_longitude
from astro_text.dignity import get_dignity


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_days(days: int | float | None) -> str:
    """Smart 'Days' formatting for the transit grid.

    `days` is an integer; negative means the aspect is separating (the
    exact date is in the past). The absolute value is shown with the two
    largest relevant time units when under 2 days, e.g. '1d 3h', '6h 32m';
    otherwise the integer is shown with 'd', e.g. '3d'. Separating values
    are prefixed with 'sep ' (e.g. 'sep 1d 3h').
    """
    if days is None:
        return ""
    try:
        raw = float(days)
    except (TypeError, ValueError):
        return str(days)
    prefix = "sep " if raw < 0 else ""
    n = abs(raw)
    if n == 0:
        return f"{prefix}0h"
    if n < 2:
        if n < 1:
            hours = int(round(n * 24))
            if hours < 1:
                minutes = int(round(n * 24 * 60))
                return f"{prefix}{minutes}m"
            return f"{prefix}{hours}h"
        days_part = int(n)
        hours_part = int(round((n - days_part) * 24))
        if hours_part >= 24:
            days_part += 1
            hours_part = 0
        if hours_part:
            return f"{prefix}{days_part}d {hours_part}h"
        return f"{prefix}{days_part}d"
    return f"{prefix}{int(n)}d"


# ---------------------------------------------------------------------------
# Row models
# ---------------------------------------------------------------------------

class PlanetRow(GObject.Object):
    """One row in the natal planet table."""

    __gtype_name__ = "AstroPlanetRow"

    body = GObject.Property(type=str, default="")
    sign = GObject.Property(type=str, default="")
    degree = GObject.Property(type=str, default="")
    house = GObject.Property(type=str, default="")
    dignity = GObject.Property(type=str, default="")
    speed = GObject.Property(type=str, default="")
    retro = GObject.Property(type=str, default="")
    sort_degree = GObject.Property(type=float, default=0.0)
    sort_house = GObject.Property(type=int, default=0)

    def __init__(self, body="", sign="", degree="", house="", dignity="",
                 speed="", retro="", sort_degree=0.0, sort_house=0, **kwargs):
        super().__init__(**kwargs)
        self.body = body
        self.sign = sign
        self.degree = degree
        self.house = house
        self.dignity = dignity
        self.speed = speed
        self.retro = retro
        self.sort_degree = sort_degree
        self.sort_house = sort_house


class TransitRow(GObject.Object):
    """One row in the transit grid (priority-scored)."""

    __gtype_name__ = "AstroTransitRow"

    body = GObject.Property(type=str, default="")
    aspect = GObject.Property(type=str, default="")
    natal = GObject.Property(type=str, default="")
    t_sign = GObject.Property(type=str, default="")
    n_sign = GObject.Property(type=str, default="")
    orb = GObject.Property(type=str, default="")
    days = GObject.Property(type=str, default="")
    priority = GObject.Property(type=str, default="")
    # Raw names (no glyphs) used by the filter row
    body_name = GObject.Property(type=str, default="")
    natal_name = GObject.Property(type=str, default="")
    aspect_name = GObject.Property(type=str, default="")
    t_sign_name = GObject.Property(type=str, default="")
    n_sign_name = GObject.Property(type=str, default="")
    sort_orb = GObject.Property(type=float, default=0.0)
    sort_days = GObject.Property(type=int, default=0)
    sort_priority = GObject.Property(type=int, default=0)

    def __init__(self, body="", aspect="", natal="", t_sign="", n_sign="",
                 orb="", days="", priority="", body_name="", natal_name="",
                 aspect_name="", t_sign_name="", n_sign_name="",
                 sort_orb=0.0, sort_days=0, sort_priority=0, **kwargs):
        super().__init__(**kwargs)
        self.body = body
        self.aspect = aspect
        self.natal = natal
        self.t_sign = t_sign
        self.n_sign = n_sign
        self.orb = orb
        self.days = days
        self.priority = priority
        self.body_name = body_name
        self.natal_name = natal_name
        self.aspect_name = aspect_name
        self.t_sign_name = t_sign_name
        self.n_sign_name = n_sign_name
        self.sort_orb = sort_orb
        self.sort_days = sort_days
        self.sort_priority = sort_priority


class PlanetAggRow(GObject.Object):
    """One row in the by-planet aggregation table."""

    __gtype_name__ = "AstroPlanetAggRow"

    body = GObject.Property(type=str, default="")
    total = GObject.Property(type=str, default="")
    count = GObject.Property(type=str, default="")
    top_aspect = GObject.Property(type=str, default="")
    vs_natal = GObject.Property(type=str, default="")
    sort_total = GObject.Property(type=int, default=0)

    def __init__(self, body="", total="", count="", top_aspect="", vs_natal="",
                 sort_total=0, **kwargs):
        super().__init__(**kwargs)
        self.body = body
        self.total = total
        self.count = count
        self.top_aspect = top_aspect
        self.vs_natal = vs_natal
        self.sort_total = sort_total


# ---------------------------------------------------------------------------
# Column helpers
# ---------------------------------------------------------------------------

def _text_column(title: str, prop: str, sortable: bool = False,
                 sorter: Gtk.Sorter | None = None, xalign: float = 0.0,
                 monospace: bool = False) -> Gtk.ColumnViewColumn:
    """Build a text column bound to a GObject property."""
    factory = Gtk.SignalListItemFactory()
    factory.connect("setup", _setup_label_cell, monospace)
    factory.connect("bind", _bind_label_cell, prop)
    col = Gtk.ColumnViewColumn(title=title, factory=factory)
    if xalign:
        col.set_xalign(xalign)
    if sortable and sorter is not None:
        col.set_sorter(sorter)
    return col


def _setup_label_cell(factory, list_item, monospace: bool):
    label = Gtk.Label()
    label.set_xalign(0.0)
    label.set_ellipsize(Pango.EllipsizeMode.END)
    if monospace:
        label.set_markup('<span font_family="monospace"> </span>')
    list_item.set_child(label)


def _bind_label_cell(factory, list_item, prop: str):
    label = list_item.get_child()
    row = list_item.get_item()
    label.set_text(str(getattr(row, prop, "")))


def _prop_sorter(item_type, prop: str, descending: bool = False) -> Gtk.Sorter:
    """Numeric sorter over a GObject property (falls back to string)."""
    return Gtk.NumericSorter(
        expression=Gtk.PropertyExpression.new(
            item_type, None, prop
        ),
        sort_order=Gtk.SortType.DESCENDING if descending else Gtk.SortType.ASCENDING,
    )


def _string_sorter(item_type, prop: str) -> Gtk.Sorter:
    return Gtk.StringSorter(
        expression=Gtk.PropertyExpression.new(item_type, None, prop)
    )


# ---------------------------------------------------------------------------
# Table builders
# ---------------------------------------------------------------------------

def build_planet_table(chart: dict) -> Gtk.Widget:
    """Natal planet table: Body, Sign, Degree, House, Dignity, Speed, Retro."""
    rows = []
    for b in sorted(chart.get("bodies", []), key=lambda x: x.get("longitude", 0.0)):
        name = b.get("name", "?")
        glyph = symbol_for_body(name) or ""
        sign = b.get("sign_name", "?")
        deg = format_longitude(b.get("longitude", 0.0))
        house = str(b.get("house", "-"))
        dignity = ""
        try:
            dignity = get_dignity(
                name, sign, sign_degree=b.get("sign_degree", 0.0)
            )["label"]
        except Exception:
            dignity = ""
        speed = f"{b.get('speed', 0.0):.3f}"
        retro = "R" if b.get("retrograde") else ""
        rows.append(PlanetRow(
            body=f"{glyph} {name}".strip(),
            sign=sign,
            degree=deg,
            house=house,
            dignity=dignity,
            speed=speed,
            retro=retro,
            sort_degree=b.get("longitude", 0.0),
            sort_house=b.get("house", 0),
        ))

    model = Gio.ListStore.new(PlanetRow)
    for r in rows:
        model.append(r)

    sort_model = Gtk.SortListModel(model=model)
    selection = Gtk.SingleSelection(model=sort_model)
    view = Gtk.ColumnView(model=selection)
    view.append_column(_text_column("Body", "body", sortable=True, sorter=_string_sorter(PlanetRow, "body")))
    view.append_column(_text_column("Sign", "sign", sortable=True, sorter=_string_sorter(PlanetRow, "sign")))
    view.append_column(_text_column("Degree", "degree", sortable=True, sorter=_prop_sorter(PlanetRow, "sort_degree")))
    view.append_column(_text_column("House", "house", sortable=True, sorter=_prop_sorter(PlanetRow, "sort_house")))
    view.append_column(_text_column("Dignity", "dignity", sortable=True, sorter=_string_sorter(PlanetRow, "dignity")))
    view.append_column(_text_column("Speed", "speed", sortable=True, sorter=_string_sorter(PlanetRow, "speed")))
    view.append_column(_text_column("Retro", "retro", sortable=True, sorter=_string_sorter(PlanetRow, "retro")))

    # Default sort: by degree (longitude)
    sort_model.set_sorter(_prop_sorter(PlanetRow, "sort_degree"))
    return view


def _sign_glyph(name: str) -> str:
    """Glyph for a sign name, falling back to the plain name."""
    try:
        return symbol_for_sign(name)
    except Exception:
        return name


def _sign_label(name: str) -> str:
    """Sign cell text: glyph + name (e.g. '♌ Leo')."""
    if not name:
        return ""
    return f"{_sign_glyph(name)} {name}".strip()


class _TransitFilterState(GObject.Object):
    """Filter state for the transit grid (GObject props so notify fires)."""

    __gtype_name__ = "AstroTransitFilterState"

    point = GObject.Property(type=str, default="")
    point_side = GObject.Property(type=str, default="transit")
    aspect = GObject.Property(type=str, default="all")
    sign_side = GObject.Property(type=str, default="transit")
    sign = GObject.Property(type=str, default="any")


def _build_transit_filter_row(state) -> Gtk.Box:
    """Filter row above the transit grid: point, natal/transit, aspect, sign.

    `state` is a GObject with `point`, `point_side`, `aspect`, `sign_side`,
    `sign` string properties. The returned box exposes the widgets as
    attributes (`point_entry`, `point_side_dropdown`, `aspect_dropdown`,
    `sign_side_dropdown`, `sign_dropdown`) so tests can drive them.
    """
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    row.set_spacing(6)
    row.set_margin_top(6)
    row.set_margin_start(6)
    row.set_margin_end(6)

    row.append(Gtk.Label(label="Filter:"))

    row.point_entry = Gtk.Entry()
    row.point_entry.set_placeholder_text("Point (e.g. Mercury)")
    row.point_entry.set_max_width_chars(14)
    row.append(row.point_entry)

    row.point_side_dropdown = Gtk.DropDown.new_from_strings([
        "transit", "natal",
    ])
    row.point_side_dropdown.set_selected(0)
    row.append(row.point_side_dropdown)

    row.aspect_dropdown = Gtk.DropDown.new_from_strings([
        "all", "conjunction", "opposition", "trine", "square",
        "sextile", "quincunx",
    ])
    row.aspect_dropdown.set_selected(0)
    row.append(row.aspect_dropdown)

    row.sign_side_dropdown = Gtk.DropDown.new_from_strings([
        "transit", "natal",
    ])
    row.sign_side_dropdown.set_selected(0)
    row.append(row.sign_side_dropdown)

    row.sign_dropdown = Gtk.DropDown.new_from_strings([
        "any", "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    ])
    row.sign_dropdown.set_selected(0)
    row.append(row.sign_dropdown)

    def _apply(*_args):
        state.point = row.point_entry.get_text().strip()
        state.point_side = row.point_side_dropdown.get_selected_item().get_string()
        state.aspect = row.aspect_dropdown.get_selected_item().get_string()
        state.sign_side = row.sign_side_dropdown.get_selected_item().get_string()
        state.sign = row.sign_dropdown.get_selected_item().get_string()

    row.point_entry.connect("changed", _apply)
    row.point_side_dropdown.connect("notify::selected", _apply)
    row.aspect_dropdown.connect("notify::selected", _apply)
    row.sign_side_dropdown.connect("notify::selected", _apply)
    row.sign_dropdown.connect("notify::selected", _apply)
    _apply()
    return row


def build_transit_grid(active_transits: list[dict],
                       transit_bodies: list[dict] | None = None,
                       natal_bodies: list[dict] | None = None) -> Gtk.Widget:
    """Transit grid: Body, Aspect, Natal, T Sign, N Sign, Orb, Days, Priority.

    `active_transits` is the priority-scored list from
    astro_analyze.scoring.score_active_transits (already sorted desc by
    priority; the user can re-sort by clicking headers — re-clicking the
    same header inverts the order, GTK's built-in behavior).

    `transit_bodies` / `natal_bodies` are the body lists from the transit
    and natal charts; they provide the sign for each planet. When omitted,
    sign columns show '?' and the sign filter is a no-op.

    The returned widget is a vertical box: a filter row (point / aspect /
    sign) above the sortable ColumnView. The filter row is reachable as
    `widget.filter_row` for tests.
    """
    transit_signs = {b.get("name", ""): b.get("sign_name", "")
                     for b in (transit_bodies or [])}
    natal_signs = {b.get("name", ""): b.get("sign_name", "")
                   for b in (natal_bodies or [])}

    rows = []
    for t in active_transits:
        tb = t.get("transiting_body", "?")
        nb = t.get("natal_body", "?")
        aspect = t.get("aspect", "?")
        tb_sym = symbol_for_body(tb) or tb
        nb_sym = symbol_for_body(nb) or nb
        asp_sym = symbol_for_aspect(aspect) or aspect
        t_sign = transit_signs.get(tb, "")
        n_sign = natal_signs.get(nb, "")
        rows.append(TransitRow(
            body=f"{tb_sym} {tb}".strip(),
            aspect=f"{asp_sym} {aspect}".strip(),
            natal=f"{nb_sym} {nb}".strip(),
            t_sign=_sign_label(t_sign),
            n_sign=_sign_label(n_sign),
            orb=f"{t.get('orb', 0.0):.2f}°",
            days=format_days(t.get("days_to_exact", 0)),
            priority=str(t.get("priority", 0)),
            body_name=tb,
            natal_name=nb,
            aspect_name=aspect,
            t_sign_name=t_sign,
            n_sign_name=n_sign,
            sort_orb=float(t.get("orb", 0.0)),
            sort_days=int(t.get("days_to_exact", 0)),
            sort_priority=int(t.get("priority", 0)),
        ))

    model = Gio.ListStore.new(TransitRow)
    for r in rows:
        model.append(r)

    # Filter state + CustomFilter (re-evaluated on every filter change)
    state = _TransitFilterState()

    def _match(item):
        if state.point:
            if state.point_side == "transit":
                if item.body_name != state.point:
                    return False
            else:
                if item.natal_name != state.point:
                    return False
        if state.aspect != "all" and item.aspect_name != state.aspect:
            return False
        if state.sign != "any":
            if state.sign_side == "transit":
                if item.t_sign_name != state.sign:
                    return False
            else:
                if item.n_sign_name != state.sign:
                    return False
        return True

    filt = Gtk.CustomFilter.new(_match)
    filter_model = Gtk.FilterListModel(model=model, filter=filt)

    sort_model = Gtk.SortListModel(model=filter_model)
    selection = Gtk.SingleSelection(model=sort_model)
    view = Gtk.ColumnView(model=selection)
    view.append_column(_text_column("Body", "body", sortable=True, sorter=_string_sorter(TransitRow, "body")))
    view.append_column(_text_column("Aspect", "aspect", sortable=True, sorter=_string_sorter(TransitRow, "aspect")))
    view.append_column(_text_column("Natal", "natal", sortable=True, sorter=_string_sorter(TransitRow, "natal")))
    view.append_column(_text_column("T Sign", "t_sign", sortable=True, sorter=_string_sorter(TransitRow, "t_sign")))
    view.append_column(_text_column("N Sign", "n_sign", sortable=True, sorter=_string_sorter(TransitRow, "n_sign")))
    view.append_column(_text_column("Orb", "orb", sortable=True, sorter=_prop_sorter(TransitRow, "sort_orb")))
    view.append_column(_text_column("Days", "days", sortable=True, sorter=_prop_sorter(TransitRow, "sort_days")))
    view.append_column(_text_column("Priority", "priority", sortable=True, sorter=_prop_sorter(TransitRow, "sort_priority", descending=True)))

    # Default sort: priority descending
    sort_model.set_sorter(_prop_sorter(TransitRow, "sort_priority", descending=True))

    def _on_filter_changed(*_args):
        filt.changed(Gtk.FilterChange.DIFFERENT)

    state.connect("notify::point", _on_filter_changed)
    state.connect("notify::point_side", _on_filter_changed)
    state.connect("notify::aspect", _on_filter_changed)
    state.connect("notify::sign_side", _on_filter_changed)
    state.connect("notify::sign", _on_filter_changed)

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.filter_row = _build_transit_filter_row(state)
    box.append(box.filter_row)
    box.append(view)
    view.set_vexpand(True)
    return box


def build_planet_agg_table(rows: list[dict]) -> Gtk.Widget:
    """By-planet aggregation: Body, Total, Count, Top Aspect, vs Natal."""
    agg_rows = []
    for r in rows:
        agg_rows.append(PlanetAggRow(
            body=r.get("body", "?"),
            total=str(r.get("total_priority", 0)),
            count=str(r.get("transit_count", 0)),
            top_aspect=r.get("top_aspect", ""),
            vs_natal=r.get("top_natal_body", ""),
            sort_total=int(r.get("total_priority", 0)),
        ))

    model = Gio.ListStore.new(PlanetAggRow)
    for r in agg_rows:
        model.append(r)

    sort_model = Gtk.SortListModel(model=model)
    selection = Gtk.SingleSelection(model=sort_model)
    view = Gtk.ColumnView(model=selection)
    view.append_column(_text_column("Body", "body", sortable=True, sorter=_string_sorter(PlanetAggRow, "body")))
    view.append_column(_text_column("Total", "total", sortable=True, sorter=_prop_sorter(PlanetAggRow, "sort_total", descending=True)))
    view.append_column(_text_column("Count", "count", sortable=True, sorter=_prop_sorter(PlanetAggRow, "sort_total")))
    view.append_column(_text_column("Top Aspect", "top_aspect", sortable=True, sorter=_string_sorter(PlanetAggRow, "top_aspect")))
    view.append_column(_text_column("vs Natal", "vs_natal", sortable=True, sorter=_string_sorter(PlanetAggRow, "vs_natal")))

    sort_model.set_sorter(_prop_sorter(PlanetAggRow, "sort_total", descending=True))
    return view
