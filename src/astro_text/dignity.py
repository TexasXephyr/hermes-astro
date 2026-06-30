"""
Dignity rule lookup for astrology-tool.

This module replaces hard-coded domicile/exaltation/detriment/fall tables
with lookups against the central YAML corpus.
"""
from astro_data.loaders import yaml_loader


def _load_dignities() -> dict:
    return yaml_loader("dignities")


def _load_scoring() -> dict:
    return yaml_loader("scoring")


def _load_signs() -> dict:
    return yaml_loader("signs")


def _normalize_body(name: str) -> str:
    """Map common aliases and node variants to canonical names."""
    n = name.strip()
    bodies = yaml_loader("bodies")
    if n in bodies:
        return n

    aliases = {
        "sun": "Sun",
        "moon": "Moon",
        "mercury": "Mercury",
        "venus": "Venus",
        "mars": "Mars",
        "jupiter": "Jupiter",
        "saturn": "Saturn",
        "uranus": "Uranus",
        "neptune": "Neptune",
        "pluto": "Pluto",
        "mean node": "Mean Node",
        "true node": "True Node",
        "north node": "Mean Node",
        "node": "Mean Node",
        "south node": "South Node",
        "chiron": "Chiron",
    }
    canonical = aliases.get(n.lower())
    return canonical if canonical and canonical in bodies else n


def _sign_index(name: str) -> int:
    signs = _load_signs()
    if name not in signs:
        raise ValueError(f"Unknown sign '{name}'")
    return signs[name]["id"]


def _opposite_sign(name: str) -> str:
    idx = _sign_index(name)
    opposite_idx = (idx + 6) % 12
    signs = _load_signs()
    for sign_name, data in signs.items():
        if data["id"] == opposite_idx:
            return sign_name
    raise ValueError(f"Could not find opposite of sign '{name}'")


def get_dignity(body: str, sign: str, sign_degree: float | None = None) -> dict:
    """
    Return the essential dignity of a body in a sign.

    Args:
        body: Canonical body name.
        sign: Canonical sign name.
        sign_degree: Optional degree within sign (0-30). If provided,
                     exaltation/fall are marked exact when within the
n                     configured orb (default 1 degree if not specified).

    Returns:
        Dict with keys: label, score, exact_degree.
    """
    scores = _load_scoring()
    dignities = _load_dignities()
    body_name = _normalize_body(body)

    # Validate sign first so unknown signs raise ValueError.
    _sign_index(sign)

    entry = dignities.get(body_name, {})

    def _in_list(field: str) -> bool:
        return sign in entry.get(field, [])

    def _degree_match(field: str) -> bool:
        """
        Return True if exaltation/fall applies for this placement.
        When no sign_degree is provided, fall back to sign-based dignity.
        When sign_degree is provided, require it to be within the configured orb.
        """
        if sign_degree is None:
            return True
        deg = entry.get(f"{field}_degree")
        if deg is None:
            return True
        orb = entry.get(f"{field}_orb", 2.0)
        return abs(sign_degree - float(deg)) <= orb

    def _exact(field: str) -> bool:
        """Return True if sign_degree is within the tight exact-degree orb."""
        if sign_degree is None:
            return False
        deg = entry.get(f"{field}_degree")
        if deg is None:
            return False
        exact_orb = entry.get(f"{field}_exact_orb", 0.5)
        return abs(sign_degree - float(deg)) <= exact_orb

    if _in_list("domicile"):
        return {
            "label": "domicile",
            "score": scores.get("domicile", 5),
            "exact_degree": False,
        }
    if _in_list("exaltation") and _degree_match("exaltation"):
        return {
            "label": "exaltation",
            "score": scores.get("exaltation", 4),
            "exact_degree": _exact("exaltation"),
        }
    if _in_list("detriment"):
        return {
            "label": "detriment",
            "score": scores.get("detriment", -5),
            "exact_degree": False,
        }
    if _in_list("fall") and _degree_match("fall"):
        return {
            "label": "fall",
            "score": scores.get("fall", -4),
            "exact_degree": _exact("fall"),
        }

    return {
        "label": "peregrine",
        "score": scores.get("peregrine", 0),
        "exact_degree": False,
    }


def score_dignity(body: str, sign: str, house: int, retrograde: bool = False, sign_degree: float | None = None) -> int:
    """
    Return a total dignity score for a body placement.

    Scoring is read from scoring.yaml:
        - essential dignity (domicile/exaltation/detriment/fall/peregrine)
        - accidental dignity by house quality (angular/succedent/cadent)
        - direct/retrograde modifier
    """
    scores = _load_scoring()
    essential = get_dignity(body, sign, sign_degree=sign_degree)
    score = essential["score"]

    # Accidental dignity by house
    if house in {1, 4, 7, 10}:
        score += scores.get("angular", 3)
    elif house in {2, 5, 8, 11}:
        score += scores.get("succedent", 2)
    elif house in {3, 6, 9, 12}:
        score += scores.get("cadent", 1)

    # Directional modifier
    if retrograde:
        score += scores.get("retrograde", -1)
    else:
        score += scores.get("direct", 1)

    return score
