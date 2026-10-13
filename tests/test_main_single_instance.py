"""Tests for main()'s single-instance check.

Importing `glucoglance.main` pulls in GTK and AppIndicator, which only
needs their typelibs (installed from apt, also in CI), not a display
server. Everything that would touch the display - the dialog, the tray,
the window icon - is replaced with a recording fake.
"""

import pytest

from glucoglance import main as app_main


@pytest.fixture
def calls(monkeypatch):
    """Record what main() does instead of doing it."""
    recorded = []

    class FakeApplication:
        def __init__(self):
            recorded.append("Application()")

        def start(self):
            recorded.append("start")

    monkeypatch.setattr(app_main, "Application", FakeApplication)
    monkeypatch.setattr(app_main, "show_already_running", lambda: recorded.append("dialog"))
    monkeypatch.setattr(app_main.Gtk.Window, "set_default_icon_from_file", lambda path: None)
    return recorded


def test_second_copy_shows_the_notice_and_never_starts(calls, monkeypatch):
    monkeypatch.setattr(app_main, "acquire_instance_lock", lambda: None)
    app_main.main()
    assert calls == ["dialog"]


def test_first_copy_starts_without_the_notice(calls, monkeypatch):
    monkeypatch.setattr(app_main, "acquire_instance_lock", lambda: object())
    app_main.main()
    assert calls == ["Application()", "start"]


def test_main_takes_the_real_lock(calls, tmp_path, monkeypatch):
    # End to end through instance_lock, with the lock file in a temp
    # runtime dir: a copy already holding it makes main() bow out.
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    held = app_main.acquire_instance_lock()
    assert held is not None
    app_main.main()
    assert calls == ["dialog"]

    held.release()
    calls.clear()
    app_main.main()
    assert calls == ["Application()", "start"]
