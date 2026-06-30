"""
astro_calc — C FFI wrapper for Swiss Ephemeris.

Provides low-level chart calculation via libastro-calc.so.
"""
from .astro_ctypes import (
    ac_init,
    ac_cleanup,
    ac_date_to_jd,
    ac_calc_chart,
    body_id_from_name,
    body_name_from_id,
    orb_preset_from_name,
    calculate_aspects,
    ac_sign_name,
    ac_body_name,
    ac_detect_aspect,
    # Constants
    AC_OK,
    AC_ERR,
    AC_MAX_BODIES,
    AC_ASP_NONE,
    AC_ASP_CONJUNCTION,
    AC_ASP_SEMISEXTILE,
    AC_ASP_SEMISQUARE,
    AC_ASP_SEXTILE,
    AC_ASP_SQUARE,
    AC_ASP_TRINE,
    AC_ASP_SESQUIQUADRATE,
    AC_ASP_QUINCUNX,
    AC_ASP_OPPOSITION,
    AC_ORB_CLASSICAL,
    AC_ORB_MODERN,
    AC_ORB_TIGHT,
    AC_ORB_WIDE,
)

__all__ = [
    # Functions
    "ac_init",
    "ac_cleanup",
    "ac_date_to_jd",
    "ac_calc_chart",
    "body_id_from_name",
    "body_name_from_id",
    "orb_preset_from_name",
    "calculate_aspects",
    "ac_sign_name",
    "ac_body_name",
    "ac_detect_aspect",
    # Constants
    "AC_OK",
    "AC_ERR",
    "AC_MAX_BODIES",
    "AC_ASP_NONE",
    "AC_ASP_CONJUNCTION",
    "AC_ASP_SEMISEXTILE",
    "AC_ASP_SEMISQUARE",
    "AC_ASP_SEXTILE",
    "AC_ASP_SQUARE",
    "AC_ASP_TRINE",
    "AC_ASP_SESQUIQUADRATE",
    "AC_ASP_QUINCUNX",
    "AC_ASP_OPPOSITION",
    "AC_ORB_CLASSICAL",
    "AC_ORB_MODERN",
    "AC_ORB_TIGHT",
    "AC_ORB_WIDE",
]
