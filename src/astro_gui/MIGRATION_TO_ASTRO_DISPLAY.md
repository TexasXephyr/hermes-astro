# Migration to astro_display

The `astro_gui/renderers/wheel_renderer.py` wheel renderer has been ported
to the centralized `astro_display` package as part of Phase 7 centralization.

## New location

```python
from astro_display import WheelRenderer
# or explicitly
from astro_display.svg.wheel import WheelRenderer
```

## What changed

- Symbol tables (`PLANET_GLYPHS`, `SIGN_GLYPHS`) are now loaded from
  `astro_text.symbols` (`symbol_for_body`, `symbol_for_sign`), which draws
  from the central `astro_data` YAML corpus.
- Font discovery is handled by `astro_display.fonts.find_font()`.
- Aspect colors are read from `astro_data.loaders.yaml_loader("aspects")`
  with case-insensitive aspect-name matching against both `aspect_name` and
  `aspect` keys.
- The public API, geometry, layers, and dark-theme color scheme are
  otherwise identical to the original `astro_gui` implementation.

## Public methods

- `WheelRenderer.render_natal(chart_data, scale=1.0)`
- `WheelRenderer.render_transit(natal_data, transit_data, width=600, height=600, scale=1.0)`
- `WheelRenderer.render_synastry(chart_a_data, chart_b_data, cross_aspects, width=600, height=600, scale=1.0)`

## Migration example

```python
# Old
from astro_gui.renderers.wheel_renderer import WheelRenderer

# New
from astro_display import WheelRenderer

renderer = WheelRenderer()
svg = renderer.render_natal(chart_data)
```

## File map

| Original | New |
| --- | --- |
| `astro_gui/renderers/wheel_renderer.py` | `astro_display/svg/wheel.py` |
| hard-coded glyph dicts | `astro_text.symbols` + `astro_data.loaders` |
| hard-coded `_FONT_PATH` | `astro_display/fonts.py` |

No changes were made to the existing `astro_gui` package; it remains usable
while consumers migrate.
