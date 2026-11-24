# Manual tray tests

A checklist to run by hand before a release, or after touching `ui/tray.py`,
`domain/range_tracker.py`, `main.py` or the poller. Tick each box as it passes.

Defaults assumed below: low **80**, high **180**, hysteresis **5** (mg/dL).
If your `config.toml` differs, shift the numbers.

---

## Setup

1. Terminal 1 - start the tray on fake data (polls every 2 s):
   ```bash
   source .venv/bin/activate
   python scripts/run_with_fake_reading.py --value 120 --interval 2
   ```
2. Terminal 2 - change the reading:
   ```bash
   f="$XDG_RUNTIME_DIR/glucoglance-fake-reading"
   echo 190 > "$f"        # value in mg/dL
   echo "190 5" > "$f"    # value + trend (1 ⇊, 2 ↓, 3 →, 4 ↑, 5 ⇈)
   echo error > "$f"      # or: stale, auth
   ```
3. After each `echo`, wait one poll (~2 s) before checking.

**Acknowledge** = middle-click the icon, or click the menu item
"Stop blinking" / "Clear highlight".

---

## 1. Startup

- [ ] **Waiting icon** - Start the harness → the app mark (normal eye) shows for a moment.
- [ ] **First reading** - Started with `--value 120` → mark replaced by `120 →` in green.

## 2. Values and colors

| ✓ | Test | Do | Expect |
|---|---|---|---|
| [ ] | Normal | `echo 120` | `120 →` green, no blink |
| [ ] | High edge (in) | `echo 180` | green |
| [ ] | High | `echo 181` | yellow, blinks |
| [ ] | Low edge (in) | `echo 80` | green |
| [ ] | Low | `echo 79` | red, blinks |
| [ ] | Trend arrows | `echo "120 1"` … `"120 5"` | `⇊ ↓ → ↑ ⇈` in that order |
| [ ] | Unknown trend | `echo "120 9"` | `120 ?` |
| [ ] | 3 digits / 2 digits | `echo 250`, then `echo 60` | both fully visible, no clipping, no leftover digits |

## 3. Highlight (blink)

| ✓ | Test | Do | Expect |
|---|---|---|---|
| [ ] | Blink starts | `echo 120`, then `echo 200` | blinks yellow (filled ↔ plain) |
| [ ] | Menu while blinking | Open the menu | Item "Stop blinking (middle-click)" present; opening the menu does **not** stop it |
| [ ] | Ack by menu | Click "Stop blinking" | Stops, plain yellow text, item disappears |
| [ ] | Ack by middle-click | `echo 120`, `echo 200`, middle-click | Same as above |
| [ ] | No re-blink same stretch | After ack, `echo 210` | No blink |
| [ ] | Back in range clears | `echo 120`, `echo 200`, then `echo 150` | Green, blink stops by itself, item gone |
| [ ] | New stretch blinks | then `echo 200` | Blinks again |
| [ ] | Low ↔ high jump | `echo 70`, ack, `echo 200` | Blinks yellow (new crossing) |
| [ ] | Steady after timeout | See [Short blink](#short-blink-timeout); `echo 200`, wait past timeout | Stops blinking, **stays filled**; menu item reads "Clear highlight (middle-click)" |
| [ ] | Ack steady | Click "Clear highlight" | Plain yellow text |

## 4. Hysteresis and acknowledge (#20)

| ✓ | Test | Do | Expect |
|---|---|---|---|
| [ ] | Band holds color | `echo 120`, `echo 190`, `echo 178` | Still yellow and blinking |
| [ ] | Leaves band | `echo 175` | Green |
| [ ] | **Ack in band → green** | `echo 190`, `echo 178`, ack | Stops, turns **green** at once |
| [ ] | After that | `echo 179` | Green, no blink |
| [ ] | Fresh crossing | `echo 182` | Blinks yellow again |
| [ ] | Ack while really out | `echo 120`, `echo 195`, ack | Stops, **stays yellow** |
| [ ] | Band after that | `echo 178` | Yellow, no blink (hysteresis still applies) |
| [ ] | Low side | `echo 120`, `echo 75`, `echo 82`, ack | Turns **green** |
| [ ] | Ack with nothing highlighted | `echo 120`, middle-click | Nothing changes |

## 5. Errors (no data)

| ✓ | Test | Do | Expect |
|---|---|---|---|
| [ ] | Network | `echo error` | Red-eye mark, no number; menu line "No data: can't reach LibreLinkUp" |
| [ ] | Stale | `echo stale` | Red-eye; "No data: no recent sensor reading" |
| [ ] | Auth | `echo auth` | Red-eye; "No data: login needed" (harness skips the login prompt) |
| [ ] | Garbage | `echo abc` | Same as network |
| [ ] | Recovery | `echo 120` | Number back, menu line gone |
| [ ] | Error mid-blink | `echo 200` (blinking), `echo error` | Blink stops, red-eye, no ack item in menu |
| [ ] | Blink resumes | `echo 205` | Blinks again (not acknowledged yet) |
| [ ] | Middle-click during error | `echo 200`, `echo error`, middle-click, `echo 205` | Click ignored; blinks again |
| [ ] | Ack, error, back in band | `echo 190`, `echo 178`, ack, `echo error`, `echo 178` | Green, no blink |
| [ ] | No ghost image | Alternate `echo 250` / `echo error` 3-4 times | Never a number drawn under the mark, or vice versa; neighbor icons don't jump sideways |

## 6. Menu

- [ ] **About** - Click "GlucoGlance" → About dialog opens.
- [ ] **Start at login** - Toggle → checkbox flips (harness: no real change).
- [ ] **Show in Applications menu** - Toggle → checkbox flips (hidden if installed from the .deb).
- [ ] **Restart** - Icon disappears and comes back with the current reading.
- [ ] **Log out** - Does nothing under the harness (logged only). Test it on the real app (section 8).
- [ ] **Quit** - Icon disappears, terminal 1 returns to the prompt.

## 7. Settings variants

Back up first: `cp ~/.config/glucoglance/config.toml{,.bak}`. Edit, then **Restart** from the menu. Restore the backup when done.

- [ ] **mmol/L** - `unit = "mmol"`; `echo 120` → `6.7 →`. Thresholds still behave as in mg/dL.
- [ ] **No blink** - `highlight_pulse = false`; `echo 200` → yellow, no blink, no ack item.
- [ ] **Custom thresholds** - `high_threshold_mgdl = 160`; `echo 165` → yellow.
- [ ] **Custom colors** - change `color_high`; `echo 200` → new color.
- [ ] **Hysteresis 0** - `range_hysteresis_mgdl = 0`; `echo 190`, `echo 179` → green straight away.

## 8. Real app only (not covered by the harness)

- [ ] **Single instance** - Start `glucoglance` twice → "already running" notice, only one icon.
- [ ] **First login** - Log out → login dialog; wrong password → error shown; right one → readings.
- [ ] **Log out** - Credentials forgotten, login dialog after restart.
- [ ] **Autostart** - Toggle "Start at login" → `~/.config/autostart/glucoglance.desktop` created / removed.
- [ ] **Real reading** - Matches the LibreLinkUp phone app.

---

## Tools

### Short blink timeout

Blinking lasts 20 min before going steady. To test it in seconds, start with:

```bash
python - --interval 2 <<'EOF'
import runpy, sys
import glucoglance.ui.tray as tray
tray._BLINK_DURATION_S = 15  # seconds
sys.argv = ["scripts/run_with_fake_reading.py", *sys.argv[1:]]
runpy.run_path(sys.argv[0], run_name="__main__")
EOF
```

### Check without looking (D-Bus)

Useful for scripting, or when you can't tell blink states apart by eye.

```bash
pid=$(pgrep -f run_with_fake_reading.py | head -1)
bus=$(busctl --user list --no-legend | awk -v p="$pid" '$2==p {print $1; exit}')
obj=/org/ayatana/NotificationItem/glucoglance
sni=org.kde.StatusNotifierItem

# Status: Active = plain icon, NeedsAttention = filled. Alternating = blinking.
busctl --user get-property "$bus" $obj $sni Status

# Simulate a middle-click (acknowledge)
busctl --user call "$bus" $obj $sni SecondaryActivate ii 0 0
```
