"""User-facing settings, stored as TOML at an XDG-compliant config path.

Only non-secret configuration lives here (polling interval, display unit,
which UI frontend to use, the account email, a cached region host to skip
LibreLinkUp's redirect round trip, the glucose-range thresholds/colors the
tray icon uses, and whether to start at login). The account password is
never written to this file - see `config.credentials` for that.
"""

import os
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

import tomli_w

from glucoglance.domain.range import DEFAULT_HIGH_THRESHOLD_MGDL, DEFAULT_LOW_THRESHOLD_MGDL
from glucoglance.domain.units import GlucoseUnit

_APP_DIR_NAME = "glucoglance"
_CONFIG_FILE_NAME = "config.toml"

# Defaults for the tray icon's range colors, as '#rrggbb' hex - the format
# stored in config.toml and understood by ui.icon_renderer.parse_hex_color.
_DEFAULT_COLOR_LOW = "#ED4343"
_DEFAULT_COLOR_NORMAL = "#4DCC66"
_DEFAULT_COLOR_HIGH = "#F5D334"


@dataclass
class Settings:
    """The full set of user-configurable, non-secret settings."""

    interval_seconds: int = 60
    unit: GlucoseUnit = GlucoseUnit.MGDL
    frontend: str = "tray"
    account_email: str | None = None
    base_host: str | None = None
    low_threshold_mgdl: int = DEFAULT_LOW_THRESHOLD_MGDL
    high_threshold_mgdl: int = DEFAULT_HIGH_THRESHOLD_MGDL
    color_low: str = _DEFAULT_COLOR_LOW
    color_normal: str = _DEFAULT_COLOR_NORMAL
    color_high: str = _DEFAULT_COLOR_HIGH
    autostart_enabled: bool = True

    def to_toml_dict(self) -> dict:
        """Convert to a plain dict of TOML-serializable types.

        TOML has no `null`: fields that are still unset (`account_email`,
        `base_host` before first login) are omitted entirely rather than
        written as None, which `tomli_w` would reject.
        """
        data = asdict(self)
        data["unit"] = self.unit.value
        return {key: value for key, value in data.items() if value is not None}

    @classmethod
    def from_toml_dict(cls, data: dict) -> "Settings":
        """Build a Settings from a dict loaded from TOML, tolerating missing keys."""
        defaults = cls()
        return cls(
            interval_seconds=data.get("interval_seconds", defaults.interval_seconds),
            unit=GlucoseUnit(data.get("unit", defaults.unit.value)),
            frontend=data.get("frontend", defaults.frontend),
            account_email=data.get("account_email"),
            base_host=data.get("base_host"),
            low_threshold_mgdl=data.get("low_threshold_mgdl", defaults.low_threshold_mgdl),
            high_threshold_mgdl=data.get("high_threshold_mgdl", defaults.high_threshold_mgdl),
            color_low=data.get("color_low", defaults.color_low),
            color_normal=data.get("color_normal", defaults.color_normal),
            color_high=data.get("color_high", defaults.color_high),
            autostart_enabled=data.get("autostart_enabled", defaults.autostart_enabled),
        )


def config_dir() -> Path:
    """The directory settings live in, honoring $XDG_CONFIG_HOME if set."""
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg_config_home) if xdg_config_home else Path.home() / ".config"
    return base / _APP_DIR_NAME


def config_path() -> Path:
    """The full path to the settings TOML file."""
    return config_dir() / _CONFIG_FILE_NAME


def load_settings() -> Settings:
    """Load settings from disk, or return defaults if the file doesn't exist yet."""
    path = config_path()
    if not path.exists():
        return Settings()
    with path.open("rb") as f:
        data = tomllib.load(f)
    return Settings.from_toml_dict(data)


def save_settings(settings: Settings) -> None:
    """Write settings to disk, creating the config directory if needed."""
    config_dir().mkdir(parents=True, exist_ok=True)
    with config_path().open("wb") as f:
        tomli_w.dump(settings.to_toml_dict(), f)
