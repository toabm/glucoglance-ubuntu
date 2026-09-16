# Glucose Widget for Ubuntu

A tray widget that shows your current glucose reading (from a FreeStyle
Libre sensor, via LibreLinkUp) in the Ubuntu top bar. Phase 1: just the
number and trend arrow, refreshed roughly every minute. Threshold alarms are
planned as a phase 2.

## Requirements

You need a LibreLinkUp **follower** account already set up: the sensor
wearer shares their readings to LibreLinkUp, and you use a follower
account's email/password to log in here. This app cannot talk to the
sensor directly.

## Install

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

(If your Ubuntu/distro version ships classic `AppIndicator3` instead of the
Ayatana fork, install `gir1.2-appindicator3-0.1` instead - the app tries
Ayatana first and falls back automatically.)

## Run

```bash
glucose-widget
```

On first run, a dialog asks for your LibreLinkUp email and password. The
email is saved to `~/.config/glucose-widget/config.toml`; the password is
stored in your system keyring, never in plaintext.

Right-click the tray icon for **Start at login** (checkbox), **Restart**
(reload after a config.toml edit), and **Quit**.

## Configuration

Settings live at `~/.config/glucose-widget/config.toml` (created with
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

Edit the file and restart `glucose-widget` for changes to take effect.

## Running automatically at login

Enabled by default - on every startup the app installs (or removes) a
`~/.config/autostart/glucose-widget.desktop` entry to match the
`autostart_enabled` setting. Toggle it anytime from the tray icon's
right-click menu ("Start at login"), or by editing `autostart_enabled` in
`config.toml` and restarting.

## Tests

```bash
pytest
```

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
