"""Tests for about_dialog's version lookup (pure, no display server needed)."""

import tomllib
from pathlib import Path

from glucoglance.ui.about_dialog import _installed_version

_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_installed_version_matches_pyproject():
    # Read the expected version from pyproject.toml rather than hardcoding it,
    # so a version bump doesn't also require editing this test.
    with open(_PYPROJECT, "rb") as f:
        expected = tomllib.load(f)["project"]["version"]
    assert _installed_version() == expected
