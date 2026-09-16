"""Tests for settings load/save. Uses $XDG_CONFIG_HOME to keep this off the
real filesystem location.
"""

from glucose_widget.config.settings import Settings, config_path, load_settings, save_settings
from glucose_widget.domain.units import GlucoseUnit


def test_defaults_when_no_file_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    settings = load_settings()
    assert settings == Settings()


def test_autostart_is_enabled_by_default():
    assert Settings().autostart_enabled is True


def test_save_with_unset_optional_fields_does_not_raise(tmp_path, monkeypatch):
    # Regression test: account_email/base_host default to None, and TOML has
    # no null - saving used to crash with "Object of type 'NoneType' is not
    # TOML serializable" before to_toml_dict() started omitting None fields.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_settings(Settings())
    assert config_path().exists()


def test_round_trip_preserves_values(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    original = Settings(
        interval_seconds=30,
        unit=GlucoseUnit.MMOL,
        frontend="tray",
        account_email="user@example.com",
        base_host="api-eu.libreview.io",
        low_threshold_mgdl=70,
        high_threshold_mgdl=160,
        color_low="#FF0000",
        color_normal="#00FF00",
        color_high="#0000FF",
        autostart_enabled=False,
    )
    save_settings(original)
    loaded = load_settings()
    assert loaded == original


def test_round_trip_with_unset_optional_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_settings(Settings())
    loaded = load_settings()
    assert loaded == Settings()
