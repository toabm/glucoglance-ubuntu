"""Locates the app's bundled icon file.

The icon ships inside the package (`assets/icon.png`) rather than as a
loose file in the repo, so it's found correctly whether the app is
running from an editable dev install or a real `pip install .` copy in
site-packages - see pyproject.toml's `[tool.setuptools.package-data]` for
the build-time side of that.
"""

from importlib.resources import files
from pathlib import Path


def app_icon_path() -> Path:
    """Absolute path to the app's icon PNG, suitable for a .desktop file's
    Icon= key or any other place that needs a real file path."""
    return Path(str(files("glucose_widget") / "assets" / "icon.png"))
