"""test_png_dialog_flow.py — Headless verification of item 33 fix: PNG save
dialog flow.

Covers:
1. _on_png_dialog_result writes a real non-empty PNG for natal/transit/
   synastry SVGs (Gdk.Texture rasterization, same code path as the GUI).
2. _resolve_save_path handles a GFile with get_path() == None by falling
   back to the file:// URI (portal-based Gtk.FileDialog case).
3. _on_dialog_result treats ANY GLib.Error from save_finish as a silent
   cancel (no status-bar error) and shows a clear message when the chosen
   path cannot be resolved.

Runs without a display.
"""

import os
import sys
import tempfile

sys.path.insert(0, "/home/xephyr/astro/src")

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from astro_gui.window import MainWindow
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
# Fixtures: real SVGs from the library backend (no server needed)
# ------------------------------------------------------------------
def _load_svgs():
    client = AstroClient()
    people = client.list_people().get("people", [])
    xephyr = next((p for p in people if p.get("name") == "Xephyr"), None)
    assert xephyr is not None, "Xephyr not found in people list"
    chart = client.get_chart(xephyr["chart_id"])
    assert chart is not None, "Missing natal chart"
    renderer = WheelRenderer(width=600, height=600)
    natal = renderer.render_natal(chart)
    transit = renderer.render_transit(chart, chart, scale=1.0)
    # Synastry: pick a second person with a chart if available, else reuse
    partner = next(
        (p for p in people if p.get("name") != "Xephyr" and p.get("chart_id")),
        None,
    )
    if partner:
        chart_b = client.get_chart(partner["chart_id"])
        synastry = renderer.render_synastry(
            chart, chart_b, [{"a": "Sun", "b": "Moon", "aspect": "trine"}]
        )
    else:
        synastry = renderer.render_synastry(
            chart, chart, [{"a": "Sun", "b": "Moon", "aspect": "trine"}]
        )
    return natal, transit, synastry


# ------------------------------------------------------------------
# 1. _on_png_dialog_result writes real non-empty PNGs
# ------------------------------------------------------------------
def _png_writes():
    w = MainWindow()
    try:
        natal, transit, synastry = _load_svgs()
        for label, svg in (("natal", natal), ("transit", transit), ("synastry", synastry)):
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, f"{label}.png")
                w._on_png_dialog_result(path, svg)
                assert os.path.exists(path), f"{label}: PNG missing"
                size = os.path.getsize(path)
                assert size > 0, f"{label}: PNG empty ({size} bytes)"
                # PNG magic bytes
                with open(path, "rb") as f:
                    assert f.read(8) == b"\x89PNG\r\n\x1a\n", f"{label}: bad PNG header"
                msg = w.status_bar._info_label.get_text()
                assert msg.startswith("Exported PNG:"), f"{label}: status {msg!r}"
    finally:
        w.close()


check("_on_png_dialog_result writes non-empty PNGs for natal/transit/synastry",
      _png_writes)


# ------------------------------------------------------------------
# 2. _resolve_save_path: get_path() == None falls back to file:// URI
# ------------------------------------------------------------------
class _FakeGFile:
    """Minimal stand-in for a Gio.File with no local path."""

    def __init__(self, path=None, uri=None):
        self._path = path
        self._uri = uri

    def get_path(self):
        return self._path

    def get_uri(self):
        return self._uri


def _resolve_paths():
    w = MainWindow()
    try:
        # Normal local path
        assert w._resolve_save_path(_FakeGFile(path="/tmp/out.png")) == "/tmp/out.png"
        # Portal-style: no local path, file:// URI with percent-encoding
        uri = "file:///home/xephyr/Downloads/my%20chart.png"
        assert w._resolve_save_path(_FakeGFile(path=None, uri=uri)) == \
            "/home/xephyr/Downloads/my chart.png", "URI fallback must unquote"
        # Unresolvable: neither path nor file:// URI
        assert w._resolve_save_path(_FakeGFile(path=None, uri="http://x/y")) is None
        assert w._resolve_save_path(_FakeGFile(path=None, uri=None)) is None
    finally:
        w.close()


check("_resolve_save_path falls back to file:// URI when get_path() is None",
      _resolve_paths)


# ------------------------------------------------------------------
# 3. _on_dialog_result: silent cancel + clear unresolvable-path message
# ------------------------------------------------------------------
class _FakeDialog:
    def __init__(self, file=None, error=None):
        self._file = file
        self._error = error

    def save_finish(self, result):
        if self._error is not None:
            raise self._error
        return self._file


def _cancel_is_silent():
    w = MainWindow()
    try:
        fired = []

        def cb(path, payload):
            fired.append(path)

        # Any GLib.Error from save_finish = silent cancel, no status change
        err = GLib.Error.new_literal(
            GLib.quark_from_string("gtk-file-dialog-error-quark"),
            "Dismissed by user",
            1,
        )
        w._on_dialog_result(_FakeDialog(error=err), None, (cb, ()))
        assert fired == [], "cancel must not invoke the callback"
        msg = w.status_bar._info_label.get_text()
        assert "Export error" not in msg and "PNG export failed" not in msg, \
            f"cancel leaked into status bar: {msg!r}"
    finally:
        w.close()


check("_on_dialog_result: ANY save_finish error is a silent cancel", _cancel_is_silent)


def _unresolvable_path_message():
    w = MainWindow()
    try:
        fired = []

        def cb(path, payload):
            fired.append(path)

        # GFile with no path and no file:// URI -> clear message, no crash
        w._on_dialog_result(_FakeDialog(file=_FakeGFile(path=None, uri=None)),
                            None, (cb, ()))
        assert fired == [], "unresolvable path must not invoke the callback"
        msg = w.status_bar._info_label.get_text()
        assert msg == "Could not resolve the chosen path", f"status: {msg!r}"
    finally:
        w.close()


check("_on_dialog_result: unresolvable path shows clear message, no crash",
      _unresolvable_path_message)


def _normal_path_dispatches():
    w = MainWindow()
    try:
        fired = []

        def cb(path, payload):
            fired.append((path, payload))

        w._on_dialog_result(
            _FakeDialog(file=_FakeGFile(path="/tmp/out.png")),
            None, (cb, ("svg-data",)),
        )
        assert fired == [("/tmp/out.png", ("svg-data",))], f"fired: {fired!r}"
    finally:
        w.close()


check("_on_dialog_result: normal path dispatches to the callback", _normal_path_dispatches)


def _png_callback_accepts_tuple_payload():
    """Regression: _pick_save_path passes payload as a 1-tuple; the PNG
    callback must unpack it (the old code did `svg = payload` and crashed
    with 'write() argument must be str, not tuple')."""
    w = MainWindow()
    try:
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60"><rect width="60" height="60" fill="#1a1a1a"/></svg>'
        path = "/tmp/png_tuple_payload_test.png"
        w._on_png_dialog_result(path, (svg,))
        assert os.path.exists(path), "PNG not written"
        assert os.path.getsize(path) > 0, "PNG empty"
        msg = w.status_bar._info_label.get_text()
        assert msg.startswith("Exported PNG"), f"status: {msg!r}"
    finally:
        w.close()
        if os.path.exists("/tmp/png_tuple_payload_test.png"):
            os.unlink("/tmp/png_tuple_payload_test.png")


check("_on_png_dialog_result: tuple payload (real dialog path) writes PNG",
      _png_callback_accepts_tuple_payload)


print(f"\nResults: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
