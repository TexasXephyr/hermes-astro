"""
Body set selectors for astrology-tool.

Provides BodySet class for validating and managing sets of celestial bodies,
plus predefined DEFAULT_POINTS and ALL_POINTS constants.
"""
from typing import Iterable, List, Set

from .loaders import yaml_loader


_ALIASES: dict[str, str] = {}


def _load_bodies() -> dict:
    """Load bodies.yaml and return as dict."""
    return yaml_loader("bodies")


def _build_aliases(bodies: dict) -> dict[str, str]:
    """Build a map from lowercase alias to canonical name."""
    aliases: dict[str, str] = {}
    for canonical, data in bodies.items():
        aliases[canonical.lower()] = canonical
        for alias in data.get("aliases", []):
            aliases[alias.lower()] = canonical
    return aliases


def _get_valid_names() -> Set[str]:
    """Return set of all valid body names from bodies.yaml."""
    bodies = _load_bodies()
    return set(bodies.keys())


# Predefined point selectors
# These are computed at import time from the YAML corpus
DEFAULT_POINTS: List[str] = []
ALL_POINTS: List[str] = []


def _init_point_selectors():
    """Initialize DEFAULT_POINTS and ALL_POINTS from bodies.yaml."""
    global DEFAULT_POINTS, ALL_POINTS, _ALIASES
    bodies = _load_bodies()

    # Default: all bodies with default_include=true
    DEFAULT_POINTS.extend([
        name for name, data in bodies.items()
        if data.get("default_include", False)
    ])

    # All: every body in the corpus
    ALL_POINTS.extend(sorted(bodies.keys()))

    _ALIASES = _build_aliases(bodies)

_init_point_selectors()


class BodySet:
    """
    A validated set of celestial body names.

    Validates all names against bodies.yaml and provides
    set-like operations with preserved iteration order.

    Args:
        names: Iterable of body names (case-insensitive).
               Use DEFAULT_POINTS or ALL_POINTS for presets.

    Raises:
        ValueError: If any name is not in bodies.yaml, or if empty.

    Example:
        >>> bs = BodySet(DEFAULT_POINTS)
        >>> "Sun" in bs
        True
        >>> list(bs)
        ['Sun', 'Moon', 'Mercury', ...]
    """

    def __init__(self, names: Iterable[str]):
        self._names: List[str] = []
        self._valid_names = _get_valid_names()
        self._aliases = _ALIASES

        name_list = list(names)
        if not name_list:
            valid = ", ".join(sorted(self._valid_names))
            raise ValueError(f"BodySet cannot be empty. See valid names: {valid}")

        for name in name_list:
            # Case-insensitive matching
            matched = self._find_match(name)
            if matched is None:
                valid = ", ".join(sorted(self._valid_names))
                raise ValueError(
                    f"Unknown body '{name}'. See valid names: {valid}"
                )
            self._names.append(matched)

    def _find_match(self, name: str) -> str | None:
        """Find case-insensitive match, return canonical name or None."""
        normalized = name.lower()
        if normalized in self._aliases:
            return self._aliases[normalized]
        for valid in self._valid_names:
            if valid.lower() == normalized:
                return valid
        return None
    
    def __iter__(self):
        return iter(self._names)
    
    def __contains__(self, name: str) -> bool:
        return self._find_match(name) in self._names
    
    def __len__(self) -> int:
        return len(self._names)
    
    def __repr__(self) -> str:
        return f"BodySet({self._names!r})"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, BodySet):
            return False
        return self._names == other._names
    
    def to_list(self) -> List[str]:
        """Return bodies as a list (preserves order)."""
        return self._names.copy()
    
    def to_set(self) -> Set[str]:
        """Return bodies as a set (unordered)."""
        return set(self._names)
