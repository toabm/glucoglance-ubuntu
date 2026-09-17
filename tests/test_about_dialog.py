"""Tests for about_dialog's version lookup (pure, no display server needed)."""

from glucoglance.ui.about_dialog import _installed_version


def test_installed_version_matches_pyproject():
    assert _installed_version() == "0.1.0"
