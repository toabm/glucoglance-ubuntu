"""GlucoGlance: an Ubuntu tray application that displays a live glucose
reading fetched from the LibreLinkUp cloud API.

Package layout:
    client   - talks to the LibreLinkUp API and turns its responses into domain objects.
    domain   - plain data types (GlucoseReading, TrendArrow, unit conversion) with no I/O.
    poller   - background polling loop that publishes new readings/errors as events.
    alerts   - placeholder for phase 2 (threshold alarms); empty for now.
    ui       - the on-screen display (tray indicator today, possibly others later).
    config   - user settings and credential storage.
"""
