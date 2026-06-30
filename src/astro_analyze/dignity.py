"""
Classical and accidental dignity calculator.
Tropical zodiac, stdlib only.

This module now delegates essential dignity and scoring to astro_text,
which is backed by the central YAML corpus in astro_data.
"""
from astro_text.dignity import get_dignity, score_dignity
from astro_text.format import ordinal


# ------------------------------------------------------------------
# House quality
ANGULAR_HOUSES = {1, 4, 7, 10}
SUCCEDENT_HOUSES = {2, 5, 8, 11}
CADENT_HOUSES = {3, 6, 9, 12}


def _normalize_body_name(name: str) -> str:
    """Map node names and common variants to canonical keys.

    Per the centralization spec, North Node is an alias of Mean Node.
    Mean/True/South nodes remain distinct when explicitly named.
    """
    n = name.strip()
    mapping = {
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
        "lilith": "Lilith",
        "ceres": "Ceres",
        "pallas": "Pallas",
        "juno": "Juno",
        "vesta": "Vesta",
    }
    return mapping.get(n.lower(), n)


def calculate_dignity(body_name: str, sign: int, sign_degree: float,
                      house: int, retrograde: bool) -> dict:
    """
    Return dignity assessment with score.

    Essential dignity is now looked up via astro_text from the YAML corpus.
    Scoring:
        +5 domicile
        +4 exaltation
        -5 detriment
        -4 fall
        +3 angular house
        +2 succedent house
        +1 cadent house
        +1 direct
        -2 retrograde
    """
    name = _normalize_body_name(body_name)

    # Map numeric sign index to canonical sign name.
    sign_names = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    ]
    sign_name = sign_names[sign % 12]

    essential = get_dignity(name, sign_name, sign_degree)
    domicile = essential["label"] == "domicile"
    exaltation = essential["label"] == "exaltation"
    detriment = essential["label"] == "detriment"
    fall = essential["label"] == "fall"
    exact_degree = essential["exact_degree"]

    # Accidental dignity by house
    if house in ANGULAR_HOUSES:
        accidental = "strong"
    elif house in SUCCEDENT_HOUSES:
        accidental = "moderate"
    elif house in CADENT_HOUSES:
        accidental = "weak"
    else:
        accidental = "weak"

    score = score_dignity(name, sign_name, house, retrograde, sign_degree)

    return {
        "body": name,
        "domicile": domicile,
        "exaltation": exaltation,
        "exact_degree": exact_degree,
        "detriment": detriment,
        "fall": fall,
        "accidental": accidental,
        "retrograde": retrograde,
        "score": score,
    }
