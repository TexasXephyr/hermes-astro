"""astro_gui.renderers package.

The wheel renderer now lives in the centralized astro_display package.
This module re-exports it so legacy import paths
(``astro_gui.renderers.WheelRenderer``) keep working without silently
picking up the old, superseded implementation.
"""
from astro_display import WheelRenderer

__all__ = ["WheelRenderer"]
