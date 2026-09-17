"""Tests for icon_renderer's pure text-to-bitmap rendering.

Cairo/Pango rendering to an in-memory surface needs no display server, so
this is safe to unit-test unlike the actual tray/GTK integration.
"""

from glucoglance.ui.icon_renderer import (
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
