"""Tests for ui.app_icon's bundled-icon path resolution."""

from glucoglance.ui.app_icon import app_icon_path


def test_icon_path_points_to_an_existing_png():
    path = app_icon_path()
    assert path.exists()
    assert path.suffix == ".png"
