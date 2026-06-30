"""
YAML asset loader for astrology-tool central corpus.

Loads YAML assets from src/astro_data/assets/ with per-process caching.
Reloads only when file mtime changes.
"""
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml

# Asset directory is relative to this module's location
ASSETS_DIR = Path(__file__).parent / "assets"

# Canonical asset names
ASSET_NAMES = frozenset([
    "bodies",
    "signs",
    "aspects",
    "dignities",
    "house_systems",
    "moon_phases",
    "planetary_hours",
    "scoring",
])

# Cache storage: {asset_name: (data, mtime)}
_cache: Dict[str, tuple] = {}


def _load_yaml_file(path: Path) -> Dict[str, Any]:
    """Load a YAML file using safe_load only."""
    content = path.read_text(encoding="utf-8")
    return yaml.safe_load(content)


def yaml_loader(name: str) -> Dict[str, Any]:
    """
    Load a YAML asset by name.
    
    Args:
        name: One of ASSET_NAMES (bodies, signs, aspects, dignities,
              house_systems, moon_phases, planetary_hours, scoring)
    
    Returns:
        Parsed YAML data as a dictionary.
    
    Raises:
        ValueError: If name is not in ASSET_NAMES.
        FileNotFoundError: If the asset file doesn't exist.
        yaml.YAMLError: If the YAML is malformed.
    """
    if name not in ASSET_NAMES:
        valid = ", ".join(sorted(ASSET_NAMES))
        raise ValueError(f"Unknown asset '{name}'. Valid names: {valid}")
    
    path = ASSETS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Asset file not found: {path}")
    
    current_mtime = path.stat().st_mtime
    
    # Check cache
    if name in _cache:
        cached_data, cached_mtime = _cache[name]
        if current_mtime == cached_mtime:
            return cached_data
    
    # Load fresh
    data = _load_yaml_file(path)
    _cache[name] = (data, current_mtime)
    return data


def clear_cache() -> None:
    """Clear the asset cache. Forces reload on next yaml_loader() call."""
    _cache.clear()


def get_cache_info() -> Dict[str, Any]:
    """Return cache diagnostics for debugging."""
    return {
        name: {"cached": True, "mtime": mtime}
        for name, (_, mtime) in _cache.items()
    }
