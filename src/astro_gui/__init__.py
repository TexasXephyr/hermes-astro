# astro_gui package
from .api_client import AstroApiClient, AstroApiError
from .main import AstroGuiApplication
from .window import MainWindow
from .widgets.person_selector import PersonSelector
from .widgets.status_bar import StatusBar

# NOTE: WheelRenderer now lives in the centralized astro_display package.
# The legacy astro_gui.renderers.wheel_renderer is deprecated and no longer
# exported here; consumers should use `from astro_display import WheelRenderer`.
from astro_display import WheelRenderer

__all__ = [
    "AstroApiClient",
    "AstroApiError",
    "AstroGuiApplication",
    "MainWindow",
    "PersonSelector",
    "StatusBar",
    "WheelRenderer",
]
