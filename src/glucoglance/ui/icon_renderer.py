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
The catch is that the icon's horizontal slot is the bitmap's native width,
so the bitmap has to be rendered at about panel height (see _RENDER_HEIGHT).

To draw attention to an out-of-range reading without any sound or popup,
`filled` draws the text on a solid rounded "pill" of the range color -
much easier to catch in peripheral vision than colored text alone.
"""

import math

import cairo
import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo  # noqa: E402 (must follow gi.require_version)

# Rendered at (roughly) the panel's actual row height, not larger. For wide
# images (width >= 1.5x height) the ubuntu-appindicators extension sizes the
# icon's slot to the bitmap's *native* pixel width, then scales the image
# down to fit the row height inside that slot - so any extra render height
# turns into empty space on both sides of the text. (At 64px tall this was
# ~37px of blank space per side on a 32px panel.) The font size is what sets
# how big the text looks relative to the row; keep it at ~56% of the height.
_RENDER_HEIGHT = 32
_FONT_DESCRIPTION = "Sans Bold 18"
_PILL_CORNER_RADIUS = 6
DEFAULT_TEXT_COLOR_RGBA = (1, 1, 1, 1)  # white, matches this desktop's dark top bar
_DARK_TEXT_COLOR_RGBA = (0.1, 0.1, 0.1, 1)

Rgba = tuple[float, float, float, float]


def render_text_icon(
    text: str,
    color: Rgba = DEFAULT_TEXT_COLOR_RGBA,
    *,
    filled: bool = False,
    min_width: int = 0,
) -> cairo.ImageSurface:
    """Draw `text` centered in `color`, sized to fit it with a small margin.
    Returns a Cairo surface ready to be written to PNG.

    With `filled`, `color` becomes a rounded background filling the whole
    image and the text is drawn on top of it in black or white, whichever
    contrasts better (see `contrasting_text_color`).

    `min_width` pads the image (transparently, text still centered) to at
    least that many pixels wide - see TrayDisplay._error_icon_spec for why.
    """
    layout = _build_layout(text)
    _ink, logical = layout.get_pixel_extents()
    margin = _RENDER_HEIGHT // 8
    width = max(logical.width + margin * 2, min_width, 1)
    height = _RENDER_HEIGHT

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    if filled:
        ctx.set_source_rgba(*color)
        _rounded_rectangle(ctx, width, height, _PILL_CORNER_RADIUS)
        ctx.fill()
        ctx.set_source_rgba(*contrasting_text_color(color))
    else:
        ctx.set_source_rgba(*color)
    ctx.move_to((width - logical.width) / 2 - logical.x, (height - logical.height) / 2 - logical.y)
    PangoCairo.update_layout(ctx, layout)
    PangoCairo.show_layout(ctx, layout)
    return surface


def render_text_icon_png_bytes(
    text: str,
    color: Rgba = DEFAULT_TEXT_COLOR_RGBA,
    *,
    filled: bool = False,
    min_width: int = 0,
) -> bytes:
    """Same as `render_text_icon`, but returns encoded PNG bytes - handy for
    tests, which don't need a real file on disk."""
    import io

    surface = render_text_icon(text, color, filled=filled, min_width=min_width)
    buf = io.BytesIO()
    surface.write_to_png(buf)
    return buf.getvalue()


def parse_hex_color(hex_color: str) -> Rgba:
    """Parse a '#rrggbb' string (as stored in settings.toml) into an RGBA
    float tuple for Cairo. Alpha is always fully opaque."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16) / 255
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255
    return (r, g, b, 1.0)


def contrasting_text_color(background: Rgba) -> Rgba:
    """Near-black or white, whichever reads better on `background`, so a
    user-chosen range color never leaves the text unreadable. Uses the WCAG relative-luminance formula; 0.179 is where black and white
    text have equal contrast against the background."""
    r, g, b, _a = background
    luminance = 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)
    return _DARK_TEXT_COLOR_RGBA if luminance > 0.179 else DEFAULT_TEXT_COLOR_RGBA


def _linearize(channel: float) -> float:
    """Undo sRGB gamma for one 0..1 color channel (part of the WCAG formula)."""
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _rounded_rectangle(ctx: cairo.Context, width: float, height: float, radius: float) -> None:
    """Add a rounded rectangle covering the whole (width x height) surface
    to `ctx`'s current path."""
    ctx.new_sub_path()
    ctx.arc(width - radius, radius, radius, -math.pi / 2, 0)
    ctx.arc(width - radius, height - radius, radius, 0, math.pi / 2)
    ctx.arc(radius, height - radius, radius, math.pi / 2, math.pi)
    ctx.arc(radius, radius, radius, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def _build_layout(text: str) -> Pango.Layout:
    """Build a Pango layout for `text` in our fixed icon font, using a
    throwaway surface just to get a Cairo context to lay text out on."""
    scratch = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    ctx = cairo.Context(scratch)
    layout = PangoCairo.create_layout(ctx)
    layout.set_font_description(Pango.FontDescription(_FONT_DESCRIPTION))
    layout.set_text(text, -1)
    return layout
