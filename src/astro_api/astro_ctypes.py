"""
ctypes wrapper for libastro-calc.so
Python stdlib only.
"""
import ctypes
import os

# ------------------------------------------------------------------
# Load Swiss Ephemeris shared lib (dependency) with RTLD_GLOBAL so
# that symbols are visible to libastro-calc.so.

_SE_LIB = os.path.expanduser("~/swisseph_test/pyswisseph-2.10.3.2/libswe/libswe.so")
ctypes.CDLL(_SE_LIB, mode=ctypes.RTLD_GLOBAL)

# ------------------------------------------------------------------
# Find the shared library
_LIB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LIB_PATH = os.path.join(_LIB_DIR, "astro_calc", "libastro-calc.so")
if not os.path.exists(_LIB_PATH):
    # fallback: assume LD_LIBRARY_PATH or rpath has it
    _LIB_PATH = "libastro-calc.so"

_lib = ctypes.CDLL(_LIB_PATH)

# ------------------------------------------------------------------
# Constants from C header

AC_MAX_BODIES = 32
AC_ERRSTR_LEN = 256

AC_OK = 0
AC_ERR = -1

# Body IDs
AC_SUN = 0
AC_MOON = 1
AC_MERCURY = 2
AC_VENUS = 3
AC_MARS = 4
AC_JUPITER = 5
AC_SATURN = 6
AC_URANUS = 7
AC_NEPTUNE = 8
AC_PLUTO = 9
AC_MEAN_NODE = 10
AC_TRUE_NODE = 11
AC_CHIRON = 15
AC_LILITH = 12
AC_CERES = 17
AC_PALLAS = 18
AC_JUNO = 19
AC_VESTA = 20

# Aspects
AC_ASP_NONE = -1
AC_ASP_CONJUNCTION = 0
AC_ASP_SEMISEXTILE = 1
AC_ASP_SEMISQUARE = 2
AC_ASP_SEXTILE = 3
AC_ASP_SQUARE = 4
AC_ASP_TRINE = 5
AC_ASP_SESQUIQUADRATE = 6
AC_ASP_QUINCUNX = 7
AC_ASP_OPPOSITION = 8

# Orb presets
AC_ORB_CLASSICAL = 0
AC_ORB_MODERN = 1
AC_ORB_TIGHT = 2
AC_ORB_WIDE = 3

# ------------------------------------------------------------------
# Struct definitions

class AcBody(ctypes.Structure):
    _fields_ = [
        ("body_id", ctypes.c_int),
        ("name", ctypes.c_char * 32),
        ("longitude", ctypes.c_double),
        ("latitude", ctypes.c_double),
        ("distance", ctypes.c_double),
        ("speed", ctypes.c_double),
        ("retrograde", ctypes.c_int),
        ("sign", ctypes.c_int),
        ("sign_degree", ctypes.c_double),
        ("house", ctypes.c_int),
    ]

class AcCusp(ctypes.Structure):
    _fields_ = [
        ("house_num", ctypes.c_int),
        ("longitude", ctypes.c_double),
        ("sign", ctypes.c_int),
        ("sign_degree", ctypes.c_double),
    ]

class AcChart(ctypes.Structure):
    _fields_ = [
        ("result", ctypes.c_int),
        ("err", ctypes.c_char * AC_ERRSTR_LEN),
        ("num_bodies", ctypes.c_int),
        ("bodies", AcBody * AC_MAX_BODIES),
        ("cusps", AcCusp * 13),
        ("ascendant", ctypes.c_double),
        ("mc", ctypes.c_double),
        ("armc", ctypes.c_double),
        ("vertex", ctypes.c_double),
    ]

class AcAspect(ctypes.Structure):
    _fields_ = [
        ("aspect", ctypes.c_int),
        ("aspect_name", ctypes.c_char_p),
        ("exact_angle", ctypes.c_double),
        ("actual_angle", ctypes.c_double),
        ("orb", ctypes.c_double),
        ("applying", ctypes.c_int),
    ]

# ------------------------------------------------------------------
# Helper: body name → ID mapping

BODY_MAP = {
    "Sun": AC_SUN,
    "Moon": AC_MOON,
    "Mercury": AC_MERCURY,
    "Venus": AC_VENUS,
    "Mars": AC_MARS,
    "Jupiter": AC_JUPITER,
    "Saturn": AC_SATURN,
    "Uranus": AC_URANUS,
    "Neptune": AC_NEPTUNE,
    "Pluto": AC_PLUTO,
    "Mean Node": AC_MEAN_NODE,
    "True Node": AC_TRUE_NODE,
    "Chiron": AC_CHIRON,
    "Lilith": AC_LILITH,
    "Ceres": AC_CERES,
    "Pallas": AC_PALLAS,
    "Juno": AC_JUNO,
    "Vesta": AC_VESTA,
}

_NAME_TO_ID = {k.lower(): v for k, v in BODY_MAP.items()}
_ID_TO_NAME = {v: k for k, v in BODY_MAP.items()}

# Node alias handling per spec: North Node and Node are aliases of Mean Node.
# True Node is already present in BODY_MAP. South Node is derived at a higher layer.
_NODE_ALIASES = {
    "north node": AC_MEAN_NODE,
    "node": AC_MEAN_NODE,
}

def body_id_from_name(name: str) -> int:
    n = name.strip()
    if n in BODY_MAP:
        return BODY_MAP[n]
    low = n.lower()
    if low in _NAME_TO_ID:
        return _NAME_TO_ID[low]
    if low in _NODE_ALIASES:
        return _NODE_ALIASES[low]
    raise ValueError(f"Unknown body name: {name}")

def body_name_from_id(bid: int) -> str:
    return _ID_TO_NAME.get(bid, "Unknown")

# ------------------------------------------------------------------
# House systems mapping

HOUSE_SYSTEMS = {
    "A": "Equal",
    "B": "Alcabitus",
    "C": "Campanus",
    "D": "Equal (MC)",
    "E": "Equal",
    "F": "Carter poli-equ.",
    "G": "Gauquelin sectors",
    "H": "Horizon / azimuth",
    "I": "Sunshine",
    "i": "Sunshine (alt.)",
    "K": "Koch",
    "L": "Porphyry",
    "M": "Morinus",
    "N": "Equal/1=Aries",
    "O": "Porphyry",
    "P": "Placidus",
    "Q": "Pullen SD",
    "q": "Pullen SR",
    "R": "Regiomontanus",
    "S": "Sripati",
    "T": "Polich/Page",
    "U": "Krusinski-Pisa",
    "V": "Vehlow equal",
    "W": "Whole sign",
    "X": "Axial rotation",
    "Y": "APC houses",
}

# ------------------------------------------------------------------
# Orb presets mapping

ORB_PRESETS = {
    "classical": AC_ORB_CLASSICAL,
    "modern": AC_ORB_MODERN,
    "tight": AC_ORB_TIGHT,
    "wide": AC_ORB_WIDE,
}

def orb_preset_from_name(name: str) -> int:
    return ORB_PRESETS.get(name.lower(), AC_ORB_MODERN)

# ------------------------------------------------------------------
# C function signatures

_lib.ac_init.argtypes = [ctypes.c_char_p]
_lib.ac_init.restype = ctypes.c_int

_lib.ac_cleanup.argtypes = []
_lib.ac_cleanup.restype = None

_lib.ac_calc_bodies.argtypes = [
    ctypes.c_double,
    ctypes.POINTER(ctypes.c_int),
    ctypes.c_int,
    ctypes.POINTER(AcBody),
]
_lib.ac_calc_bodies.restype = ctypes.c_int

_lib.ac_calc_houses.argtypes = [
    ctypes.c_double,
    ctypes.c_double,
    ctypes.c_double,
    ctypes.c_char,
    ctypes.POINTER(AcCusp),
    ctypes.POINTER(ctypes.c_double),
    ctypes.POINTER(ctypes.c_double),
]
_lib.ac_calc_houses.restype = ctypes.c_int

_lib.ac_calc_chart.argtypes = [
    ctypes.c_double,
    ctypes.c_double,
    ctypes.c_double,
    ctypes.POINTER(ctypes.c_int),
    ctypes.c_int,
    ctypes.c_char,
    ctypes.POINTER(AcChart),
]
_lib.ac_calc_chart.restype = ctypes.c_int

_lib.ac_date_to_jd.argtypes = [
    ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_double,
]
_lib.ac_date_to_jd.restype = ctypes.c_double

_lib.ac_sign_name.argtypes = [ctypes.c_int]
_lib.ac_sign_name.restype = ctypes.c_char_p

_lib.ac_body_name.argtypes = [ctypes.c_int]
_lib.ac_body_name.restype = ctypes.c_char_p

_lib.ac_aspect_angle.argtypes = [ctypes.c_double, ctypes.c_double]
_lib.ac_aspect_angle.restype = ctypes.c_double

_lib.ac_detect_aspect.argtypes = [
    ctypes.c_double, ctypes.c_double,
    ctypes.c_double, ctypes.c_double,
    ctypes.c_int,
    ctypes.POINTER(AcAspect),
]
_lib.ac_detect_aspect.restype = ctypes.c_int

# ------------------------------------------------------------------
# Python wrappers

def _default_ephe_path() -> str | None:
    """Resolve a Swiss Ephemeris data directory, or None (Moshier).

    Order: ASTRO_EPHE_PATH env var → common local installs. The full
    ephemeris is REQUIRED for minor bodies (Chiron, Lilith, Ceres,
    Pallas, Juno, Vesta) — Moshier's built-in tables cannot compute
    them, and the C wrapper silently zero-fills on failure (which is
    how '0.00 Aries' Chiron appeared).
    """
    import os
    candidates = [
        os.environ.get("ASTRO_EPHE_PATH"),
        "/media/xephyr/Local Data/Astrolog/ephemeris",
        "/usr/share/swisseph",
        "/usr/share/ephe",
    ]
    for c in candidates:
        if c and os.path.isdir(c):
            # Require at least the planet files; a bare dir is not proof.
            if any(os.path.exists(os.path.join(c, f)) for f in ("sepl_00.se1", "se01800.se1", "se01801.se1", "se01802.se1")):
                return c
    return None


def ac_init(ephe_path: str | None = None) -> int:
    """Initialize Swiss Ephemeris.

    Pass an explicit directory to override; otherwise the default full
    ephemeris is used when available, falling back to Moshier.
    """
    path_bytes = None
    if ephe_path:
        path_bytes = ephe_path.encode("utf-8")
    else:
        d = _default_ephe_path()
        if d:
            path_bytes = d.encode("utf-8")
    return _lib.ac_init(path_bytes)

def ac_cleanup() -> None:
    _lib.ac_cleanup()

def ac_date_to_jd(year: int, month: int, day: int,
                  hour: int, minute: int, second: int,
                  tz_offset: float) -> float:
    return _lib.ac_date_to_jd(year, month, day, hour, minute, second, tz_offset)

def ac_sign_name(sign_num: int) -> str:
    return _lib.ac_sign_name(sign_num).decode("utf-8")

def ac_body_name(body_id: int) -> str:
    return _lib.ac_body_name(body_id).decode("utf-8")

def ac_calc_chart(jd_ut: float, lat: float, lon: float,
                  body_ids: list[int], house_system: str) -> dict:
    """
    Calculate a full chart. Returns a clean Python dict.
    """
    n = len(body_ids)
    if n > AC_MAX_BODIES:
        raise ValueError(f"Too many bodies (max {AC_MAX_BODIES})")

    ids_arr = (ctypes.c_int * n)(*body_ids)
    chart = AcChart()

    hs_char = house_system.encode("utf-8")[0] if house_system else ord("K")
    ret = _lib.ac_calc_chart(jd_ut, lat, lon, ids_arr, n, hs_char, ctypes.byref(chart))

    if ret != AC_OK:
        err = chart.err.decode("utf-8").strip("\x00")
        raise RuntimeError(f"Chart calculation failed: {err}")

    bodies = []
    for i in range(chart.num_bodies):
        b = chart.bodies[i]
        # The C wrapper zero-fills a body when swe_calc_ut fails (e.g.
        # minor bodies unavailable in the Moshier fallback ephemeris).
        # A legitimate body NEVER has distance 0 — drop the fake rather
        # than render a bogus "0.00 Aries" planet (2026-08-24 bug).
        if b.distance == 0.0 and b.longitude == 0.0 and b.speed == 0.0:
            continue
        bodies.append({
            "body_id": b.body_id,
            "name": b.name.decode("utf-8").strip("\x00"),
            "longitude": round(b.longitude, 6),
            "latitude": round(b.latitude, 6),
            "distance": round(b.distance, 6),
            "speed": round(b.speed, 6),
            "retrograde": bool(b.retrograde),
            "sign": b.sign,
            "sign_name": ac_sign_name(b.sign),
            "sign_degree": round(b.sign_degree, 6),
            "house": b.house,
        })

    houses = []
    for i in range(1, 13):
        c = chart.cusps[i]
        houses.append({
            "house_num": c.house_num,
            "longitude": round(c.longitude, 6),
            "sign": c.sign,
            "sign_name": ac_sign_name(c.sign),
            "sign_degree": round(c.sign_degree, 6),
        })

    return {
        "result": chart.result,
        "num_bodies": chart.num_bodies,
        "bodies": bodies,
        "houses": houses,
        "ascendant": round(chart.ascendant, 6),
        "mc": round(chart.mc, 6),
        "armc": round(chart.armc, 6),
        "vertex": round(chart.vertex, 6),
    }

def ac_detect_aspect(lon1: float, speed1: float,
                     lon2: float, speed2: float,
                     preset: int) -> dict:
    asp = AcAspect()
    _lib.ac_detect_aspect(lon1, speed1, lon2, speed2, preset, ctypes.byref(asp))
    return {
        "aspect": asp.aspect,
        "aspect_name": (asp.aspect_name.decode("utf-8")
                         if isinstance(asp.aspect_name, bytes)
                         else asp.aspect_name),
        "exact_angle": round(asp.exact_angle, 4),
        "actual_angle": round(asp.actual_angle, 4),
        "orb": round(asp.orb, 4),
        "applying": bool(asp.applying),
    }

def calculate_aspects(bodies: list[dict], preset: int) -> list[dict]:
    """
    Calculate aspects between all pairs of bodies.
    """
    aspects = []
    n = len(bodies)
    for i in range(n):
        for j in range(i + 1, n):
            a = bodies[i]
            b = bodies[j]
            asp = ac_detect_aspect(
                a["longitude"], a["speed"],
                b["longitude"], b["speed"],
                preset,
            )
            if asp["aspect"] != AC_ASP_NONE:
                aspects.append({
                    "body_a": a["name"],
                    "body_b": b["name"],
                    "aspect_id": asp["aspect"],
                    "aspect_name": asp["aspect_name"],
                    "exact_angle": asp["exact_angle"],
                    "actual_angle": asp["actual_angle"],
                    "orb": asp["orb"],
                    "applying": asp["applying"],
                })
    return aspects

# ------------------------------------------------------------------
# Module-level init

ac_init()
