# School Cycle Days — Product Architecture and Distribution Plan

## Product definition

School Cycle Days is now designed as a **standalone school-cycle calendar application**.

Home Assistant is an optional integration, not a prerequisite and not the application's database.

A user who does not use Home Assistant should still receive the complete product:

- a polished web calendar;
- school-year setup;
- configurable five-day cycle labels;
- manual non-school/snow days;
- state holiday generation;
- `.ics` import and cleanup;
- automatic cycle recalculation;
- a subscription-ready `.ics` calendar feed;
- a versioned JSON API;
- persistent SQLite storage.

The product boundary is therefore:

```text
Browser / mobile browser
          |
          v
+-----------------------------------------+
| School Cycle Days                       |
|                                         |
| Web calendar UI                         |
| Settings / imports / corrections        |
| Cycle engine                            |
| SQLite                                  |
| REST API                                |
| ICS feed                                |
+--------------------+--------------------+
                     |
            optional integrations
                     |
       +-------------+-------------+
       |                           |
       v                           v
     MQTT                   Home Assistant REST/WS
   Discovery                 migration/publish adapter
```

The standalone schedule in SQLite is authoritative.

---

# Current v0.3 architecture

## Core modules

### `database.py`

Owns local persistence.

Tables:

```text
settings
non_school_days
holiday_days
schedule_days
```

`schedule_days` is the authoritative generated calendar.

No external service owns or is required to reconstruct this state.

### `schedule.py`

Pure standalone scheduling engine.

Responsibilities:

- validate the configured school-year range;
- apply five cycle-day labels;
- apply the selected starting cycle day;
- block manually entered/imported non-school dates;
- block holidays;
- skip weekends when advancing the cycle;
- generate one row for every configured calendar date;
- expose today / next-school-day queries;
- construct month-view data;
- export the generated schedule as iCalendar.

There is no Home Assistant dependency in this module.

### `ics_import.py`

Imports arbitrary external `.ics` school calendars.

The compatibility rule from the original project is preserved:

```text
SUMMARY starts with "No School"
```

Matching events become standalone non-school dates.

The cleaner also produces a standalone cleaned `.ics` containing only matching events.

### `main.py`

FastAPI application and web UI routes.

The main UI is calendar-first rather than integration-first.

### `mqtt_adapter.py`

Optional output adapter.

When MQTT is configured, it publishes Home Assistant MQTT Discovery for:

```text
Today
Tomorrow
Next School Day
```

with retained JSON state/attributes.

A broker failure must never prevent local calendar generation.

### `ha_client.py` / `service.py`

These now represent optional compatibility/integration functionality.

They are retained for:

- one-click migration from legacy HA Helpers;
- optional direct publishing of a copy of the schedule into an HA calendar;
- historical compatibility during migration.

They are not the core application model.

---

# Built-in standalone calendar

The first page of the application is now the product's calendar.

It provides:

- month navigation;
- a Today summary;
- a Next School Day summary;
- visual school-day cards;
- cycle day number and label;
- No School highlighting;
- weekend styling;
- current-day highlighting;
- responsive/mobile layout;
- light/dark mode based on the browser preference.

The calendar reads directly from `schedule_days`.

That is important: the visual calendar is not reading Home Assistant, Google Calendar, or an exported ICS file. It is rendering the application's own authoritative state.

---

# Always-available external outputs

These require no third-party account or integration.

## ICS subscription

```text
GET /calendar.ics
```

A user can subscribe to this URL from compatible calendar applications or download it directly.

The generated ICS includes deterministic UIDs:

```text
school-cycle-days-YYYY-MM-DD@local
```

This means School Cycle Days can be the authoritative calendar while Apple Calendar, Outlook, Thunderbird, Home Assistant, or another consumer merely displays it.

## Health API

```text
GET /api/v1/health
```

Reports standalone health and whether optional integrations are configured.

## Today

```text
GET /api/v1/today
```

Example:

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

## Tomorrow

```text
GET /api/v1/tomorrow
```

Uses the same schema.

## Next school day

```text
GET /api/v1/next-school-day
```

Returns the next row with:

```text
kind = school
```

## Schedule range

```text
GET /api/v1/schedule
```

Optional query arguments:

```text
?start=2026-09-01&end=2026-09-30
```

Dates use ISO `YYYY-MM-DD`.

These `/api/v1/` routes should be treated as the first versioned public API contract.

---

# Home Assistant should consume the app, not own it

There are three supported integration strategies.

## 1. MQTT Discovery — preferred for HA users with MQTT

Configure:

```dotenv
SCD_MQTT_HOST=192.168.1.10
SCD_MQTT_PORT=1883
SCD_MQTT_USERNAME=...
SCD_MQTT_PASSWORD=...
```

The app publishes Home Assistant Discovery and retained state for the primary schedule sensors.

This is the cleanest HA integration because it requires no School Cycle Days custom component and no YAML-defined REST sensors.

## 2. REST API — generic external-sensor integration

HA or any automation platform can poll `/api/v1/today`, `/api/v1/tomorrow`, etc.

The REST API is deliberately platform-neutral.

## 3. Legacy/direct HA adapter

Optional environment variables:

```dotenv
SCD_HA_URL=http://homeassistant.local:8123
SCD_HA_TOKEN=...
```

This adapter exists primarily for migration and direct HA calendar publishing.

It should not become the primary architecture again.

---

# Distribution goals

The intended public product should support at least these deployment profiles.

## Docker / Docker Compose

This should be the primary self-hosted distribution format.

Benefits:

- consistent Python/runtime version;
- one persistent `/data` volume;
- simple upgrades;
- easy NAS/server/Raspberry Pi deployment;
- straightforward reverse-proxy support.

Target user experience:

```bash
docker compose up -d
```

Then browse to:

```text
http://server:8088
```

For public distribution, publish signed/versioned images to GHCR:

```text
ghcr.io/<owner>/school-cycle-days:<version>
ghcr.io/<owner>/school-cycle-days:latest
```

Do not require end users to build the image themselves once releases begin.

## Python package

Keep `pyproject.toml` valid so advanced users can run:

```bash
pip install school-cycle-days
```

A console entry point should eventually be added:

```text
school-cycle-days
```

which starts the server or launches a setup wizard.

## Windows/macOS/Linux desktop packaging — later

A future desktop wrapper could use:

- Tauri;
- PyInstaller + browser launch;
- another lightweight shell.

This is lower priority than a robust Docker release.

## Hosted/SaaS possibility — later

The current single-database design is for one household/school configuration.

Do not simply expose the current app as multi-user SaaS.

A hosted service would require:

- accounts;
- tenant isolation;
- per-user calendars;
- authentication;
- authorization;
- database schema changes;
- encrypted integration credentials;
- email/account recovery;
- operational monitoring.

Treat SaaS as a separate architecture milestone.

---

# First-run onboarding required before public release

Environment-file editing is acceptable during development but should not be the normal public-user workflow.

Before a general release, add a first-run setup wizard.

Recommended sequence:

1. Welcome / what the app does.
2. School year start and end.
3. Cycle length / labels (initially five, eventually configurable).
4. Starting cycle day.
5. State/region holiday preference.
6. Optional `.ics` school-calendar upload.
7. Preview generated calendar.
8. Optional integrations:
   - MQTT;
   - Home Assistant;
   - future external calendars.
9. Finish and open calendar.

The setup wizard should write ordinary application settings into SQLite.

Secrets should not be stored in plain settings rows without a deliberate credential-storage design.

---

# Authentication and security before distribution

The current development build assumes a trusted LAN/VPN.

That is appropriate for local testing but insufficient if users expose the application to the Internet.

Before recommending public exposure, implement one of:

- built-in local authentication;
- trusted reverse-proxy authentication;
- OIDC/OAuth integration.

At minimum, the public release should protect mutating routes such as:

```text
/settings
/ics/process
/non-school-days/*
/holidays/*
/calendar/rebuild
/integrations/*
```

Also add CSRF protection for browser forms before an Internet-facing release.

The read-only ICS/API surfaces may eventually support separate access tokens so a calendar client can subscribe without receiving administrator credentials.

Recommended eventual model:

```text
/admin UI             -> authenticated session
/api/v1/* read-only   -> optional API token / local access policy
/calendar.ics         -> optional subscription token
```

---

# Database migrations

Public releases must not rely on ad-hoc `CREATE TABLE IF NOT EXISTS` forever.

Before v1.0 add a schema migration mechanism, for example Alembic or a small explicit migration runner.

Every release that changes schema should:

1. identify current schema version;
2. back up or migrate transactionally;
3. apply ordered migrations;
4. fail safely without destroying the old database.

Add a metadata table such as:

```text
schema_version
```

before multiple external users depend on the database.

---

# Backup/export

Before public release, provide UI-accessible backup/export.

At minimum:

- download a JSON configuration/data backup;
- download the SQLite database;
- export the generated ICS;
- restore from a supported backup format.

Docker documentation should explicitly state that `/data` must be persistent.

---

# Release engineering

Recommended GitHub release pipeline:

```text
push version tag
      |
      +--> run tests/lint
      +--> build Python distribution
      +--> build multi-arch Docker image
      +--> vulnerability scan
      +--> publish GHCR image
      +--> create GitHub Release
      +--> attach changelog
```

Target Docker platforms:

```text
linux/amd64
linux/arm64
```

That covers common PCs/servers and modern Raspberry Pi/NAS deployments.

---

# CI gates before v1.0

Require tests for:

- five-day cycle advancement;
- weekend skipping;
- holiday skipping;
- manual non-school days;
- `.ics` imported no-school dates;
- multi-day ICS events;
- malformed trailing VEVENT repair;
- schedule rebuild idempotence;
- ICS output validity;
- REST endpoint schemas;
- month-grid rendering;
- database migration;
- optional MQTT behavior with a mocked broker/client;
- HA adapters with mocked HA APIs.

The standalone core tests must run without Home Assistant.

---

# Product UX roadmap

## High priority

1. First-run wizard.
2. Calendar event click/details drawer.
3. Preview changes before applying a large import.
4. Import review screen with checkboxes for matched ICS events.
5. Automatic snow-day workflow: add closure and show how future cycle days shift.
6. Backup/restore UI.
7. Integration settings UI instead of environment variables.
8. Authentication/security layer.

## Medium priority

1. Week/agenda views.
2. Print-friendly school-year calendar.
3. Configurable cycle length instead of hard-coded five days.
4. Custom colors per cycle day.
5. Notes/special events that do not affect cycle progression.
6. Multiple children/schools/calendars in one instance.
7. PWA install support and offline read-only calendar cache.
8. Locale/date-format support.

## Later

1. Google Calendar adapter.
2. Microsoft/Outlook adapter.
3. CalDAV publishing.
4. Push notifications.
5. Native mobile wrapper if demand justifies it.
6. Hosted multi-user product.

---

# Versioning direction

The current standalone rewrite is effectively a pre-release product line.

Suggested milestones:

```text
0.3  standalone authoritative calendar + REST + ICS + optional MQTT/HA
0.4  onboarding + calendar UX refinement + import preview
0.5  auth + backup/restore + integration settings UI
0.6  database migrations + stronger automated tests + release pipeline
0.7  configurable cycle length / multi-calendar groundwork
1.0  documented, migration-safe, distributable self-hosted release
```

Do not call the project 1.0 solely because the core calendar works. A distributable 1.0 should have a safe upgrade path, backup/restore, onboarding, authentication guidance, and tested release artifacts.

---

# Architectural rule going forward

New features should answer this question:

> Would this still work for a user who has no Home Assistant installation?

If the answer is no, the feature belongs in an adapter/integration layer, not in the core calendar.

The final product identity is:

> **School Cycle Days is a standalone school-calendar application with optional integrations.**

Not:

> a Home Assistant calendar utility.
