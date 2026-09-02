# School Cycle Days — Standalone Application

This is now the **preferred architecture** for the School Cycle Days rewrite.

The application runs independently of Home Assistant and connects to Home Assistant remotely using Home Assistant's supported HTTP REST API and WebSocket API.

It does **not** require AppDaemon and, on current Home Assistant, it does **not** require a custom Home Assistant integration or bridge.

## Why there is no HA bridge

During the earlier custom-integration port, calendar deletion was implemented by calling Home Assistant's internal `CalendarEntity.async_delete_event()` method from Python running inside HA.

Further review of current Home Assistant Core showed that Home Assistant now exposes the same operation to authenticated remote clients through its built-in WebSocket API:

```text
calendar/event/delete
```

Home Assistant also exposes calendar event retrieval over REST:

```text
GET /api/calendars/<entity_id>?start=<timestamp>&end=<timestamp>
```

The returned event representation includes the calendar event UID when the calendar provider supplies one. That UID can then be passed to `calendar/event/delete` over the WebSocket connection.

Therefore the standalone application can perform the complete workflow remotely:

```text
Standalone School Cycle Days
        |
        | HTTPS/REST
        |  - HA configuration/timezone
        |  - calendar list
        |  - calendar event list
        |  - calendar.create_event
        |
        | WebSocket
        |  - authenticate
        |  - calendar/event/delete
        v
Home Assistant
        |
        v
calendar.school
```

There is no application process inside Home Assistant in this design.

The earlier HA-native custom integration remains in this branch as a migration/reference implementation until the standalone path has been proven in your environment.

---

# Responsibilities

## Standalone application owns

- school-year start/end dates;
- cycle-day labels;
- starting cycle-day number;
- manually entered non-school days;
- holiday calculation and storage;
- generation rules;
- determination of which calendar events belong to School Cycle Days;
- selective regeneration logic;
- the user interface;
- persistent application data;
- communication with Home Assistant.

## Home Assistant owns

- the target `calendar.*` entity;
- actual calendar persistence/provider integration;
- authentication/authorization;
- execution of calendar create/delete operations.

Home Assistant is now a remote dependency rather than the application runtime.

---

# Project layout

```text
standalone_app/
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── README.md
├── data/
│   └── school_cycle_days.sqlite3   # created at runtime
├── school_cycle_days/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── ha_client.py
│   ├── main.py
│   └── service.py
└── templates/
    └── index.html
```

## `config.py`

Loads environment-level configuration such as Home Assistant's URL/token and the SQLite database location.

## `database.py`

Owns application persistence. It currently uses SQLite from Python's standard library.

Tables:

```text
settings
non_school_days
holiday_days
```

This means application state no longer depends on Home Assistant Helpers or `.storage` entities.

## `ha_client.py`

Contains the only Home Assistant-specific transport code.

It implements:

```python
await ha.test_connection()
await ha.config()
await ha.calendars()
await ha.events(...)
await ha.create_event(...)
await ha.delete_event(...)
```

The rest of the application does not need to understand Home Assistant's REST or WebSocket protocols.

## `service.py`

Contains the actual School Cycle Days business logic:

- calculate the cycle;
- skip blocked weekdays;
- optionally create visible No School/weekend entries;
- create School Cycle Days events;
- detect events owned by School Cycle Days;
- delete generated events by UID;
- selectively regenerate ranges;
- generate holidays.

## `main.py`

FastAPI HTTP routes and UI form handlers.

The web layer is intentionally thin. Business logic stays in `service.py` so a different UI can be added later without rewriting the calendar engine.

---

# Home Assistant authentication

For a private/local installation, create a Home Assistant Long-Lived Access Token.

In HA:

```text
Your Profile
→ Security
→ Long-Lived Access Tokens
→ Create Token
```

Use a dedicated token for this application rather than reusing another application's token.

Store it in the environment:

```text
SCD_HA_TOKEN=...
```

Do not commit the real token to GitHub.

The application sends it as:

```http
Authorization: Bearer <token>
```

for REST requests and uses the same access token in the HA WebSocket authentication handshake.

---

# Configuration

Copy:

```bash
cp .env.example .env
```

Then edit `.env`:

```dotenv
SCD_HA_URL=http://homeassistant.local:8123
SCD_HA_TOKEN=YOUR_LONG_LIVED_ACCESS_TOKEN
SCD_DATABASE_PATH=./data/school_cycle_days.sqlite3
SCD_VERIFY_SSL=true
SCD_HOST=0.0.0.0
SCD_PORT=8088
```

If you connect to HA through HTTPS using an internally/self-signed certificate and certificate verification cannot succeed, you can temporarily use:

```dotenv
SCD_VERIFY_SSL=false
```

A trusted certificate is preferable.

---

# Run locally with Python

Requires Python 3.12+.

From `standalone_app/`:

```bash
python -m venv .venv
```

Windows Git Bash:

```bash
source .venv/Scripts/activate
```

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install:

```bash
pip install -e .
```

Run in development mode:

```bash
uvicorn school_cycle_days.main:app --reload --host 0.0.0.0 --port 8088
```

Open:

```text
http://localhost:8088
```

## Development hot reload

This is a major advantage over a Home Assistant custom integration.

When running:

```bash
uvicorn school_cycle_days.main:app --reload
```

changes to Python source files cause the standalone process to restart automatically.

You **do not restart Home Assistant** when modifying:

```text
main.py
service.py
ha_client.py
database.py
config.py
```

Home Assistant does not contain or execute this code.

Template changes are generally visible on the next request; if a browser has cached something, refresh the browser.

Changes to environment variables in `.env` require restarting the standalone process because application settings are loaded at startup.

---

# Run with Docker Compose

From `standalone_app/`:

```bash
docker compose up -d --build
```

The application will listen on:

```text
http://<docker-host>:8088
```

Persistent database data is stored in:

```text
./data/
```

because Compose mounts that folder into `/data` in the container.

## Updating Docker deployment

After pulling new application code:

```bash
git pull
cd ha_custom_integration/standalone_app
docker compose up -d --build
```

No Home Assistant restart is needed.

---

# Web UI workflow

## Initial setup

1. Start the standalone application.
2. Open its web UI.
3. Confirm Home Assistant is connected.
4. Choose the target HA calendar from the calendar dropdown.
5. Choose the US state used for holiday calculation.
6. Enter school-year start/end dates.
7. Enter Cycle Day 1 through Cycle Day 5 labels.
8. Set the starting cycle day.
9. Save settings.

The calendar dropdown comes directly from Home Assistant's `/api/calendars` endpoint, so entity IDs do not have to be typed manually.

## Add a non-school day

Use the **Non-school days** panel:

1. choose a date;
2. press **Add non-school day**.

The date is stored in the application's SQLite database.

## Remove a non-school day

Each stored date has a **Remove** control in the UI.

## Holidays

Press:

```text
Load / refresh holidays
```

The application calculates US holidays for the school-year period and configured state and stores them locally.

Holiday dates are included in the blocked-day set used when generating cycle days.

## Initial generation

Press:

```text
Generate configured school year
```

This creates events but does not delete existing events first.

Use this for a clean/empty calendar or first test.

## Regeneration

Use:

```text
Delete generated events + regenerate range
```

You can enter a partial range, such as:

```text
2026-12-03 through 2027-06-15
```

or leave both range fields blank to use the configured school year.

The application:

1. requests calendar events for the range from HA;
2. identifies School Cycle Days events;
3. obtains each event UID;
4. deletes only those events through `calendar/event/delete`;
5. leaves unrelated calendar events untouched;
6. recreates the cycle-day entries for that range.

## Delete one generated date

Use:

```text
Delete generated events on this date
```

The app queries only that date and deletes School Cycle Days events found there.

You never enter a UID manually.

---

# Event ownership

New events created by this app include this marker in their description:

```text
[school_cycle_days]
```

That gives the application an explicit ownership signal for future deletion/regeneration.

For migration, the application also recognizes events generated by the old AppDaemon implementation:

```text
Day N (...)
```

and legacy `No School` Holiday/Weekend events.

This lets the standalone application selectively clean up existing AppDaemon-generated entries without deleting unrelated calendar content.

---

# Remote deletion mechanics

Selective deletion does **not** modify the Local Calendar `.ics` file.

The application first calls:

```text
GET /api/calendars/calendar.school?start=...&end=...
```

The response can contain fields including:

```json
{
  "summary": "Day 3 (Library)",
  "description": "Library\n[school_cycle_days]",
  "uid": "...",
  "start": {"date": "2026-12-03"},
  "end": {"date": "2026-12-04"}
}
```

For each owned event, the app opens `/api/websocket`, authenticates, and sends:

```json
{
  "id": 1,
  "type": "calendar/event/delete",
  "entity_id": "calendar.school",
  "uid": "..."
}
```

This is Home Assistant's built-in calendar WebSocket command.

No School Cycle Days Python code executes inside HA.

---

# Security boundary

The access token is effectively the standalone application's credential to Home Assistant.

Recommended practices:

- do not commit `.env`;
- do not render the token in the web page;
- limit access to the standalone web UI to your LAN/VPN or put it behind your normal authenticated reverse proxy;
- use HTTPS when crossing untrusted networks;
- use a dedicated HA user/token if you want to limit the blast radius;
- revoke the token from the HA profile if the credential is ever exposed.

The web UI currently assumes a trusted/private deployment. If it will be Internet-exposed, add authentication in front of it before doing so.

---

# What happens if Home Assistant is down?

The standalone app remains running and retains all of its settings/data in SQLite.

Operations that require HA will fail until HA is reachable:

- calendar discovery;
- event listing;
- event creation;
- event deletion/regeneration.

Local operations still work:

- editing settings already in the database;
- adding/removing non-school dates;
- holiday calculation/storage.

Once HA returns, no standalone restart is required unless the failure involved a changed environment configuration.

---

# What happens if the standalone app is down?

Home Assistant continues operating normally.

Existing calendar events remain in HA's calendar provider.

The standalone app is not required for HA startup, dashboards, automations, or other integrations.

When the app starts again it reconnects using the configured HA URL/token and uses its SQLite state.

---

# Testing strategy

Use a disposable Home Assistant Local Calendar such as:

```text
calendar.school_cycle_test
```

before selecting the production school calendar.

Recommended test:

1. configure a 4-day range;
2. generate Day 1–Day 4;
3. confirm events in HA;
4. delete generated events on one date;
5. confirm the other dates remain;
6. add an unrelated manual calendar event;
7. regenerate a range containing that event;
8. confirm the unrelated event remains;
9. add a snow day to the standalone database;
10. regenerate from that date forward;
11. confirm the cycle shifts correctly.

---

# Relationship to the HA-native prototype

This branch still contains:

```text
ha_custom_integration/custom_components/school_cycle_days/
```

That code represents the earlier architecture where School Cycle Days itself ran as a Home Assistant custom integration.

It is deliberately retained for now because it provides:

- migration reference;
- behavioral comparison;
- legacy helper mapping;
- fallback if an older HA version lacks a required remote calendar operation.

It is **not** required by the standalone application on current Home Assistant.

Do not run both implementations against the same production calendar while testing.

Once the standalone implementation is proven, the HA-native implementation can either be archived under a `legacy/` directory or removed in a later cleanup commit.
