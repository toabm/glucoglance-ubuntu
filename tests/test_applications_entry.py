"""Tests for config.applications_entry's install/remove of the per-user
Applications-menu entry.

Points the module's applications directory at a temp path, and
XDG_DATA_DIRS at temp paths, so this never touches the real desktop
session's app list or depends on what's installed system-wide.
"""

from glucoglance.config import applications_entry
from glucoglance.config.autostart import app_exec_path
from glucoglance.ui.app_icon import app_icon_path


def _desktop_keys(content: str) -> dict[str, str]:
    """Parse the `key=value` lines of a single-group .desktop file."""
    return dict(line.split("=", 1) for line in content.splitlines() if "=" in line)


def test_installing_creates_desktop_file(tmp_path, monkeypatch):
    monkeypatch.setattr(applications_entry, "_APPLICATIONS_DIR", tmp_path / "applications")
    applications_entry.set_applications_entry_installed(True)
    assert applications_entry.applications_entry_path().exists()
    assert applications_entry.is_applications_entry_installed()


def test_desktop_file_launches_the_running_install_with_the_launcher_icon(tmp_path, monkeypatch):
    monkeypatch.setattr(applications_entry, "_APPLICATIONS_DIR", tmp_path)
    applications_entry.set_applications_entry_installed(True)
    content = applications_entry.applications_entry_path().read_text()
    assert content.startswith("[Desktop Entry]\n")
    keys = _desktop_keys(content)
    assert keys["Type"] == "Application"
    assert keys["Name"] == "GlucoGlance"
    assert keys["Exec"] == str(app_exec_path())
    assert keys["Icon"] == str(app_icon_path())
    assert keys["Terminal"] == "false"
    # Unlike the autostart entry, nothing GNOME-autostart-specific.
    assert not any(key.startswith("X-GNOME-Autostart") for key in keys)


def test_removing_deletes_desktop_file(tmp_path, monkeypatch):
    monkeypatch.setattr(applications_entry, "_APPLICATIONS_DIR", tmp_path)
    applications_entry.set_applications_entry_installed(True)
    applications_entry.set_applications_entry_installed(False)
    assert not applications_entry.is_applications_entry_installed()


def test_removing_when_never_installed_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(applications_entry, "_APPLICATIONS_DIR", tmp_path)
    applications_entry.set_applications_entry_installed(False)
    assert not applications_entry.is_applications_entry_installed()


def test_refresh_rewrites_an_outdated_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(applications_entry, "_APPLICATIONS_DIR", tmp_path)
    path = applications_entry.applications_entry_path()
    path.write_text("[Desktop Entry]\nExec=/old/venv/bin/glucoglance\n")
    applications_entry.refresh_applications_entry()
    assert _desktop_keys(path.read_text())["Exec"] == str(app_exec_path())


def test_refresh_does_not_install_a_missing_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(applications_entry, "_APPLICATIONS_DIR", tmp_path)
    applications_entry.refresh_applications_entry()
    assert not applications_entry.is_applications_entry_installed()


def test_system_entry_found_in_any_xdg_data_dir(tmp_path, monkeypatch):
    empty_dir, deb_dir = tmp_path / "empty", tmp_path / "usr-share"
    (deb_dir / "applications").mkdir(parents=True)
    (deb_dir / "applications" / "glucoglance.desktop").write_text("[Desktop Entry]\n")
    monkeypatch.setenv("XDG_DATA_DIRS", f"{empty_dir}::{deb_dir}")
    assert applications_entry.system_entry_installed()


def test_no_system_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path))
    assert not applications_entry.system_entry_installed()


def test_system_entry_falls_back_to_default_data_dirs(tmp_path, monkeypatch):
    deb_dir = tmp_path / "usr-share"
    (deb_dir / "applications").mkdir(parents=True)
    (deb_dir / "applications" / "glucoglance.desktop").write_text("[Desktop Entry]\n")
    monkeypatch.delenv("XDG_DATA_DIRS", raising=False)
    monkeypatch.setattr(applications_entry, "_DEFAULT_XDG_DATA_DIRS", str(deb_dir))
    assert applications_entry.system_entry_installed()


def test_tray_checkbox_installs_and_removes_the_entry(tmp_path, monkeypatch):
    # The tray's toggle handler, without building the (display-bound)
    # tray itself: importing it only needs the GTK/AppIndicator typelibs.
    from glucoglance.ui import tray

    class FakeCheckItem:
        def __init__(self, active):
            self._active = active

        def get_active(self):
            return self._active

    monkeypatch.setattr(applications_entry, "_APPLICATIONS_DIR", tmp_path)
    tray.TrayDisplay._on_applications_entry_toggled(FakeCheckItem(True))
    assert applications_entry.is_applications_entry_installed()
    tray.TrayDisplay._on_applications_entry_toggled(FakeCheckItem(False))
    assert not applications_entry.is_applications_entry_installed()
