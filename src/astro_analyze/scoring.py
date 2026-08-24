"""
Composite transit priority scoring — the "relative value" of a transit.

This module centralizes the aspect-priority formula that was proven in
morning_brief_producer.py and duplicated in astro-transit-cookbook:

    priority = floor(contact_relevance / (1 + 0.2*|days| + 0.15*days^2))

where contact_relevance = aspect_score + dig_t + dig_n + applying_bonus
                          + rulership + luminary

All weights come from the central YAML corpus (scoring.yaml) so there is a
single source of truth. Consumers:

- astro_analyze.transits.period_impact  (adds `priority` to each event)
- astro_api server /v1/analysis/period-impact and /v1/chart/transit
- astro CLI `grid` command (sortable transit table)
- astro-transit-cookbook (deduped to import from here)
"""
from __future__ import annotations

import math

from astro_data.loaders import yaml_loader
from astro_text.dignity import get_dignity

MAJOR_ASPECTS = {"conjunction", "opposition", "trine", "square", "sextile", "quincunx"}


def _scoring() -> dict:
    return yaml_loader("scoring")


def aspect_weights() -> dict:
    """Base weight per major aspect type (from scoring.yaml)."""
    return _scoring().get("aspect_weights", {})


def aspect_value(aspect: str, orb: float, grid_weight: float = 1.0) -> int:
    """Base aspect score from type and orb, with non-linear orb decay.

    direction_multiplier = 2.0 * exp(a*orb + b*orb^2) with a, b from
    scoring.yaml. Returns floor(weight * multiplier * grid_weight).
    """
    s = _scoring()
    a = float(s.get("orb_decay_a", 0.347))
    b = float(s.get("orb_decay_b", -0.15))
    weight = aspect_weights().get(aspect.lower(), 0)
    direction_multiplier = 2.0 * math.exp(a * orb + b * orb * orb)
    return math.floor(weight * direction_multiplier * grid_weight)


def compute_planetary_grid_weights(transit_chart: dict) -> dict:
    """Two-pass grid-weight computation from current-sky aspects.

    Pass 1: sum raw aspect values (grid_weight=1.0) for each planet.
    Pass 2: grid_weight = 1.0 + grid_scale * sqrt(raw_sum).
    Only major aspects contribute.
    """
    s = _scoring()
    scale = float(s.get("grid_scale", 0.1))
    raw: dict[str, float] = {}
    for asp in transit_chart.get("aspects", []):
        name = (asp.get("aspect_name") or asp.get("aspect", "")).lower()
        if name not in MAJOR_ASPECTS:
            continue
        orb = float(asp.get("orb", 999))
        val = aspect_value(name, orb, 1.0)  # Pass 1: no multiplier
        a = asp.get("body_a") or asp.get("transit_body") or ""
        b = asp.get("body_b") or asp.get("natal_body") or ""
        if a:
            raw[a] = raw.get(a, 0) + val
        if b:
            raw[b] = raw.get(b, 0) + val
    return {p: 1.0 + scale * math.sqrt(v) for p, v in raw.items()}


def _dignity_score(body_name: str, sign_name: str) -> int:
    if not sign_name:
        return 0
    try:
        return get_dignity(body_name, sign_name)["score"]
    except ValueError:
        return 0


def _rules_any(body: str, sign: str) -> bool:
    if not sign:
        return False
    try:
        return get_dignity(body, sign)["label"] == "domicile"
    except ValueError:
        return False


def aspect_priority(
    t_body: str,
    t_sign: str,
    n_body: str,
    n_sign: str,
    orb: float,
    days: int,
    aspect: str,
    grid_weight: float = 1.0,
) -> int:
    """Composite priority score for a transit aspect. Higher = more significant.

    Mirrors morning_brief_producer.aspect_priority: aspect weight decayed by
    orb, dignity of both bodies, rulership bonus, luminary bonus, applying
    bonus, and distance-to-exact penalty.
    """
    s = _scoring()
    aspect_score = aspect_value(aspect, orb, grid_weight)

    dig_t = _dignity_score(t_body, t_sign)
    dig_n = _dignity_score(n_body, n_sign)

    rulership = int(s.get("rulership_bonus", 20)) if (
        _rules_any(t_body, n_sign) or _rules_any(n_body, t_sign)
    ) else 0

    luminary = int(s.get("luminary_bonus", 10)) if (
        t_body in ("Sun", "Moon") or n_body in ("Sun", "Moon")
    ) else 0

    applying_bonus = int(s.get("applying_bonus", 15)) if days >= 0 else 0

    contact_relevance = (
        aspect_score + dig_t + dig_n + applying_bonus + rulership + luminary
    )

    lin = float(s.get("distance_linear", 0.2))
    quad = float(s.get("distance_quadratic", 0.15))
    return math.floor(contact_relevance / (1 + lin * abs(days) + quad * abs(days) ** 2))


def score_active_transits(
    active_transits: list[dict],
    natal_chart: dict,
    transit_chart: dict,
) -> list[dict]:
    """Attach `priority` to each active transit and sort descending.

    Args:
        active_transits: list from period_impact (transiting_body,
            natal_body, aspect, orb, days_to_exact, ...).
        natal_chart: chart dict with `bodies` (for natal sign lookup).
        transit_chart: chart dict with `bodies` (for transit sign lookup)
            and `aspects` (for grid weights).

    Returns:
        New list of dicts, each with an added `priority` int, sorted by
        priority descending then orb ascending. Moon transits are kept but
        score naturally low; callers may filter.
    """
    natal_signs = {b["name"]: b.get("sign_name", "") for b in natal_chart.get("bodies", [])}
    transit_signs = {b["name"]: b.get("sign_name", "") for b in transit_chart.get("bodies", [])}
    grid_weights = compute_planetary_grid_weights(transit_chart)

    scored = []
    for t in active_transits:
        tb = t.get("transiting_body", "")
        nb = t.get("natal_body", "")
        aspect = (t.get("aspect") or "").lower()
        if aspect not in MAJOR_ASPECTS:
            continue
        orb = float(t.get("orb", 999))
        days = int(t.get("days_to_exact", 0))
        priority = aspect_priority(
            tb, transit_signs.get(tb, ""),
            nb, natal_signs.get(nb, ""),
            orb, days, aspect,
            grid_weight=grid_weights.get(tb, 1.0),
        )
        item = dict(t)
        item["priority"] = priority
        scored.append(item)

    scored.sort(key=lambda x: (-x.get("priority", 0), x.get("orb", 999)))
    return scored


def planet_relative_values(
    active_transits: list[dict],
    natal_chart: dict,
    transit_chart: dict,
) -> list[dict]:
    """Aggregate per-transiting-planet relative value.

    For each transiting body, sum the priority of its active transits and
    count them. Returns a list sorted by total priority descending:

        [{"body": "Saturn", "total_priority": 210, "transit_count": 3,
          "top_aspect": "conjunction", "top_natal_body": "Sun"}, ...]
    """
    scored = score_active_transits(active_transits, natal_chart, transit_chart)
    agg: dict[str, dict] = {}
    for t in scored:
        body = t.get("transiting_body", "")
        if not body:
            continue
        entry = agg.setdefault(body, {
            "body": body,
            "total_priority": 0,
            "transit_count": 0,
            "top_priority": 0,
            "top_aspect": "",
            "top_natal_body": "",
        })
        entry["total_priority"] += t.get("priority", 0)
        entry["transit_count"] += 1
        if t.get("priority", 0) > entry["top_priority"]:
            entry["top_priority"] = t.get("priority", 0)
            entry["top_aspect"] = t.get("aspect", "")
            entry["top_natal_body"] = t.get("natal_body", "")
    return sorted(agg.values(), key=lambda x: -x["total_priority"])
