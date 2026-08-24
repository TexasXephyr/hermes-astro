"""table_renderer.py — Sortable tabular views for the astrology GUI.

Builds Gtk.ColumnView tables (GTK4's modern sortable list) for:
  - Natal planet table: Body, Sign, Degree, House, Dignity, Speed, Retro
  - Transit grid: Body, Aspect, Natal, Orb, Days, Priority (sortable)
  - By-planet aggregation: Body, Total, Count, Top Aspect, vs Natal

All views are backed by Gtk.SortListModel so clicking a column header
sorts the data. The transit grid consumes the priority-scored output
from astro_analyze.scoring (via AstroClient.period_impact).
"""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject, Gio, Pango

from astro_text.symbols import symbol_for_body, symbol_for_aspect
from astro_text.format import format_longitude


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
    orb = GObject.Property(type=str, default="")
    days = GObject.Property(type=str, default="")
    priority = GObject.Property(type=str, default="")
    sort_orb = GObject.Property(type=float, default=0.0)
    sort_days = GObject.Property(type=int, default=0)
    sort_priority = GObject.Property(type=int, default=0)

    def __init__(self, body="", aspect="", natal="", orb="", days="",
                 priority="", sort_orb=0.0, sort_days=0, sort_priority=0, **kwargs):
        super().__init__(**kwargs)
        self.body = body
        self.aspect = aspect
        self.natal = natal
        self.orb = orb
        self.days = days
        self.priority = priority
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
        dignity = b.get("dignity", {}).get("label", "") if isinstance(b.get("dignity"), dict) else ""
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


def build_transit_grid(active_transits: list[dict]) -> Gtk.Widget:
    """Transit grid: Body, Aspect, Natal, Orb, Days, Priority (sortable).

    `active_transits` is the priority-scored list from
    astro_analyze.scoring.score_active_transits (already sorted desc by
    priority; the user can re-sort by clicking headers).
    """
    rows = []
    for t in active_transits:
        tb = t.get("transiting_body", "?")
        nb = t.get("natal_body", "?")
        aspect = t.get("aspect", "?")
        tb_sym = symbol_for_body(tb) or tb
        nb_sym = symbol_for_body(nb) or nb
        asp_sym = symbol_for_aspect(aspect) or aspect
        rows.append(TransitRow(
            body=f"{tb_sym} {tb}".strip(),
            aspect=f"{asp_sym} {aspect}".strip(),
            natal=f"{nb_sym} {nb}".strip(),
            orb=f"{t.get('orb', 0.0):.2f}°",
            days=str(t.get("days_to_exact", 0)),
            priority=str(t.get("priority", 0)),
            sort_orb=float(t.get("orb", 0.0)),
            sort_days=int(t.get("days_to_exact", 0)),
            sort_priority=int(t.get("priority", 0)),
        ))

    model = Gio.ListStore.new(TransitRow)
    for r in rows:
        model.append(r)

    sort_model = Gtk.SortListModel(model=model)
    selection = Gtk.SingleSelection(model=sort_model)
    view = Gtk.ColumnView(model=selection)
    view.append_column(_text_column("Body", "body", sortable=True, sorter=_string_sorter(TransitRow, "body")))
    view.append_column(_text_column("Aspect", "aspect", sortable=True, sorter=_string_sorter(TransitRow, "aspect")))
    view.append_column(_text_column("Natal", "natal", sortable=True, sorter=_string_sorter(TransitRow, "natal")))
    view.append_column(_text_column("Orb", "orb", sortable=True, sorter=_prop_sorter(TransitRow, "sort_orb")))
    view.append_column(_text_column("Days", "days", sortable=True, sorter=_prop_sorter(TransitRow, "sort_days")))
    view.append_column(_text_column("Priority", "priority", sortable=True, sorter=_prop_sorter(TransitRow, "sort_priority", descending=True)))

    # Default sort: priority descending
    sort_model.set_sorter(_prop_sorter(TransitRow, "sort_priority", descending=True))
    return view


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
