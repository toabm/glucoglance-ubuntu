# Contributing to GlucoGlance

Thanks for helping out! GlucoGlance is a small hobby project, so reviews
may take a few days.

## Before you start

- **Read the Disclaimer section in the [README](README.md).** This app is not a
  medical device. Changes must not add medical claims, dosing advice, or
  anything that suggests the app can replace the official Libre app or a
  fingerstick meter.
- **Never commit or paste real credentials or health data** - not in
  code, test fixtures, issues, or PR descriptions. Test fixtures must use
  made-up values (see `tests/fixtures/`).
- For anything bigger than a small fix, open an issue first so we can
  agree on the approach before you spend time on it.

## Development setup

You need Ubuntu (or a similar GNOME desktop) with the GTK/AppIndicator
system packages:

```bash
sudo apt install python3-venv python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

`--system-site-packages` is required so the venv can reuse the apt-installed
`python3-gi` bindings.

## Checks

Both should pass before you open a PR (CI runs them on every PR too):

```bash
ruff check .
pytest --cov=glucoglance --cov-report=term-missing
```

GTK/tray code (`main.py`, `ui/tray.py`, `ui/credential_prompt.py`) can't
be tested headlessly, so if you change it, describe in the PR how you
tested it by hand (Ubuntu version, GNOME Shell version).

## Code style

- Follow the existing layering: `client -> domain -> poller -> ui/config`.
  Each layer only depends on the one below it (see `CLAUDE.md`'s
  Architecture section for details).
- Give modules and non-trivial functions a docstring explaining *why*, not
  just *what*.
- Keep code readable over clever.

## Branches and pull requests

- `develop` is the working branch; `master` only receives PRs from
  `develop` for releases.
- Branch off `develop` and open your PR against `develop`.
- Commit messages: a short imperative summary line, a blank line, then a
  bulleted list of what changed and why.

## Reporting bugs

Use the bug report issue template. Include your Ubuntu and GNOME Shell
versions and the app version (tray menu → GlucoGlance). If LibreLinkUp
suddenly starts failing for everyone, it's often because Abbott changed
the minimum app version their API accepts - see the `version` header note
in `CLAUDE.md`.
