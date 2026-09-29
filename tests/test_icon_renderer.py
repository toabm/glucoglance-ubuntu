"""Tests for icon_renderer's pure text-to-bitmap rendering.

Cairo/Pango rendering to an in-memory surface needs no display server, so
this is safe to unit-test unlike the actual tray/GTK integration.
"""

from glucoglance.ui.icon_renderer import (
    contrasting_text_color,
    parse_hex_color,
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
