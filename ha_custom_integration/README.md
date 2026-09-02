# School Cycle Days — Rewrite / Migration Work

This folder contains the replacement work for the original AppDaemon School Cycle Days application. The existing `apps/` tree has not been overwritten.

## Final architectural direction

The **primary implementation is the standalone application** under:

```text
ha_custom_integration/standalone_app/
```

It does **not require Home Assistant**.

The standalone app owns:

- its web UI;
- the authoritative school-cycle schedule;
- SQLite persistence;
- school-year configuration;
- cycle-day labels;
- non-school/snow days;
- holiday generation;
- external `.ics` import/cleanup;
- a polished built-in month calendar;
- an ICS subscription feed;
- a versioned REST API.

Home Assistant is now only an optional integration target/consumer.

```text
                 +-----------------------------+
                 | School Cycle Days           |
                 |                             |
Browser -------->| standalone calendar UI      |
                 | SQLite schedule             |
                 | cycle engine                |
                 | ICS import                  |
                 +-------------+---------------+
                               |
                +--------------+--------------+
                |              |              |
                v              v              v
           /calendar.ics   /api/v1/*      optional MQTT
                                           Discovery
                                                |
                                                v
                                         Home Assistant
```

The direct HA REST/WebSocket adapter remains only for legacy migration and optional calendar-copy behavior.

## Why this is preferable

### No HA dependency

Someone can use School Cycle Days without installing or knowing about Home Assistant.

### Better development

Run:

```bash
uvicorn school_cycle_days.main:app --reload
```

Python changes reload the standalone process without restarting Home Assistant.

### Better calendar ownership

The schedule exists once, in the standalone database.

Consumers subscribe to/read that schedule instead of School Cycle Days creating, finding, deleting, and recreating external calendar records as its primary storage model.

### Better distribution path

The product can be distributed as a normal self-hosted web application through Docker/GHCR, with Home Assistant as one optional integration among several.

## Standalone calendar UI

The main page is now a purpose-built calendar with:

- month navigation;
- Today summary;
- Next School Day summary;
- visual cycle-day cards;
- No School highlighting;
- weekend treatment;
- current-day highlighting;
- responsive/mobile layout;
- browser light/dark mode.

The UI reads directly from the authoritative `schedule_days` SQLite table.

## External `.ics` import

The standalone UI carries forward the original `apps/cycleDays/no_school_calendar.py` behavior.

Users can upload any `.ics` file. It does not need to come from Home Assistant.

The importer:

1. extracts `VEVENT` blocks;
2. keeps events whose `SUMMARY` starts with `No School`;
3. ignores unrelated events;
4. repairs a final event missing `END:VEVENT`;
5. expands multi-day closures into covered dates;
6. deduplicates dates;
7. imports them as non-school days or downloads a cleaned `.ics`.

See:

```text
standalone_app/ICS_IMPORT_GUIDE.md
```

## Built-in outputs

### ICS calendar

```text
GET /calendar.ics
```

### REST API

```text
GET /api/v1/health
GET /api/v1/today
GET /api/v1/tomorrow
GET /api/v1/next-school-day
GET /api/v1/schedule
```

These are platform-neutral outputs.

## Optional Home Assistant integration

### MQTT Discovery

Preferred when the user already has an MQTT broker.

The app can publish Home Assistant Discovery/state for:

```text
Today
Tomorrow
Next School Day
```

### REST sensors

HA or another automation platform can poll the `/api/v1/*` endpoints.

### ICS

HA or any compatible calendar client can consume `/calendar.ics`.

### Direct HA adapter

Still available for:

- importing old HA Helper values;
- optionally publishing a copy to an HA calendar during transition.

It is not authoritative.

See:

```text
standalone_app/HOME_ASSISTANT_OPTIONAL_INTEGRATION.md
```

## Directory layout

```text
ha_custom_integration/
├── README.md
├── APPDAEMON_COMPATIBILITY_AUDIT.md
├── LOCAL_TESTING_GUIDE.md
├── STANDALONE_MIGRATION_GUIDE.md
├── STANDALONE_TESTING_GUIDE.md
│
├── standalone_app/                    # PRIMARY PRODUCT
│   ├── README.md
│   ├── PRODUCT_ARCHITECTURE_AND_DISTRIBUTION.md
│   ├── HOME_ASSISTANT_OPTIONAL_INTEGRATION.md
│   ├── ICS_IMPORT_GUIDE.md
│   ├── .env.example
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── pyproject.toml
│   ├── school_cycle_days/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── ha_client.py
│   │   ├── ics_import.py
│   │   ├── main.py
│   │   ├── mqtt_adapter.py
│   │   ├── schedule.py
│   │   └── service.py
│   ├── templates/
│   │   └── index.html
│   └── tests/
│       ├── test_ics_import.py
│       ├── test_schedule.py
│       └── test_service.py
│
└── custom_components/                 # EARLIER HA-NATIVE PROTOTYPE
    └── school_cycle_days/
```

The earlier custom integration remains for migration/reference until the standalone version is proven, but it is no longer the intended runtime.

## Quick start

```bash
cd ha_custom_integration/standalone_app
python -m venv .venv
source .venv/Scripts/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn school_cycle_days.main:app --reload --host 0.0.0.0 --port 8088
```

Then browse to:

```text
http://localhost:8088
```

A pure standalone install needs no HA or MQTT values in `.env`.

## Docker

```bash
docker compose up -d --build
```

Compose defaults all integration variables to blank, so this also works as a standalone deployment.

## Public-distribution roadmap

The application is now structured toward eventual distribution to other users.

Before a general v1.0 release, the major remaining productization work is:

- first-run onboarding wizard;
- authentication/security and CSRF protection;
- integration settings in the UI;
- backup/restore;
- database schema migrations;
- versioned Docker/GHCR releases;
- stronger CI/release automation;
- import preview/review;
- configurable cycle length;
- broader API and UI tests.

See:

```text
standalone_app/PRODUCT_ARCHITECTURE_AND_DISTRIBUTION.md
```

for the detailed product/release plan.

## Development validation

Run locally:

```bash
python -m compileall school_cycle_days tests
pytest -q
```

The core schedule/ICS tests are explicitly designed to run without Home Assistant.

## Architectural invariant

Going forward, every core feature should satisfy:

> Would this still work for a user who has no Home Assistant installation?

If not, it belongs in an optional adapter layer.
