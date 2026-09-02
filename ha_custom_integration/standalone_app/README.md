# School Cycle Days — Standalone Application

School Cycle Days is now a **standalone school-cycle calendar application**.

Home Assistant is optional. The app can run completely on its own with:

- a polished month calendar;
- school-year and cycle-day configuration;
- manual snow/no-school days;
- state holiday generation;
- `.ics` import/cleanup;
- automatic schedule recalculation;
- SQLite persistence;
- a subscription-ready `.ics` feed;
- a versioned REST API.

Optional integrations include MQTT/Home Assistant Discovery and direct Home Assistant migration/publishing helpers.

## Core architectural rule

The application must still work when all Home Assistant and MQTT settings are blank.

The authoritative schedule lives in SQLite, not in Home Assistant, Google Calendar, or an external `.ics` file.

```text
Browser
   |
   v
School Cycle Days
├── web calendar
├── cycle engine
├── SQLite
├── ICS import
├── ICS feed
└── REST API
     |
     +-- optional MQTT / Home Assistant Discovery
     +-- optional direct Home Assistant adapter
```

## Quick start

From `ha_custom_integration/standalone_app/`:

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
pip install -e '.[dev]'
cp .env.example .env
uvicorn school_cycle_days.main:app --reload --host 0.0.0.0 --port 8088
```

Open:

```text
http://localhost:8088
```

No Home Assistant configuration is required.

## Docker

```bash
docker compose up -d --build
```

The application listens on port `8088` and persists its SQLite database under `/data` in the container.

## Standalone calendar

The home page is the product's own calendar UI.

It includes:

- month navigation;
- Today summary;
- Next School Day summary;
- cycle day number and label;
- No School highlighting;
- weekend styling;
- current-day highlighting;
- responsive layout;
- browser light/dark-mode support.

Saving settings, adding/removing a non-school day, loading holidays, or importing a district calendar recalculates the local schedule automatically.

## Schedule ownership

The generated schedule is stored in:

```text
schedule_days
```

inside the SQLite database.

Each date is classified as one of:

```text
school
no_school
weekend
```

School days contain:

```text
cycle_day
label/detail
```

The cycle advances only on actual school days.

## External `.ics` import

Upload any `.ics` school/district calendar from the web UI.

The importer preserves the original project's rule:

```text
SUMMARY starts with "No School"
```

Matching events become standalone non-school dates.

The importer also:

- deduplicates dates;
- expands multi-day events;
- repairs a trailing VEVENT missing `END:VEVENT`;
- skips malformed events rather than aborting the entire import;
- can download a cleaned `.ics` containing only the matching events.

See [`ICS_IMPORT_GUIDE.md`](ICS_IMPORT_GUIDE.md).

## Built-in ICS feed

Always available:

```text
GET /calendar.ics
```

This can be used as a subscription/download feed by compatible calendar clients.

School cycle days are always present.

Settings control whether the feed also includes:

- No School entries;
- weekend entries.

## REST API

### Health

```text
GET /api/v1/health
```

### Today

```text
GET /api/v1/today
```

### Tomorrow

```text
GET /api/v1/tomorrow
```

### Next school day

```text
GET /api/v1/next-school-day
```

### Schedule range

```text
GET /api/v1/schedule
```

Optional range:

```text
/api/v1/schedule?start=2026-09-01&end=2026-09-30
```

Example schedule object:

```json
{
  "day": "2026-09-08",
  "kind": "school",
  "cycle_day": 1,
  "title": "Day 1",
  "detail": "Art",
  "source": "generated"
}
```

The `/api/v1/` namespace is intended to become a stable public integration contract.

## Optional MQTT / Home Assistant Discovery

Set:

```dotenv
SCD_MQTT_HOST=192.168.1.10
SCD_MQTT_PORT=1883
SCD_MQTT_USERNAME=
SCD_MQTT_PASSWORD=
```

When enabled, schedule rebuilds publish retained Home Assistant Discovery/state for:

```text
Today
Tomorrow
Next School Day
```

MQTT failures are intentionally isolated from the core application. A broker outage cannot prevent schedule generation or use of the standalone calendar.

See [`HOME_ASSISTANT_OPTIONAL_INTEGRATION.md`](HOME_ASSISTANT_OPTIONAL_INTEGRATION.md).

## Optional direct Home Assistant adapter

For legacy migration or direct HA-calendar publishing only:

```dotenv
SCD_HA_URL=http://homeassistant.local:8123
SCD_HA_TOKEN=<long-lived-access-token>
```

This enables:

- one-click import of the old HA Helpers;
- discovery of HA calendars;
- optional publication of a copy of the cycle schedule into an HA calendar.

Home Assistant remains non-authoritative.

## Environment file

Minimal standalone `.env`:

```dotenv
SCD_DATABASE_PATH=./data/school_cycle_days.sqlite3
SCD_HOST=0.0.0.0
SCD_PORT=8088
```

Everything else is optional.

See `.env.example` for integration settings.

## Project layout

```text
standalone_app/
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── README.md
├── ICS_IMPORT_GUIDE.md
├── HOME_ASSISTANT_OPTIONAL_INTEGRATION.md
├── PRODUCT_ARCHITECTURE_AND_DISTRIBUTION.md
├── school_cycle_days/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── ha_client.py
│   ├── ics_import.py
│   ├── main.py
│   ├── mqtt_adapter.py
│   ├── schedule.py
│   └── service.py
├── templates/
│   └── index.html
└── tests/
    ├── test_ics_import.py
    ├── test_schedule.py
    └── test_service.py
```

## Development reload behavior

Run:

```bash
uvicorn school_cycle_days.main:app --reload
```

Python changes restart the standalone application automatically.

Home Assistant does not need to restart.

HTML template changes generally require only a browser refresh.

Environment-variable changes require restarting the standalone process.

## Tests

```bash
python -m compileall school_cycle_days tests
pytest -q
```

The core schedule and ICS-import tests are designed to run without Home Assistant.

## Public distribution direction

The target is a distributable self-hosted application, not a personal HA script.

Before a general v1.0 release, the major remaining productization items are:

- first-run onboarding wizard;
- authentication / Internet-exposure security;
- CSRF protection;
- integration-settings UI;
- backup/restore;
- database schema migrations;
- automated Docker release pipeline;
- versioned release artifacts;
- broader integration/API tests;
- configurable cycle length;
- import preview/review UI.

See [`PRODUCT_ARCHITECTURE_AND_DISTRIBUTION.md`](PRODUCT_ARCHITECTURE_AND_DISTRIBUTION.md) for the detailed roadmap and release criteria.

## Current migration status

The earlier Home Assistant-native custom integration remains in the parent branch/folder as a migration/reference implementation while the standalone application is proven.

It is no longer the preferred runtime.

The long-term identity is:

> **School Cycle Days is a standalone school-calendar application with optional integrations.**
