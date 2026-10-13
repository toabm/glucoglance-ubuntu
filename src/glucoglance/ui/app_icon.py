"""Locates the app's bundled icon files.

The icons ship inside the package (`assets/`) rather than as loose files
in the repo, so they are found correctly whether the app is
running from an editable dev install or a real `pip install .` copy in
site-packages - see pyproject.toml's `[tool.setuptools.package-data]` for
the build-time side of that.
"""

from importlib.resources import files
from pathlib import Path


def app_icon_path() -> Path:
    """Absolute path to the app's icon PNG, suitable for a .desktop file's
    Icon= key or any other place that needs a real file path."""
    return Path(str(files("glucoglance") / "assets" / "icon.png"))


def tray_icon_path(*, error: bool = False) -> Path:
    """Absolute path to the small eye/gauge/drop icon (SVG) - the tray's
    own mark, also used as the About dialog's image. `error` selects the
    red-eye variant shown when there's no current reading."""
    name = "tray-icon-error.svg" if error else "tray-icon.svg"
    return Path(str(files("glucoglance") / "assets" / name))
