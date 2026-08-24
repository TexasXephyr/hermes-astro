"""table_renderer.py — Sortable tabular views for the astrology GUI.

Builds Gtk.ColumnView tables (GTK4's modern sortable list) for:
  - Natal planet table: Body, Sign, Degree, House, Dignity, Speed, Retro
  - Transit grid: T Body, T Sign, T House, Aspect, N Body, N Sign, N House,
    Orb, Days, Priority (sortable, with a filter row for point / aspect /
    sign / house)
  - By-planet aggregation: Body, Total, Count, Top Aspect, vs Natal

All views are backed by a Gtk.SortListModel. Sort controls are a row of
explicit Gtk.Buttons rendered ABOVE the view (one per column title):
clicking a button sorts the model, re-clicking inverts the direction,
and the active button's label shows the direction with a ▲/▼ prefix.
GTK's built-in ColumnView header sorting is NOT used — on GTK 4.22 the
header row cannot host custom widgets (a header factory's setup/bind
callbacks fire but the native GtkColumnViewTitle widgets still render,
so custom buttons never appear) and Gtk.ColumnView exposes no sort
signal to hook. The transit grid consumes the
priority-scored output from astro_analyze.scoring (via
AstroClient.period_impact) and looks up transit/natal signs from the
body lists passed in by the caller.
"""
from __future__ import annotations

import math
import re

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject, Gio, Pango
import cairo

from astro_text.symbols import symbol_for_body, symbol_for_aspect
from astro_text.format import format_longitude
from astro_text.dignity import get_dignity
from astro_text.houses import find_house
from astro_display.glyph_data import ALL as GLYPHS


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
    t_house = GObject.Property(type=str, default="")
    n_house = GObject.Property(type=str, default="")
    orb = GObject.Property(type=str, default="")
    days = GObject.Property(type=str, default="")
    priority = GObject.Property(type=str, default="")
    # Raw names (no glyphs) used by the filter row
    body_name = GObject.Property(type=str, default="")
    natal_name = GObject.Property(type=str, default="")
    aspect_name = GObject.Property(type=str, default="")
    t_sign_name = GObject.Property(type=str, default="")
    n_sign_name = GObject.Property(type=str, default="")
    t_house_num = GObject.Property(type=int, default=0)
    n_house_num = GObject.Property(type=int, default=0)
    sort_orb = GObject.Property(type=float, default=0.0)
    sort_days = GObject.Property(type=int, default=0)
    sort_priority = GObject.Property(type=int, default=0)

    def __init__(self, body="", aspect="", natal="", t_sign="", n_sign="",
                 t_house="", n_house="", orb="", days="", priority="",
                 body_name="", natal_name="", aspect_name="", t_sign_name="",
                 n_sign_name="", t_house_num=0, n_house_num=0,
                 sort_orb=0.0, sort_days=0, sort_priority=0, **kwargs):
        super().__init__(**kwargs)
        self.body = body
        self.aspect = aspect
        self.natal = natal
        self.t_sign = t_sign
        self.n_sign = n_sign
        self.t_house = t_house
        self.n_house = n_house
        self.orb = orb
        self.days = days
        self.priority = priority
        self.body_name = body_name
        self.natal_name = natal_name
        self.aspect_name = aspect_name
        self.t_sign_name = t_sign_name
        self.n_sign_name = n_sign_name
        self.t_house_num = t_house_num
        self.n_house_num = n_house_num
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
    sort_count = GObject.Property(type=int, default=0)

    def __init__(self, body="", total="", count="", top_aspect="", vs_natal="",
                 sort_total=0, sort_count=0, **kwargs):
        super().__init__(**kwargs)
        self.body = body
        self.total = total
        self.count = count
        self.top_aspect = top_aspect
        self.vs_natal = vs_natal
        self.sort_total = sort_total
        self.sort_count = sort_count


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


def _make_sorter(item_type, prop: str,
                 descending: bool = False) -> Gtk.Sorter:
    """Return a sorter over a property, in the given direction.

    Numeric properties (int/float) get a Gtk.NumericSorter (which can be
    flipped in place with set_sort_order). String properties get a
    Gtk.CustomSorter because Gtk.StringSorter has no direction setter
    on this GTK version — the comparator reads the property directly so
    the same sorter object can serve both directions.
    """
    prop_pspec = None
    try:
        for ps in item_type.list_properties():
            if ps.name == prop or ps.name == prop.replace("_", "-"):
                prop_pspec = ps
                break
    except Exception:
        prop_pspec = None
    if prop_pspec is None:
        # Unknown property: fall back to a plain string sorter.
        return Gtk.StringSorter(
            expression=Gtk.PropertyExpression.new(item_type, None, prop)
        )
    if prop_pspec.value_type in (GObject.TYPE_INT, GObject.TYPE_INT64,
                                 GObject.TYPE_UINT, GObject.TYPE_UINT64,
                                 GObject.TYPE_LONG, GObject.TYPE_ULONG,
                                 GObject.TYPE_FLOAT, GObject.TYPE_DOUBLE):
        return Gtk.NumericSorter(
            expression=Gtk.PropertyExpression.new(item_type, None, prop),
            sort_order=Gtk.SortType.DESCENDING if descending else Gtk.SortType.ASCENDING,
        )

    state = {"desc": descending}

    def _cmp(a, b, _user=None):
        av = getattr(a, prop, "")
        bv = getattr(b, prop, "")
        if av == bv:
            return 0
        r = -1 if av < bv else 1
        return -r if state["desc"] else r

    sorter = Gtk.CustomSorter.new(_cmp)
    sorter._direction = state
    return sorter


def _set_sorter_direction(sorter: Gtk.Sorter, descending: bool):
    """Flip a sorter to ascending/descending (numeric or custom)."""
    if isinstance(sorter, Gtk.NumericSorter):
        sorter.set_sort_order(
            Gtk.SortType.DESCENDING if descending else Gtk.SortType.ASCENDING
        )
        return
    state = getattr(sorter, "_direction", None)
    if state is not None:
        state["desc"] = descending


def _header_button(label: str) -> Gtk.Button:
    """A sort button; its label shows the sort direction when active."""
    btn = Gtk.Button()
    btn.set_label(label)
    btn.set_focusable(False)
    return btn


def _mark_active(buttons: dict, title: str | None, descending: bool):
    """Update the sort button labels to show the active sort direction."""
    for t, btn in buttons.items():
        base = t
        if getattr(btn, "_base_title", None):
            base = btn._base_title
        if t == title:
            btn.set_label(("▼ " if descending else "▲ ") + base)
        else:
            btn.set_label(base)


def _sorter_desc(sorter: Gtk.Sorter) -> bool:
    """Is this sorter currently sorting descending?"""
    if isinstance(sorter, Gtk.NumericSorter):
        return sorter.get_sort_order() == Gtk.SortType.DESCENDING
    state = getattr(sorter, "_direction", None)
    return bool(state and state["desc"])


def _install_sort_buttons(view: Gtk.ColumnView,
                          sort_model: Gtk.SortListModel,
                          buttons: dict,
                          sorter_specs: dict,
                          default_title: str | None = None) -> Gtk.Widget:
    """Build a visible row of sort buttons above the view.

    GTK 4.22's ColumnView header row cannot host custom widgets on this
    build (a header factory's setup/bind callbacks fire but the native
    GtkColumnViewTitle widgets still render — the custom buttons never
    appear), and Gtk.ColumnView exposes no sort signal to hook. So the
    sort controls live in a plain FlowBox row rendered *above* the view,
    one small button per column title, wired directly to the
    SortListModel.

    ``buttons`` maps column title -> Gtk.Button (built by the caller with
    `_header_button`). ``sorter_specs`` maps column title -> sorter object
    with the column's preferred direction baked in.

    Clicking a sort button:
    - first click on a column activates it with its sorter's baked-in
      direction (ascending for text, descending for numeric/priority);
    - re-click on the active column inverts the direction;
    - the active button's label gets a '▲ '/'▼ ' prefix; the sort model
      is re-sorted through ``sort_model.set_sorter`` so the visible row
      order changes immediately.

    The default sort is applied by the caller (default_title + active
    direction), so the initial button shows the marker for it. The
    returned row is a Gtk.FlowBox (wraps when the window is narrow) and
    is exposed as ``view._sort_row`` for tests.
    """
    active = {"title": default_title, "desc": False}
    if default_title is not None:
        active["desc"] = _sorter_desc(sorter_specs[default_title])
        _mark_active(buttons, default_title, active["desc"])

    def _on_clicked(_btn, title, *args):
        sorter = sorter_specs[title]
        if active["title"] == title:
            # Re-click inverts.
            descending = not _sorter_desc(sorter)
        else:
            # New column: keep the sorter's baked-in default direction.
            descending = _sorter_desc(sorter)
        _set_sorter_direction(sorter, descending)
        sort_model.set_sorter(sorter)
        # Custom (string) sorters hold direction in mutable state and need
        # an explicit change notification; NumericSorter also re-sorts on
        # set_sort_order but the notification is harmless and keeps both
        # paths uniform.
        sorter.changed(Gtk.SorterChange.DIFFERENT)
        active["title"] = title
        active["desc"] = descending
        _mark_active(buttons, title, descending)

    for title, btn in buttons.items():
        btn._base_title = title
        if title in sorter_specs:
            btn.connect("clicked", _on_clicked, title)

    row = Gtk.FlowBox()
    row.set_selection_mode(Gtk.SelectionMode.NONE)
    row.set_column_spacing(4)
    row.set_row_spacing(2)
    row.set_margin_top(4)
    row.set_margin_start(6)
    row.set_margin_end(6)
    for title in sorter_specs:
        row.append(buttons[title])
    view._sort_row = row
    return row


# ---------------------------------------------------------------------------
# Table builders
# ---------------------------------------------------------------------------

def build_planet_table(chart: dict) -> Gtk.Widget:
    """Natal planet table: Body, Sign, Degree, House, Dignity, Speed, Retro.

    Returns a vertical Box: a row of sort buttons above the ColumnView.
    Clicking a sort button sorts, re-clicking inverts, and the active
    button's label carries a '▲ '/'▼ ' prefix (default sort: degree
    ascending). The sort buttons live in a visible row above the view
    because GTK 4.22's ColumnView header row cannot host custom widgets
    on this build (see `_install_sort_buttons`).
    """
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

    sorter_specs = {
        "Body": _make_sorter(PlanetRow, "body"),
        "Sign": _make_sorter(PlanetRow, "sign"),
        "Degree": _make_sorter(PlanetRow, "sort_degree"),
        "House": _make_sorter(PlanetRow, "sort_house"),
        "Dignity": _make_sorter(PlanetRow, "dignity"),
        "Speed": _make_sorter(PlanetRow, "speed"),
        "Retro": _make_sorter(PlanetRow, "retro"),
    }
    view.append_column(_text_column("Body", "body", sortable=True, sorter=sorter_specs["Body"]))
    view.append_column(_text_column("Sign", "sign", sortable=True, sorter=sorter_specs["Sign"]))
    view.append_column(_text_column("Degree", "degree", sortable=True, sorter=sorter_specs["Degree"]))
    view.append_column(_text_column("House", "house", sortable=True, sorter=sorter_specs["House"]))
    view.append_column(_text_column("Dignity", "dignity", sortable=True, sorter=sorter_specs["Dignity"]))
    view.append_column(_text_column("Speed", "speed", sortable=True, sorter=sorter_specs["Speed"]))
    view.append_column(_text_column("Retro", "retro", sortable=True, sorter=sorter_specs["Retro"]))

    # Default sort: by degree (longitude)
    sort_model.set_sorter(sorter_specs["Degree"])

    # Visible sort buttons (GTK 4.22's header row cannot host custom
    # widgets — see module docstring / _install_sort_buttons).
    buttons = {title: _header_button(title) for title in sorter_specs}
    sort_row = _install_sort_buttons(view, sort_model, buttons, sorter_specs,
                                     default_title="Degree")
    view._sort_model = sort_model
    view._sort_buttons = buttons

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.append(sort_row)
    box.append(view)
    view.set_vexpand(True)
    return box


# ---------------------------------------------------------------------------
# Path-glyph rendering (LiberZodiac outlines via cairo)
# ---------------------------------------------------------------------------

_PATH_TOKEN_RE = re.compile(r"[MLHVQCZmlhvqcz]|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
_COMMAND_RE = re.compile(r"[MLHVQCZmlhvqcz]")


def _parse_path(d: str):
    """Tokenize an SVG path into command + parameter tuples.

    The glyph outlines in ``astro_display.glyph_data`` only use the
    commands M/L/H/V/C/Q/Z (uppercase and lowercase). Repeated
    coordinate pairs after a command are split out like the SVG spec.
    """
    tokens = _PATH_TOKEN_RE.findall(d)
    cmds = []
    i = 0
    cur = None
    while i < len(tokens):
        tok = tokens[i]
        if _COMMAND_RE.fullmatch(tok):
            cur = tok
            i += 1
        # else: implicit repeat of the previous command — i already points
        # at the first coordinate, so just fall through and consume params.
        if cur is None:
            raise ValueError(f"path data starts with coordinate: {d!r}")
        # Number of parameters depends on the command letter.
        if cur in ("M", "m", "L", "l", "T", "t"):
            n = 2
        elif cur in ("H", "h", "V", "v"):
            n = 1
        elif cur in ("C", "c"):
            n = 6
        elif cur in ("S", "s", "Q", "q"):
            n = 4
        elif cur in ("Z", "z"):
            n = 0
        else:
            raise ValueError(f"unsupported path command {cur!r}")
        params = []
        for _ in range(n):
            if i >= len(tokens):
                raise ValueError(f"path {cur!r} missing parameters: {d!r}")
            params.append(float(tokens[i]))
            i += 1
        cmds.append((cur, params))
    return cmds


def _apply_glyph_path(cr, name: str, cx: float, cy: float, size: float) -> bool:
    """Stroke/fill a named glyph path on a cairo context.

    Centers the glyph at (cx, cy) scaled to ``size`` area-equivalent units
    (mirrors the SVG wheel renderer's _path_element math). Returns False
    when the name has no path outline in glyph_data.
    """
    entry = GLYPHS.get(name)
    if entry is None:
        return False
    s = size / math.sqrt(entry["w"] * entry["h"])
    dx = cx - entry["cx"] * s
    dy = cy + entry["cy"] * s  # y-flip: font units are y-up

    cr.save()
    cr.translate(dx, dy)
    cr.scale(s, -s)
    cr.new_path()
    pen = (0.0, 0.0)  # overwritten by the leading M before any relative cmd
    for cmd, params in _parse_path(entry["path"]):
        if cmd == "M":
            pen = (params[0], params[1])
            cr.move_to(*pen)
        elif cmd == "m":
            pen = (pen[0] + params[0], pen[1] + params[1])
            cr.move_to(*pen)
        elif cmd == "L":
            pen = (params[0], params[1])
            cr.line_to(*pen)
        elif cmd == "l":
            pen = (pen[0] + params[0], pen[1] + params[1])
            cr.line_to(*pen)
        elif cmd == "H":
            pen = (params[0], pen[1])
            cr.line_to(*pen)
        elif cmd == "h":
            pen = (pen[0] + params[0], pen[1])
            cr.line_to(*pen)
        elif cmd == "V":
            pen = (pen[0], params[0])
            cr.line_to(*pen)
        elif cmd == "v":
            pen = (pen[0], pen[1] + params[0])
            cr.line_to(*pen)
        elif cmd == "C":
            c1 = (params[0], params[1])
            c2 = (params[2], params[3])
            pen = (params[4], params[5])
            cr.curve_to(c1[0], c1[1], c2[0], c2[1], pen[0], pen[1])
        elif cmd == "c":
            c1 = (pen[0] + params[0], pen[1] + params[1])
            c2 = (pen[0] + params[2], pen[1] + params[3])
            pen = (pen[0] + params[4], pen[1] + params[5])
            cr.curve_to(c1[0], c1[1], c2[0], c2[1], pen[0], pen[1])
        elif cmd == "Q":
            q = (params[0], params[1])
            end = (params[2], params[3])
            # Exact quadratic->cubic conversion (cairo's quadratic_to is
            # not exposed by the gi bindings on this system).
            c1 = (pen[0] + 2.0 / 3.0 * (q[0] - pen[0]),
                  pen[1] + 2.0 / 3.0 * (q[1] - pen[1]))
            c2 = (end[0] + 2.0 / 3.0 * (q[0] - end[0]),
                  end[1] + 2.0 / 3.0 * (q[1] - end[1]))
            cr.curve_to(c1[0], c1[1], c2[0], c2[1], end[0], end[1])
            pen = end
        elif cmd == "q":
            end = (pen[0] + params[2], pen[1] + params[3])
            q = (pen[0] + params[0], pen[1] + params[1])
            c1 = (pen[0] + 2.0 / 3.0 * (q[0] - pen[0]),
                  pen[1] + 2.0 / 3.0 * (q[1] - pen[1]))
            c2 = (end[0] + 2.0 / 3.0 * (q[0] - end[0]),
                  end[1] + 2.0 / 3.0 * (q[1] - end[1]))
            cr.curve_to(c1[0], c1[1], c2[0], c2[1], end[0], end[1])
            pen = end
        elif cmd == "Z":
            cr.close_path()
    cr.restore()
    return True


class _GlyphLabel(Gtk.DrawingArea):
    """A small DrawingArea that paints a path glyph next to a text label.

    Renders the named glyph (body or sign) with cairo from the
    LiberZodiac outlines in ``astro_display.glyph_data`` — no emoji
    fallback — followed by the plain-text name.
    """

    __gtype_name__ = "AstroGlyphLabel"

    def __init__(self, name: str = "", glyph_size: float = 18.0,
                 glyph_color: str = "#ffffff", **kwargs):
        super().__init__(**kwargs)
        self._name = name
        self._glyph_size = glyph_size
        self._glyph_color = glyph_color
        self.set_draw_func(self._on_draw)

    def set_name(self, name: str):
        self._name = name
        self.queue_draw()

    def _on_draw(self, area, cr, width, height):
        # Clear (transparent) and draw the glyph path, then the label.
        cr.set_source_rgba(0, 0, 0, 0)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        x = 4.0
        if self._name:
            try:
                _apply_glyph_path(cr, self._name, x + self._glyph_size / 2.0,
                                  height / 2.0, self._glyph_size)
                cr.set_source_rgb(1, 1, 1)
                cr.fill()
            except Exception:
                pass
            x += self._glyph_size + 8.0
        # Fallback text (used only when no outline exists).
        cr.select_font_face("Liberation Sans",
                            cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(13)
        cr.set_source_rgb(0.86, 0.86, 0.86)
        cr.move_to(x, height / 2.0 + 4.5)
        cr.show_text(self._name)


def _setup_glyph_cell(factory, list_item, _unused=None):
    cell = _GlyphLabel()
    list_item.set_child(cell)


def _bind_glyph_cell(factory, list_item, prop: str):
    cell = list_item.get_child()
    row = list_item.get_item()
    cell.set_name(str(getattr(row, prop, "")))


def _glyph_column(title: str, prop: str, sortable: bool = False,
                  sorter: Gtk.Sorter | None = None,
                  glyph_size: float = 18.0, glyph_color: str = "#ffffff") -> Gtk.ColumnViewColumn:
    """A column rendered as path glyph + text (LiberZodiac outlines)."""
    factory = Gtk.SignalListItemFactory()
    factory.connect("setup", _setup_glyph_cell, glyph_size)
    factory.connect("bind", _bind_glyph_cell, prop)
    col = Gtk.ColumnViewColumn(title=title, factory=factory)
    if sortable and sorter is not None:
        col.set_sorter(sorter)
    return col


class _TransitFilterState(GObject.Object):
    """Filter state for the transit grid (GObject props so notify fires)."""

    __gtype_name__ = "AstroTransitFilterState"

    point = GObject.Property(type=str, default="")
    point_side = GObject.Property(type=str, default="transit")
    aspect = GObject.Property(type=str, default="all")
    sign_side = GObject.Property(type=str, default="transit")
    sign = GObject.Property(type=str, default="any")
    house_side = GObject.Property(type=str, default="transit")
    house = GObject.Property(type=int, default=0)


def _build_transit_filter_row(state, active_points: list[str]) -> Gtk.Box:
    """Filter row above the transit grid: point, aspect, sign, house.

    `state` is a GObject with `point`, `point_side`, `aspect`, `sign_side`,
    `sign`, `house_side`, `house` properties. The returned box exposes the
    widgets as attributes (`point_dropdown`, `point_side_dropdown`,
    `aspect_dropdown`, `sign_side_dropdown`, `sign_dropdown`,
    `house_side_dropdown`, `house_dropdown`) so tests can drive them.

    `active_points` is the ordered list of point labels present in the
    grid ('T: Mercury', 'N: Moon', ...), built by build_transit_grid.
    """
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    row.set_spacing(6)
    row.set_margin_top(6)
    row.set_margin_start(6)
    row.set_margin_end(6)

    row.append(Gtk.Label(label="Filter:"))

    point_items = ["All"] + list(active_points)
    row.point_dropdown = Gtk.DropDown.new_from_strings(point_items)
    row.point_dropdown.set_selected(0)
    row.point_dropdown.set_tooltip_text("Filter rows where the point is involved")
    row.append(row.point_dropdown)

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

    row.house_side_dropdown = Gtk.DropDown.new_from_strings([
        "transit", "natal",
    ])
    row.house_side_dropdown.set_selected(0)
    row.append(row.house_side_dropdown)

    row.house_dropdown = Gtk.DropDown.new_from_strings([
        "any", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12",
    ])
    row.house_dropdown.set_selected(0)
    row.append(row.house_dropdown)

    def _selected_string(dropdown) -> str:
        item = dropdown.get_selected_item()
        if item is None:
            return ""
        return item.get_string()

    def _point_name(label: str) -> str:
        """Map a dropdown label ('T: Mercury', 'N: Moon') to the bare name."""
        if not label or label == "All":
            return ""
        return label.split(": ", 1)[1] if ": " in label else label

    def _apply(*_args):
        state.point = _point_name(_selected_string(row.point_dropdown))
        state.point_side = _selected_string(row.point_side_dropdown)
        state.aspect = _selected_string(row.aspect_dropdown)
        state.sign_side = _selected_string(row.sign_side_dropdown)
        state.sign = _selected_string(row.sign_dropdown)
        state.house_side = _selected_string(row.house_side_dropdown)
        house = _selected_string(row.house_dropdown)
        state.house = int(house) if house not in ("", "any") else 0

    row.point_dropdown.connect("notify::selected", _apply)
    row.point_side_dropdown.connect("notify::selected", _apply)
    row.aspect_dropdown.connect("notify::selected", _apply)
    row.sign_side_dropdown.connect("notify::selected", _apply)
    row.sign_dropdown.connect("notify::selected", _apply)
    row.house_side_dropdown.connect("notify::selected", _apply)
    row.house_dropdown.connect("notify::selected", _apply)
    _apply()
    return row


def build_transit_grid(active_transits: list[dict],
                       transit_bodies: list[dict] | None = None,
                       natal_bodies: list[dict] | None = None,
                       natal_houses: list[dict] | None = None) -> Gtk.Widget:
    """Transit grid: T Body | T Sign | T House | Aspect | N Body | N Sign | N House | Orb | Days | Priority.

    `active_transits` is the priority-scored list from
    astro_analyze.scoring.score_active_transits (already sorted desc by
    priority). A row of sort buttons sits above the ColumnView — clicking
    a sort button sorts, re-clicking inverts, and the active button's
    label carries a '▲ '/'▼ ' prefix (default sort: priority descending).
    The sort buttons live in a visible row above the view because GTK
    4.22's ColumnView header row cannot host custom widgets on this build
    (see `_install_sort_buttons`).

    `transit_bodies` / `natal_bodies` are the body lists from the transit
    and natal charts; they provide the sign (and longitude / natal house)
    for each planet. When omitted, sign columns show '' and the sign
    filter is a no-op.

    `natal_houses` is the natal chart's house-cusp list; the TRANSIT
    body's natal house is computed with astro_text.houses.find_house
    (the house the transiting body is crossing). When omitted, house
    columns show ''.

    Body and sign cells are rendered with LiberZodiac path glyphs
    (cairo-drawn from astro_display.glyph_data) — no emoji fallback.
    The returned widget is a vertical box: a filter row (point dropdown /
    aspect / sign / house) above the sortable ColumnView. The filter row
    is reachable as `widget.filter_row` for tests.
    """
    transit_by_name = {b.get("name", ""): b for b in (transit_bodies or [])}
    natal_by_name = {b.get("name", ""): b for b in (natal_bodies or [])}

    rows = []
    active_points: list[str] = []
    seen_points = set()
    for t in active_transits:
        tb = t.get("transiting_body", "?")
        nb = t.get("natal_body", "?")
        aspect = t.get("aspect", "?")
        tb_body = transit_by_name.get(tb)
        nb_body = natal_by_name.get(nb)
        t_sign = (tb_body or {}).get("sign_name", "")
        n_sign = (nb_body or {}).get("sign_name", "")
        # Transit body's natal house = the house it is currently crossing.
        t_house = ""
        t_house_num = 0
        if tb_body is not None and natal_houses:
            try:
                t_house_num = find_house(float(tb_body.get("longitude", 0.0)),
                                         natal_houses)
                t_house = str(t_house_num)
            except Exception:
                t_house = ""
        # Natal body's own house from the natal chart.
        n_house = ""
        n_house_num = 0
        if nb_body is not None:
            try:
                n_house_num = int(nb_body.get("house", 0))
                n_house = str(n_house_num) if n_house_num else ""
            except (TypeError, ValueError):
                n_house = ""
        for label, name in ((f"T: {tb}", tb), (f"N: {nb}", nb)):
            if name not in seen_points:
                seen_points.add(name)
                active_points.append(label)
        rows.append(TransitRow(
            body=tb,
            aspect=aspect,
            natal=nb,
            t_sign=t_sign,
            n_sign=n_sign,
            t_house=t_house,
            n_house=n_house,
            orb=f"{t.get('orb', 0.0):.2f}°",
            days=format_days(t.get("days_to_exact", 0)),
            priority=str(t.get("priority", 0)),
            body_name=tb,
            natal_name=nb,
            aspect_name=aspect,
            t_sign_name=t_sign,
            n_sign_name=n_sign,
            t_house_num=t_house_num,
            n_house_num=n_house_num,
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
        if state.house:
            if state.house_side == "transit":
                if item.t_house_num != state.house:
                    return False
            else:
                if item.n_house_num != state.house:
                    return False
        return True

    filt = Gtk.CustomFilter.new(_match)
    filter_model = Gtk.FilterListModel(model=model, filter=filt)

    sort_model = Gtk.SortListModel(model=filter_model)
    selection = Gtk.SingleSelection(model=sort_model)
    view = Gtk.ColumnView(model=selection)

    sorter_specs = {
        "T Body": _make_sorter(TransitRow, "body"),
        "T Sign": _make_sorter(TransitRow, "t_sign"),
        "T House": _make_sorter(TransitRow, "t_house_num"),
        "Aspect": _make_sorter(TransitRow, "aspect"),
        "N Body": _make_sorter(TransitRow, "natal"),
        "N Sign": _make_sorter(TransitRow, "n_sign"),
        "N House": _make_sorter(TransitRow, "n_house_num"),
        "Orb": _make_sorter(TransitRow, "sort_orb"),
        "Days": _make_sorter(TransitRow, "sort_days"),
        "Priority": _make_sorter(TransitRow, "sort_priority", descending=True),
    }
    view.append_column(_glyph_column("T Body", "body", sortable=True, sorter=sorter_specs["T Body"]))
    view.append_column(_glyph_column("T Sign", "t_sign", sortable=True, sorter=sorter_specs["T Sign"], glyph_size=16, glyph_color="#aaaaaa"))
    view.append_column(_text_column("T House", "t_house", sortable=True, sorter=sorter_specs["T House"]))
    view.append_column(_text_column("Aspect", "aspect", sortable=True, sorter=sorter_specs["Aspect"]))
    view.append_column(_glyph_column("N Body", "natal", sortable=True, sorter=sorter_specs["N Body"]))
    view.append_column(_glyph_column("N Sign", "n_sign", sortable=True, sorter=sorter_specs["N Sign"], glyph_size=16, glyph_color="#aaaaaa"))
    view.append_column(_text_column("N House", "n_house", sortable=True, sorter=sorter_specs["N House"]))
    view.append_column(_text_column("Orb", "orb", sortable=True, sorter=sorter_specs["Orb"]))
    view.append_column(_text_column("Days", "days", sortable=True, sorter=sorter_specs["Days"]))
    view.append_column(_text_column("Priority", "priority", sortable=True, sorter=sorter_specs["Priority"]))

    # Default sort: priority descending
    sort_model.set_sorter(sorter_specs["Priority"])

    # Visible sort buttons (GTK 4.22's header row cannot host custom
    # widgets — see module docstring / _install_sort_buttons).
    buttons = {title: _header_button(title) for title in sorter_specs}
    sort_row = _install_sort_buttons(view, sort_model, buttons, sorter_specs,
                                     default_title="Priority")
    view._sort_model = sort_model
    view._sort_buttons = buttons

    def _on_filter_changed(*_args):
        filt.changed(Gtk.FilterChange.DIFFERENT)

    state.connect("notify::point", _on_filter_changed)
    state.connect("notify::point_side", _on_filter_changed)
    state.connect("notify::aspect", _on_filter_changed)
    state.connect("notify::sign_side", _on_filter_changed)
    state.connect("notify::sign", _on_filter_changed)
    state.connect("notify::house_side", _on_filter_changed)
    state.connect("notify::house", _on_filter_changed)

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.filter_row = _build_transit_filter_row(state, active_points)
    box.append(box.filter_row)
    box.append(sort_row)
    box.append(view)
    view.set_vexpand(True)
    return box


def build_planet_agg_table(rows: list[dict]) -> Gtk.Widget:
    """By-planet aggregation: Body, Total, Count, Top Aspect, vs Natal.

    Returns a vertical Box: a row of sort buttons above the ColumnView.
    Clicking a sort button sorts, re-clicking inverts, and the active
    button's label carries a '▲ '/'▼ ' prefix (default sort: total
    descending). The sort buttons live in a visible row above the view
    because GTK 4.22's ColumnView header row cannot host custom widgets
    on this build (see `_install_sort_buttons`).
    """
    agg_rows = []
    for r in rows:
        agg_rows.append(PlanetAggRow(
            body=r.get("body", "?"),
            total=str(r.get("total_priority", 0)),
            count=str(r.get("transit_count", 0)),
            top_aspect=r.get("top_aspect", ""),
            vs_natal=r.get("top_natal_body", ""),
            sort_total=int(r.get("total_priority", 0)),
            sort_count=int(r.get("transit_count", 0)),
        ))

    model = Gio.ListStore.new(PlanetAggRow)
    for r in agg_rows:
        model.append(r)

    sort_model = Gtk.SortListModel(model=model)
    selection = Gtk.SingleSelection(model=sort_model)
    view = Gtk.ColumnView(model=selection)

    sorter_specs = {
        "Body": _make_sorter(PlanetAggRow, "body"),
        "Total": _make_sorter(PlanetAggRow, "sort_total", descending=True),
        "Count": _make_sorter(PlanetAggRow, "sort_count"),
        "Top Aspect": _make_sorter(PlanetAggRow, "top_aspect"),
        "vs Natal": _make_sorter(PlanetAggRow, "vs_natal"),
    }
    view.append_column(_text_column("Body", "body", sortable=True, sorter=sorter_specs["Body"]))
    view.append_column(_text_column("Total", "total", sortable=True, sorter=sorter_specs["Total"]))
    view.append_column(_text_column("Count", "count", sortable=True, sorter=sorter_specs["Count"]))
    view.append_column(_text_column("Top Aspect", "top_aspect", sortable=True, sorter=sorter_specs["Top Aspect"]))
    view.append_column(_text_column("vs Natal", "vs_natal", sortable=True, sorter=sorter_specs["vs Natal"]))

    # Default sort: total descending
    sort_model.set_sorter(sorter_specs["Total"])

    # Visible sort buttons (GTK 4.22's header row cannot host custom
    # widgets — see module docstring / _install_sort_buttons).
    buttons = {title: _header_button(title) for title in sorter_specs}
    sort_row = _install_sort_buttons(view, sort_model, buttons, sorter_specs,
                                     default_title="Total")
    view._sort_model = sort_model
    view._sort_buttons = buttons

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.append(sort_row)
    box.append(view)
    view.set_vexpand(True)
    return box
