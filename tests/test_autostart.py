"""Tests for config.autostart's install/remove of the XDG autostart entry.

Points the module's autostart directory at a temp path instead of the
real ~/.config/autostart, so this never touches the actual desktop
session's autostart list.
"""

from glucose_widget.config import autostart


def test_enabling_creates_desktop_file(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "_AUTOSTART_DIR", tmp_path)
    autostart.set_autostart_enabled(True)
    assert autostart.autostart_desktop_path().exists()


def test_desktop_file_points_at_the_running_interpreter(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "_AUTOSTART_DIR", tmp_path)
    autostart.set_autostart_enabled(True)
    content = autostart.autostart_desktop_path().read_text()
    assert "Exec=" in content
    assert "glucose-widget" in content


def test_disabling_removes_desktop_file(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "_AUTOSTART_DIR", tmp_path)
    autostart.set_autostart_enabled(True)
    autostart.set_autostart_enabled(False)
    assert not autostart.autostart_desktop_path().exists()


def test_disabling_when_never_enabled_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "_AUTOSTART_DIR", tmp_path)
    autostart.set_autostart_enabled(False)
    assert not autostart.autostart_desktop_path().exists()


def test_exec_line_always_delays_before_launching(tmp_path, monkeypatch):
    # Only the autostart path should ever be delayed - running from a
    # terminal or the Applications-menu icon uses a plain Exec= with no
    # shell wrapper, since those go through a different .desktop file
    # entirely (or no .desktop file at all).
    monkeypatch.setattr(autostart, "_AUTOSTART_DIR", tmp_path)
    autostart.set_autostart_enabled(True)
    content = autostart.autostart_desktop_path().read_text()
    assert f"sleep {autostart._STARTUP_DELAY_SECONDS}" in content
    assert "glucose-widget" in content
