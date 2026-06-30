"""
Chart analysis orchestrator.
Combines dignity, patterns, house emphasis, element/modality balance.
Stdlib only.
"""
from .dignity import calculate_dignity
from .patterns import detect_patterns
from astro_data.loaders import yaml_loader


def _sign_name_from_id(sign_id: int) -> str:
    sign_names = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    ]
    return sign_names[sign_id % 12]


def _sign_element(sign_id: int) -> str:
    signs = yaml_loader("signs")
    return signs[_sign_name_from_id(sign_id)]["element"]


def _sign_modality(sign_id: int) -> str:
    signs = yaml_loader("signs")
    return signs[_sign_name_from_id(sign_id)]["modality"]


def analyze_chart(chart_data: dict) -> dict:
    """
    Full chart analysis from chart JSON dict.
    Expected keys: bodies, houses, aspects (optional).
    """
    bodies = chart_data.get("bodies", [])
    aspects = chart_data.get("aspects", [])

    # 1. Dignities
    dignities = []
    for b in bodies:
        dignities.append(calculate_dignity(
            body_name=b["name"],
            sign=b["sign"],
            sign_degree=b["sign_degree"],
            house=b["house"],
            retrograde=b.get("retrograde", False),
        ))

    # 2. Patterns
    patterns = detect_patterns(chart_data)

    # 3. House emphasis
    house_counts = {}
    for b in bodies:
        house_counts[b["house"]] = house_counts.get(b["house"], 0) + 1
    house_emphasis = dict(sorted(house_counts.items(), key=lambda kv: -kv[1]))

    # 4. Element balance
    element_counts = {"fire": 0, "earth": 0, "air": 0, "water": 0}
    for b in bodies:
        element_counts[_sign_element(b["sign"])] += 1

    # 5. Modality balance
    modality_counts = {"cardinal": 0, "fixed": 0, "mutable": 0}
    for b in bodies:
        modality_counts[_sign_modality(b["sign"])] += 1

    return {
        "dignities": dignities,
        "patterns": patterns,
        "house_emphasis": house_emphasis,
        "element_balance": element_counts,
        "modality_balance": modality_counts,
    }
