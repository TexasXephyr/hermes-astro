"""
YAML-backed dignity/accidental scoring module.

Exposes score() used by tests that expect a legacy-compatible API.
"""
from astro_text.dignity import score_dignity

__all__ = ["score"]


def score(body: str, sign: str, house: int, retrograde: bool = False) -> int:
    """Legacy-compatible wrapper around astro_text.dignity.score_dignity."""
    return score_dignity(body, sign, house, retrograde)
