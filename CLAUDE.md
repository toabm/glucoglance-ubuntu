# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Naming history

This project was renamed from `glucose-widget-ubuntu` (Python package `glucose_widget`) to `glucoglance-ubuntu` (package `glucoglance`, display name "GlucoGlance") in September 2026. Git history, old commit messages, and old GitHub issue/PR references still say "glucose-widget" - that's expected, not a mistake to fix.

## Commands

Setup (requires system GTK/AppIndicator bindings, not just pip packages):

```bash
sudo apt install python3-venv python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
python3 -m venv --system-site-packages .venv   # --system-site-packages is required so python3-gi is reusable
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the app: `glucoglance` (or `python -m glucoglance.main`).

Run tests: `pytest` (whole suite) or `pytest tests/test_poller.py::test_name` (single test).

Lint: `ruff check .`. Tests + coverage (branch, not just line): `pytest --cov=glucoglance --cov-report=term-missing`.

IDE type stubs for `gi.repository` (GLib/Gtk/etc.) are a separate extras group, not part of `dev`: `pip install --no-deps PyGObject-stubs`. They must be installed with `--no-deps` - without it, pip can't tell the real PyGObject/pycairo are already provided by apt and tries to rebuild them from source, which fails without cairo/girepository dev headers. This is also why CI's `dev` install never includes them.

## Architecture

Data flow is strictly one-directional and each layer only depends on the one below it; only `main.py` (the `Application` class) knows about every layer at once:

```
client (LibreLinkUp HTTP) -> domain (pure data/logic) -> poller (EventBus) -> ui (Display) / config
```

- **`client/librelinkup.py`**: talks to the unofficial LibreLinkUp API (there is no official third-party API - this impersonates the official Android app's requests). Its only public method, `get_latest_reading()`, always returns a `GlucoseReading` or raises one of `AuthError` / `NetworkError` / `StaleDataError` - callers never see raw HTTP/JSON errors. Handles login, a possible region redirect (caching the resolved host into `Settings.base_host`), and an `Account-Id` header (SHA-256 of the login response's user id) that the API requires for `/llu/connections`. The `version` header spoofs the official app's version and is **version-gated by Abbott's backend** - it has already needed bumping once (a stale version triggers a 403 with body `{"status": 920, "data": {"minimumVersion": ...}}`); if reads start failing with that shape, bump `_REQUEST_HEADERS["version"]`.
- **`domain/`**: plain data and pure functions, no I/O. `GlucoseReading` always stores its value in mg/dL (the API's native unit) - unit conversion (`domain/units.py`) and range classification (`domain/range.py`, thresholds configurable via `Settings`) happen only at display time, never duplicated elsewhere.
- **`poller/poller.py`**: a background `threading.Thread` (not asyncio - the rest of the app is GTK/GLib callback-driven, so a plain thread avoids running two event loops) that calls the client on an interval and publishes `ReadingUpdatedEvent` / `PollErrorEvent` events on an `EventBus`. This bus is the intentional seam for phase 2 (`alerts/`, currently just a stub) to subscribe to the same reading stream as the UI without touching this code.
- **`ui/`**: `Display` (in `display.py`) is the protocol `main.py` talks to; `TrayDisplay` (`tray.py`) is the only implementation. Non-obvious things here:
  - AppIndicator's built-in text **label** feature does not render under this project's target environment (GNOME Shell 46 + `ubuntu-appindicators`) even though the app publishes it correctly over D-Bus (confirmed by direct inspection) - a Shell-side bug, not fixable from here. Workaround: `ui/icon_renderer.py` renders the reading as a bitmap (Cairo/Pango) and that image *is* the tray icon.
  - GNOME Shell caches a tray icon bitmap by filename and never re-reads it once that name has been seen, even after the file's content changes. `TrayDisplay` works around this by giving every update a brand-new, never-reused filename (an incrementing counter) and deleting old files, keeping only the last two.
  - `gi.require_version("Gtk", "3.0")` must run before anything else imports `Gtk` (Ubuntu's system default is Gtk 4) - done first thing in `main.py`, and `tray.py`/`credential_prompt.py` also set it defensively since they can be imported standalone (e.g. by tests).
  - `TrayDisplay` also tries `AyatanaAppIndicator3` first and falls back to classic `AppIndicator3`, since Ubuntu ships the Ayatana fork.
  - The tray menu's top entry, "GlucoGlance" (`ui/about_dialog.py`), doubles as both a title and the About trigger - there's no separate disabled header item.
  - The medical/affiliation disclaimer lives in one place, `ui/disclaimer.py`, and is shown both in the About dialog and above the fields of the first-run credential prompt. The README's "Disclaimer" section is a longer version of the same text - keep them consistent. Don't add UI or docs that make medical claims or suggest using readings for treatment decisions.
  - "Log out" (in `tray.py`) deletes the stored keyring password and clears `Settings.account_email`, then reuses the same `os.execv` self-restart as "Restart" - the fresh process finds no credentials and falls into the normal first-run prompt flow, rather than needing separate "log out and re-prompt" code.
- **`config/`**: `settings.py` is the single source of truth for every user-tunable value (poll interval, unit, range thresholds/colors, autostart) as TOML at `~/.config/glucoglance/config.toml`; nothing hot-reloads, so a config edit needs a restart (the tray menu's "Restart" item does an `os.execv` self-restart for this). `credentials.py` stores only the password, via the system keyring - the email lives in `settings.py` since it's not secret. `autostart.py` installs/removes `~/.config/autostart/glucoglance.desktop`, generating `Exec=` as the absolute path to the script next to the running interpreter (not the bare `glucoglance` command, which isn't guaranteed to be on `PATH` in a login session for a venv install).
  - The autostart entry also always carries `X-GNOME-Autostart-Delay=6` (`_STARTUP_DELAY_SECONDS` in `autostart.py`), purely to influence where the tray icon lands relative to other autostart tray apps (GNOME's AppIndicator extension inserts new icons ahead of existing ones rather than appending, so registering later tends to land further left). **Do not implement this as a shell-wrapped `Exec=` line** (e.g. `sh -c "sleep N && exec ..."`) - an earlier version did exactly that, and it passed `desktop-file-validate` and GLib's own `shell_parse_argv` but was rejected at real login by both `systemd-xdg-autostart-generator` and `gnome-session-binary` ("Undefined escape sequence" / "didn't specify Exec field", confirmed via `journalctl -b`). The native `X-GNOME-Autostart-Delay` key is the only mechanism that actually works across both.

### Testing philosophy

Pure logic is unit-tested with fixtures/mocks and no display server: `client` parsing (including the login/redirect sequence, via `responses`), all of `domain/`, `poller` (via a fake client), `config/settings.py` and `config/autostart.py` (round-trips, via `tmp_path`), `ui/icon_renderer.py` (Cairo/Pango rendering needs no display server, so it's testable despite living under `ui/`), and `ui/about_dialog.py`'s version lookup. Actual GTK/tray rendering (does the icon really show up, does the credential dialog really pop up) is manual-only - there is no headless GTK test setup here.

Coverage includes branches (`[tool.coverage.run] branch = true`), not just lines - a line can show "covered" while one of its branches was never exercised. Overall coverage sits around 49% by design: `main.py`, `ui/tray.py`, `ui/credential_prompt.py`, `ui/display.py`, and `config/credentials.py` are GTK/keyring-dependent and deliberately manual-only, not accidentally untested. Ruff's lint rules explicitly exclude `E402` (PyGObject requires `gi.require_version()` calls before the `gi.repository` imports they gate, which cascades to every later import in a file) and `DTZ` (timestamps here are intentionally naive local time, not a bug - see `client/librelinkup.py`'s docstring).

## CI and branch workflow

GitHub Actions (`.github/workflows/ci.yml`) lints and tests every push to `develop`/`master` and every PR, publishing a JUnit test report and a coverage summary (with diff/patch coverage on PRs) as a sticky PR comment. This **cannot currently block a PR merge on failure** - GitHub's required-status-checks branch protection needs GitHub Pro on a private repo, which this one doesn't have.

For the same reason, `master` is **PR-only by convention, not by enforcement**: don't push commits directly to `master` unless explicitly asked to. Normal flow is committing to `develop` (or a feature branch off it) and opening a PR into `master` when asked to ship something.

## Project status

Phase 1 (live tray display) is done and has been verified end-to-end against the real LibreLinkUp API, including a real autostart-at-login test after a full reboot. Phase 2 (threshold alarms, subscribing to the poller's `EventBus`) is not started - `alerts/base.py` is an empty placeholder.
