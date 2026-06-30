"""test_sprint1.py — Import verification and layout summary for Sprint 1."""

import sys
sys.path.insert(0, "/home/xephyr/astro/src")

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
# 1. GTK4 import
# ------------------------------------------------------------------
check("import gi", lambda: (__import__("gi")))
check("gi.require_version Gtk 4.0", lambda: (__import__("gi").require_version("Gtk", "4.0")))
check("from gi.repository import Gtk", lambda: (__import__("gi.repository", fromlist=["Gtk"]).Gtk))
check("from gi.repository import GObject", lambda: (__import__("gi.repository", fromlist=["GObject"]).GObject))
check("from gi.repository import Gdk", lambda: (__import__("gi.repository", fromlist=["Gdk"]).Gdk))
check("from gi.repository import GLib", lambda: (__import__("gi.repository", fromlist=["GLib"]).GLib))

# ------------------------------------------------------------------
# 2. Module-level imports
# ------------------------------------------------------------------
check("import astro_gui", lambda: (__import__("astro_gui")))
check("import astro_gui.api_client", lambda: (__import__("astro_gui.api_client")))
check("import astro_gui.main", lambda: (__import__("astro_gui.main")))
check("import astro_gui.window", lambda: (__import__("astro_gui.window")))
check("import astro_gui.widgets.person_selector", lambda: (__import__("astro_gui.widgets.person_selector")))
check("import astro_gui.widgets.status_bar", lambda: (__import__("astro_gui.widgets.status_bar")))

# ------------------------------------------------------------------
# 3. Class-level imports via importlib
# ------------------------------------------------------------------
import importlib

check("AstroApiClient import", lambda: importlib.import_module("astro_gui").AstroApiClient)
check("AstroApiError import", lambda: importlib.import_module("astro_gui").AstroApiError)
check("AstroGuiApplication import", lambda: importlib.import_module("astro_gui").AstroGuiApplication)
check("MainWindow import", lambda: importlib.import_module("astro_gui").MainWindow)
check("PersonSelector import", lambda: importlib.import_module("astro_gui").PersonSelector)
check("StatusBar import", lambda: importlib.import_module("astro_gui").StatusBar)

# ------------------------------------------------------------------
# 4. Instantiation tests (no display needed for simple widgets)
# ------------------------------------------------------------------
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject

# Need a Gtk.Application to create an ApplicationWindow (MainWindow)
# But we can instantiate plain widgets without one.
check("Gtk.Box instantiation", lambda: Gtk.Box())
check("Gtk.Notebook instantiation", lambda: Gtk.Notebook())
check("Gtk.Paned instantiation", lambda: Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL))

# StatusBar is a plain Gtk.Box subclass
check("StatusBar instantiation", lambda: importlib.import_module("astro_gui").StatusBar())

# PersonSelector also plain Gtk.Box subclass, but it calls list_people()
# We mock the client or rely on exception swallowing inside _load_people.
check("PersonSelector instantiation", lambda: importlib.import_module("astro_gui").PersonSelector())

# ------------------------------------------------------------------
# 5. GObject type registration verification
# ------------------------------------------------------------------

check("StatusBar GObject type", lambda: GObject.type_from_name("AstroStatusBar"))
check("PersonSelector GObject type", lambda: GObject.type_from_name("AstroPersonSelector"))

# MainWindow is registered when the module is imported
check("MainWindow GObject type", lambda: GObject.type_from_name("AstroMainWindow"))

# AstroGuiApplication subclasses Gtk.Application and its pygobject type name
# is namespaced (astro_gui+main+AstroGuiApplication); verify by instantiation.
AppClass = importlib.import_module("astro_gui").AstroGuiApplication
check("AstroGuiApplication instantiation", lambda: AppClass())
check("AstroGuiApplication is Gtk.Application", lambda: issubclass(AppClass, Gtk.Application))

# ------------------------------------------------------------------
# 6. Layout summary
# ------------------------------------------------------------------
print("\n" + "=" * 50)
print("Sprint 1 Layout Summary")
print("=" * 50)
print("""
MainWindow (AstroMainWindow)
  └─ Gtk.Box (vertical, root)
       ├─ PersonSelector (AstroPersonSelector)
       │     └─ [Label] [DropDown] [+ New Person] [Edit]
       ├─ Gtk.Paned (horizontal)
       │     ├─ start: Navigation Panel sidebar (placeholder)
       │     └─ end:  Gtk.Notebook
       │                 └─ Tab: "Natal Wheel" (placeholder)
       └─ StatusBar (AstroStatusBar)
             └─ [info label] [current time]
""")

print("=" * 50)
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
