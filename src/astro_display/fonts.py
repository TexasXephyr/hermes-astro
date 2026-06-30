"""Font discovery for astro_display renderers."""
from pathlib import Path

_FONT_DIR = Path.home() / ".local" / "share" / "fonts"


def find_font(name: str = "regular") -> str:
    """Return absolute path to a LiberZodiac font file.

    Args:
        name: Font variant, one of "regular", "bold", "italic".

    Returns:
        Absolute path to the requested font file.

    Raises:
        FileNotFoundError: If the font file does not exist.
        ValueError: If ``name`` is not a supported variant.
    """
    name = name.lower()
    if name not in ("regular", "bold", "italic"):
        raise ValueError(f"Unknown font variant '{name}'. Use regular/bold/italic.")
    suffix = name.capitalize()
    path = _FONT_DIR / f"LiberZodiac-{suffix}.ttf"
    if not path.exists():
        raise FileNotFoundError(f"Font not found: {path}")
    return str(path.resolve())
