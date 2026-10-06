"""Tests for ui.app_icon's bundled-icon path resolution."""

from glucoglance.ui.app_icon import app_icon_path, tray_icon_path


def test_icon_path_points_to_an_existing_png():
    path = app_icon_path()
    assert path.exists()
    assert path.suffix == ".png"


def test_tray_icon_paths_point_to_existing_distinct_svgs():
    normal = tray_icon_path()
    error = tray_icon_path(error=True)
    assert normal.exists() and error.exists()
    assert normal.suffix == error.suffix == ".svg"
    assert normal != error
