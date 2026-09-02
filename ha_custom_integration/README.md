# School Cycle Days — Rewrite / Migration Work

This folder contains the replacement work for the original AppDaemon School Cycle Days application. Nothing under the existing repository `apps/` tree has been overwritten.

## Current architectural decision

The **preferred implementation is now the standalone application** under:

```text
ha_custom_integration/standalone_app/
```

It runs independently of Home Assistant and connects remotely using Home Assistant's supported REST and WebSocket APIs.

This is a deliberate change from the earlier HA-native custom-integration prototype.

### Why the architecture changed

The earlier work moved the AppDaemon application into a Home Assistant custom integration so it could use Home Assistant's internal calendar entity API, especially event deletion.

A review of current Home Assistant Core established that an authenticated remote client can now do everything this application needs without executing School Cycle Days code inside HA:

- list calendars with `GET /api/calendars`;
- retrieve calendar events with `GET /api/calendars/<entity_id>?start=...&end=...`;
- create calendar events through the normal calendar service REST endpoint;
- authenticate to `/api/websocket`;
- delete a calendar event remotely with the built-in WebSocket command `calendar/event/delete`.

That makes a custom HA bridge unnecessary on current Home Assistant.

The result is a much cleaner boundary:

```text
┌────────────────────────────────────────────┐
│ Standalone School Cycle Days               │
│                                            │
│ FastAPI web UI                             │
│ cycle-day engine                           │
│ SQLite settings/data                       │
│ holidays                                   │
│ non-school days                            │
│ selective regeneration                    │
└──────────────────────┬─────────────────────┘
                       │
              REST + WebSocket
                       │
                       ▼
┌────────────────────────────────────────────┐
│ Home Assistant                             │
│                                            │
│ authentication                             │
│ calendar entities/providers                │
│ calendar event create/delete               │
└────────────────────────────────────────────┘
```

Home Assistant is an integration target, not the runtime for the application.

## Why this is preferable

### Development

Run:

```bash
uvicorn school_cycle_days.main:app --reload
```

and Python changes reload the standalone application automatically.

There is no need to restart Home Assistant after changing School Cycle Days code.

### Reliability

Restarting or upgrading HA does not restart the School Cycle Days application.

Restarting the School Cycle Days application does not affect Home Assistant.

### UI

The application has its own purpose-built browser UI. Routine work remains UI-first:

- choose the HA calendar;
- change school-year dates;
- edit all five cycle descriptions;
- choose starting cycle day;
- add/remove non-school dates;
- calculate holidays;
- generate the calendar;
- selectively regenerate a range;
- delete generated events on a single day.

Users do not need to edit Python, YAML, Home Assistant Helpers, or `.ics` files for ordinary operation.

### Persistence

Application state is stored in SQLite rather than HA Helper entities or AppDaemon-created attributes.

## Directory layout

```text
ha_custom_integration/
├── README.md
├── APPDAEMON_COMPATIBILITY_AUDIT.md
├── LOCAL_TESTING_GUIDE.md
├── standalone_app/                 # PRIMARY IMPLEMENTATION
│   ├── README.md                   # detailed architecture/run documentation
│   ├── .env.example
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── pyproject.toml
│   ├── school_cycle_days/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── ha_client.py
│   │   ├── main.py
│   │   └── service.py
│   └── templates/
│       └── index.html
│
├── custom_components/             # EARLIER HA-NATIVE PROTOTYPE
│   └── school_cycle_days/
│       └── ...
│
└── examples/
    └── school_cycle_days_dashboard.yml
```

## Documentation

Start with:

```text
standalone_app/README.md
```

It documents:

- architecture;
- HA authentication;
- REST/WebSocket behavior;
- local Python setup;
- Docker deployment;
- hot reload/update behavior;
- data ownership;
- event ownership markers;
- selective deletion;
- security;
- testing;
- relationship to the HA-native prototype.

`APPDAEMON_COMPATIBILITY_AUDIT.md` remains useful for comparing the original AppDaemon behavior with the rewrite.

`LOCAL_TESTING_GUIDE.md` documents testing of the earlier HA-native prototype and remains as a reference while the migration is in progress.

## Standalone quick start

From:

```text
ha_custom_integration/standalone_app/
```

create `.env`:

```bash
cp .env.example .env
```

Set at least:

```dotenv
SCD_HA_URL=http://homeassistant.local:8123
SCD_HA_TOKEN=<long-lived-access-token>
```

Create a virtual environment and install:

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
pip install -e .
```

Run:

```bash
uvicorn school_cycle_days.main:app --reload --host 0.0.0.0 --port 8088
```

Then open:

```text
http://localhost:8088
```

For Docker:

```bash
docker compose up -d --build
```

## Home Assistant credential

For this personal/local deployment, create a dedicated Long-Lived Access Token from the Home Assistant user profile.

The token is supplied only through the environment:

```text
SCD_HA_TOKEN
```

Do not commit the token.

If this application is ever distributed as a general-purpose application to other users, replace the long-lived-token setup with Home Assistant's OAuth authorization flow.

## Selective calendar deletion

The standalone app never needs to delete the entire calendar file.

For regeneration it:

1. requests HA calendar events for the requested range;
2. identifies events created by School Cycle Days;
3. gets their `uid` values;
4. sends `calendar/event/delete` commands over HA's authenticated WebSocket API;
5. leaves unrelated events untouched;
6. creates the replacement events.

New events carry:

```text
[school_cycle_days]
```

in their description.

The app also recognizes the event naming convention used by the old AppDaemon application so existing cycle-day entries can be migrated selectively.

## Status of the HA-native prototype

The earlier implementation under:

```text
custom_components/school_cycle_days/
```

is intentionally **not deleted yet**.

It serves as:

- a behavioral reference;
- a fallback for testing;
- documentation of the AppDaemon-to-HA-native migration;
- possible compatibility code for an older HA release that lacks required remote calendar APIs.

It is no longer the preferred deployment architecture.

Do not run the standalone application, HA-native prototype, and AppDaemon against the same production calendar simultaneously during testing.

## Next validation target

Test the standalone app against a disposable HA Local Calendar first:

```text
calendar.school_cycle_test
```

Verify:

1. HA connection works;
2. calendars appear in the standalone UI;
3. short-range generation works;
4. event UIDs are returned by the HA calendar endpoint;
5. deleting one generated date works remotely;
6. selective regeneration preserves unrelated events;
7. snow-day cycle shifting behaves correctly;
8. standalone state survives app restart;
9. HA restart does not lose standalone state;
10. production calendar is used only after the above passes.
