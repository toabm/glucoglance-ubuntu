"""Tests for icon_renderer's pure text-to-bitmap rendering.

Cairo/Pango rendering to an in-memory surface needs no display server, so
this is safe to unit-test unlike the actual tray/GTK integration.
"""

import cairo
import pytest
from gi.repository import GLib

from glucoglance.ui.icon_renderer import (
    contrasting_text_color,
    parse_hex_color,
    render_image_icon,
    render_text_icon,
    render_text_icon_png_bytes,
)

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_renders_valid_png_bytes():
    data = render_text_icon_png_bytes("118 →")
    assert data.startswith(_PNG_MAGIC)
    assert len(data) > 0


def test_wider_text_produces_wider_image():
    narrow = render_text_icon("1")
    wide = render_text_icon("118 →")
    assert wide.get_width() > narrow.get_width()


def test_height_is_consistent_regardless_of_text():
    a = render_text_icon("1")
    b = render_text_icon("118 →")
    assert a.get_height() == b.get_height()


def test_parse_hex_color():
    assert parse_hex_color("#FF0000") == (1.0, 0.0, 0.0, 1.0)
    assert parse_hex_color("00ff00") == (0.0, 1.0, 0.0, 1.0)
    assert parse_hex_color("#0000FF") == (0.0, 0.0, 1.0, 1.0)


def test_filled_icon_is_the_same_size_as_unfilled():
    plain = render_text_icon("190 ↑")
    filled = render_text_icon("190 ↑", filled=True)
    assert (filled.get_width(), filled.get_height()) == (plain.get_width(), plain.get_height())


def _alpha_at(surface, x: int, y: int) -> int:
    """Alpha byte of one pixel (Cairo's ARGB32 is native-endian BGRA on x86)."""
    stride = surface.get_stride()
    return surface.get_data()[y * stride + x * 4 + 3]


def test_filled_icon_has_an_opaque_background():
    unfilled = render_text_icon("190 ↑", (1, 0, 0, 1))
    filled = render_text_icon("190 ↑", (1, 0, 0, 1), filled=True)
    # A point near the left edge, vertically centered: inside the pill,
    # outside the text's glyphs.
    x, y = 2, filled.get_height() // 2
    assert _alpha_at(unfilled, x, y) == 0
    assert _alpha_at(filled, x, y) == 255


def test_contrasting_text_color_picks_dark_on_light_and_white_on_dark():
    assert contrasting_text_color(parse_hex_color("#F5D334")) == (0.1, 0.1, 0.1, 1)
    assert contrasting_text_color(parse_hex_color("#1A237E")) == (1, 1, 1, 1)


def test_min_width_pads_narrow_text_but_never_shrinks():
    narrow = render_text_icon("--")
    padded = render_text_icon("--", min_width=61)
    wide = render_text_icon("188 ↑", min_width=10)
    assert narrow.get_width() < 61
    assert padded.get_width() == 61
    assert wide.get_width() == render_text_icon("188 ↑").get_width()


def _write_square_png(path, size=16):
    """A fully opaque red square, standing in for an icon file."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)
    ctx.set_source_rgba(1, 0, 0, 1)
    ctx.paint()
    surface.write_to_png(str(path))


def test_image_icon_is_scaled_centered_and_padded(tmp_path):
    image = tmp_path / "icon.png"
    _write_square_png(image)
    surface = render_image_icon(image, min_width=61)
    assert surface.get_width() == 61
    assert surface.get_height() == render_text_icon("--").get_height()
    stride = surface.get_stride()
    data = surface.get_data()
    center = (surface.get_height() // 2) * stride + (surface.get_width() // 2) * 4
    # Cairo ARGB32 is native-endian BGRA on x86: drawn in its own (red) color.
    assert tuple(data[center:center + 4]) == (0, 0, 255, 255)
    assert _alpha_at(surface, 1, 1) == 0


def test_image_icon_raises_for_a_missing_file(tmp_path):
    with pytest.raises(GLib.Error):
        render_image_icon(tmp_path / "missing.svg")
