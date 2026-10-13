# Icon candidates

Icons designed for GlucoGlance but not currently used by the app. They're
kept here, outside the Python package, so they stay in the repo without
being shipped in the wheel or the `.deb` (everything in
`src/glucoglance/assets/` is packaged).

The icons the app actually uses live in `src/glucoglance/assets/`:
`app-icon.svg`/`.png` (the app icon: launchers, window icon, `.deb`) and
`tray-icon.svg`/`tray-icon-error.svg` (the tray mark).

| File | What it is |
|---|---|
| `app-icon-eye.svg` | The app icon's eye/gauge/drop mark on its own, without the navy tile. |
| `app-icon-drop.svg` / `.png` | An alternative style: an eye with a teardrop, on a light rounded tile. |
| `icon-gauge.png` | The original app icon (a glucose gauge), used until v0.4.0. Retired because it shows a made-up reading and turns illegible at small sizes. |
