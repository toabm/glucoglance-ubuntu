"""Tests for config.autostart's install/remove of the XDG autostart entry.

Points the module's autostart directory at a temp path instead of the
real ~/.config/autostart, so this never touches the actual desktop
session's autostart list.
"""

from glucoglance.config import autostart


def test_enabling_creates_desktop_file(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "_AUTOSTART_DIR", tmp_path)
    autostart.set_autostart_enabled(True)
    assert autostart.autostart_desktop_path().exists()


def test_desktop_file_points_at_the_running_interpreter(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "_AUTOSTART_DIR", tmp_path)
    autostart.set_autostart_enabled(True)
    content = autostart.autostart_desktop_path().read_text()
    assert "Exec=" in content
    assert "glucoglance" in content


def test_disabling_removes_desktop_file(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "_AUTOSTART_DIR", tmp_path)
    autostart.set_autostart_enabled(True)
    autostart.set_autostart_enabled(False)
    assert not autostart.autostart_desktop_path().exists()


def test_disabling_when_never_enabled_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "_AUTOSTART_DIR", tmp_path)
    autostart.set_autostart_enabled(False)
    assert not autostart.autostart_desktop_path().exists()


def test_exec_line_has_no_shell_wrapper_or_quoting(tmp_path, monkeypatch):
    # Regression test: an earlier version wrapped Exec= in `sh -c "..."`
    # to run a delay first. That passed desktop-file-validate and GLib's
    # shell_parse_argv, but both systemd-xdg-autostart-generator and
    # gnome-session-binary itself rejected it at actual login (confirmed
    # live via journalctl). The delay is applied via X-GNOME-Autostart-Delay
    # instead, so Exec= must stay a single unquoted path with no shell
    # metacharacters at all.
    monkeypatch.setattr(autostart, "_AUTOSTART_DIR", tmp_path)
    autostart.set_autostart_enabled(True)
    content = autostart.autostart_desktop_path().read_text()
    exec_line = next(line for line in content.splitlines() if line.startswith("Exec="))
    assert exec_line == exec_line.strip()
    for char in ("\"", "'", "&", ";", "|", "`", "$"):
        assert char not in exec_line
    assert "glucoglance" in exec_line


def test_autostart_delay_key_is_present(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "_AUTOSTART_DIR", tmp_path)
    autostart.set_autostart_enabled(True)
    content = autostart.autostart_desktop_path().read_text()
    assert f"X-GNOME-Autostart-Delay={autostart._STARTUP_DELAY_SECONDS}" in content
