"""Renders glucose reading text as a small bitmap, for use as a tray icon.

Why this exists: GNOME Shell's AppIndicator extension is supposed to show
arbitrary text next to an indicator's icon (its "label" feature), but on at
least some Shell/extension version combinations that label never renders
even though the underlying data is published correctly - a Shell-side
rendering bug, not something we can fix from the app. Drawing the reading
into the icon itself sidesteps that entirely: icon rendering is the one
thing we've confirmed reliably works, so the number becomes the icon.

The rendered image is intentionally not square - AppIndicator/GNOME Shell
icons scale to the panel's row height while keeping their own aspect ratio,
so a short wide image (e.g. "118 →") renders fine, similar to how
built-in indicators like the keyboard layout switcher show short text.
"""

import cairo
import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo  # noqa: E402 (must follow gi.require_version)

# Rendered at a fixed height taller than a typical panel row and let the
# Shell scale it down - crisper than rendering at the exact target size.
# The Shell always scales the whole bitmap to the panel's row height, so
# shrinking the font (relative to this fixed height) is what actually makes
# the icon look smaller on screen - shrinking _RENDER_HEIGHT itself would
# just get scaled back up to the same on-screen size.
_RENDER_HEIGHT = 64
_FONT_DESCRIPTION = "Sans Bold 36"
DEFAULT_TEXT_COLOR_RGBA = (1, 1, 1, 1)  # white, matches this desktop's dark top bar


def render_text_icon(text: str, color: tuple[float, float, float, float] = DEFAULT_TEXT_COLOR_RGBA) -> cairo.ImageSurface:
    """Draw `text` centered on a transparent background in `color`, sized
    to fit it with a small margin. Returns a Cairo surface ready to be
    written to PNG."""
    layout = _build_layout(text)
    _ink, logical = layout.get_pixel_extents()
    margin = _RENDER_HEIGHT // 8
    width = max(logical.width + margin * 2, 1)
    height = _RENDER_HEIGHT

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    ctx.set_source_rgba(*color)
    ctx.move_to((width - logical.width) / 2 - logical.x, (height - logical.height) / 2 - logical.y)
    PangoCairo.update_layout(ctx, layout)
    PangoCairo.show_layout(ctx, layout)
    return surface


def render_text_icon_png_bytes(
    text: str, color: tuple[float, float, float, float] = DEFAULT_TEXT_COLOR_RGBA
) -> bytes:
    """Same as `render_text_icon`, but returns encoded PNG bytes - handy for
    tests, which don't need a real file on disk."""
    import io

    surface = render_text_icon(text, color)
    buf = io.BytesIO()
    surface.write_to_png(buf)
    return buf.getvalue()


def parse_hex_color(hex_color: str) -> tuple[float, float, float, float]:
    """Parse a '#rrggbb' string (as stored in settings.toml) into an RGBA
    float tuple for Cairo. Alpha is always fully opaque."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16) / 255
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255
    return (r, g, b, 1.0)


def _build_layout(text: str) -> Pango.Layout:
    """Build a Pango layout for `text` in our fixed icon font, using a
    throwaway surface just to get a Cairo context to lay text out on."""
    scratch = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    ctx = cairo.Context(scratch)
    layout = PangoCairo.create_layout(ctx)
    layout.set_font_description(Pango.FontDescription(_FONT_DESCRIPTION))
    layout.set_text(text, -1)
    return layout
