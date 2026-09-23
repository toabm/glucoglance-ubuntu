# GlucoGlance for Ubuntu

[![CI](https://github.com/toabm/glucoglance-ubuntu/actions/workflows/ci.yml/badge.svg)](https://github.com/toabm/glucoglance-ubuntu/actions/workflows/ci.yml)

A tray widget that shows your current glucose reading (from a FreeStyle
Libre sensor, via LibreLinkUp) in the Ubuntu top bar. Phase 1: just the
number and trend arrow, refreshed roughly every minute. Threshold alarms are
planned as a phase 2.

## Requirements

You need a LibreLinkUp **follower** account already set up: the sensor
wearer shares their readings to LibreLinkUp, and you use a follower
account's email/password to log in here. This app cannot talk to the
sensor directly.

## Installing on Ubuntu

These steps assume a fresh Ubuntu machine with nothing set up yet - if
you've already done part of this, skip ahead.

**1. Get the code:**

```bash
git clone https://github.com/toabm/glucoglance-ubuntu.git
cd glucoglance-ubuntu
```

**2. Install the system packages** the tray icon needs (these come from
`apt`, not `pip` - they're GTK/AppIndicator bindings that Python's package
index doesn't distribute):

```bash
sudo apt install python3-venv python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
```

(If your Ubuntu/distro version ships classic `AppIndicator3` instead of
the Ayatana fork, install `gir1.2-appindicator3-0.1` instead - the app
tries Ayatana first and falls back automatically, so either works.)

**3. Create a Python virtual environment and install the app into it.**
`--system-site-packages` is required here - it lets the venv reuse the
`python3-gi` bindings you just installed with `apt`, instead of trying
(and failing) to build them from PyPI:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install .
```

That's the whole install. The `glucoglance` command now exists at
`.venv/bin/glucoglance` (and on your `PATH` while the venv is
activated).

## Running it for the first time

With the venv activated (`source .venv/bin/activate`, if you're in a new
terminal):

```bash
glucoglance
```

A small dialog pops up asking for your LibreLinkUp email and password (see
Requirements above). Enter them and press OK. The email is saved to
`~/.config/glucoglance/config.toml`; the password is stored in your
system keyring (GNOME Keyring), never in plaintext. A number should then
appear in your top bar within a few seconds - that's your current glucose
reading.

You won't need to repeat this - the credentials are remembered, and (see
below) the app is set to start automatically at every login by default.

Right-click the tray icon for:
- **Start at login** - checkbox, on by default (see "Running automatically
  at login" below).
- **Restart** - reloads the app, e.g. after editing `config.toml`.
- **Quit**.

## Adding it to your Applications menu

This is separate from "start at login" below: this makes GlucoGlance
show up as a proper icon in GNOME's Activities overview and app search
(so you can launch it manually, or pin it to the Dock), rather than only
starting silently in the background. Run this once, from the repo
directory, with the venv already created as above:

```bash
test -x .venv/bin/glucoglance || { echo "Run this from the glucoglance-ubuntu directory (the venv wasn't found here)"; exit 1; }
ICON_PATH=$(.venv/bin/python3 -c "from glucoglance.ui.app_icon import app_icon_path; print(app_icon_path())")
mkdir -p ~/.local/share/applications
cat > ~/.local/share/applications/glucoglance.desktop <<EOF
[Desktop Entry]
Type=Application
Name=GlucoGlance
Exec=$(pwd)/.venv/bin/glucoglance
Icon=$ICON_PATH
Comment=Shows current blood glucose reading in the top bar
Terminal=false
Categories=Utility;
EOF
```

It should now appear if you search for "GlucoGlance" in GNOME's
Activities overview (press the Super/Windows key and start typing). From
there you can drag it onto the Dock to pin it.

(This installs into `~/.local/share/applications`, the standard location
for manually-installed apps - not `/usr/share/applications`, which is
where apt/snap-installed apps land since that directory is shared across
all users on the machine. GNOME scans both identically, so this works the
same either way; no need to move it.)

(The `Exec=` line uses an absolute path to the venv you just created,
rather than the bare `glucoglance` command, since a graphical launcher
doesn't necessarily have your venv on its `PATH`. If you ever move the
`glucoglance-ubuntu` folder, re-run the command above to update it.)

## Configuration

Settings live at `~/.config/glucoglance/config.toml` (created with
defaults on first run). Notable options:

```toml
interval_seconds = 60      # how often to poll, in seconds
unit = "mgdl"               # "mgdl" or "mmol"
low_threshold_mgdl = 80     # below this, the icon turns red
high_threshold_mgdl = 180   # above this, the icon turns yellow (green in between)
color_low = "#ED4343"
color_normal = "#4DCC66"
color_high = "#F5D334"
autostart_enabled = true   # start automatically at login (see below)
```

Edit the file and restart `glucoglance` for changes to take effect.

## Running automatically at login

Enabled by default - on every startup the app installs (or removes) a
`~/.config/autostart/glucoglance.desktop` entry to match the
`autostart_enabled` setting. That path is the standard XDG autostart
location on Ubuntu (and GNOME/most other Linux desktops generally), but
this project is only built and tested against Ubuntu - see "Installing on
Ubuntu" above. Toggle it anytime from the tray icon's right-click menu
("Start at login"), or by editing `autostart_enabled` in `config.toml` and
restarting.

That autostart entry always waits 6 seconds before actually launching the
app (only on this path - running from a terminal or the Applications-menu
icon starts immediately). This isn't configurable, and it's not about
sensor timing: it exists purely to influence where the icon lands in the
top bar. GNOME Shell's AppIndicator extension inserts each new tray icon
at a fixed position rather than appending, so indicators that register
*later* tend to end up ahead of ones that registered earlier. The delay
gives your other autostart tray apps a head start, with the goal of
landing this icon at the left edge of the right-side icon group (i.e.
immediately after the clock, ahead of things like wifi/bluetooth/volume) -
though the exact result depends on how many other apps you have and how
long they take to start, so it may need tuning (edit
`_STARTUP_DELAY_SECONDS` in `config/autostart.py`) to get exactly there.

## Tests & linting

Tests and linting need the extra dev dependencies, which the regular
install above skips:

```bash
pip install -e ".[dev]"
ruff check .                                          # lint
pytest --cov=glucoglance --cov-report=term-missing # tests + coverage
```

Overall coverage sits around 49% by design, not by accident: GTK/keyring-
dependent code (`main.py`, `ui/tray.py`, `ui/credential_prompt.py`,
`ui/display.py`, `config/credentials.py`) is deliberately manual-only -
see CLAUDE.md's "Testing philosophy" section.

Coverage includes branches (`[tool.coverage.run] branch = true` in
`pyproject.toml`, applied automatically - no extra flag needed), not
just lines: a line can show as "covered" while one of its branches
(e.g. one side of an `if`) was never actually exercised, so branch
coverage catches real gaps line coverage hides.

If your IDE flags `gi.repository` symbols (e.g. `GLib`, `Gtk`) as
unresolved, that's expected - PyGObject generates those modules
dynamically from typelibs at runtime, not from real `.py` files, so
static analyzers can't see them without type stubs. Install those
separately from `dev` (pip otherwise tries to rebuild the real
PyGObject/pycairo from source to satisfy this package's declared
dependency, and fails without cairo/girepository dev headers):

```bash
pip install --no-deps PyGObject-stubs
```

## Continuous integration

Every push to `develop`/`master` and every pull request runs `ruff` and
the full test suite (`.github/workflows/ci.yml`), publishing a test
report and a coverage summary (including diff/patch coverage on PRs) as
a PR comment. Note: this doesn't currently *block* merging on failure -
GitHub's required-status-checks branch protection needs GitHub Pro on a
private repo, which this one doesn't have (see `master` being PR-only by
convention rather than by enforcement, for the same reason).

## Project layout

- `client/` - talks to the LibreLinkUp API.
- `domain/` - plain data types (readings, trend, unit conversion), no I/O.
- `poller/` - background polling loop; publishes events on an `EventBus`.
- `alerts/` - placeholder for phase 2 threshold alarms.
- `ui/` - the tray display, built behind a small `Display` interface so
  other frontends (e.g. a floating window) can be added later.
- `config/` - settings (TOML) and credentials (system keyring).

## Why the number is drawn as an icon, not a tray label

AppIndicator has a built-in feature for showing text next to the tray icon
(a "label"). On this project's target environment (GNOME Shell 46 +
`ubuntu-appindicators`), that feature silently doesn't render anything,
even though the app publishes it correctly - a Shell-extension bug, not
something fixable from the app side. Instead, `ui/icon_renderer.py` draws
the reading as a small bitmap and that image becomes the tray icon itself,
which does render reliably. If a future Shell/extension update fixes label
rendering, this could be simplified back to `set_label()`.
