# School Cycle Days — Standalone Migration Guide

## Purpose

This guide describes the current migration path from the original AppDaemon implementation to the final standalone product architecture.

The end state is:

> School Cycle Days runs independently, owns its own schedule and UI, and exposes optional outputs/integrations such as ICS, REST, MQTT, and Home Assistant.

Home Assistant is **not** required for ordinary operation.

---

# Architecture history

## 1. Original AppDaemon implementation

```text
HA Helpers
   |
   v
AppDaemon
   |
   v
Home Assistant calendar / .ics files
```

Problems:

- state spread across HA Helpers and AppDaemon;
- direct `.ics` manipulation;
- difficult local development;
- application lifecycle tied to HA/AppDaemon;
- destructive whole-calendar cleanup patterns;
- poor portability for non-HA users.

## 2. Interim HA-native custom integration

```text
HA native entities
   |
   v
School Cycle Days custom integration
   |
   v
HA CalendarEntity
```

This removed AppDaemon and improved event deletion and UI integration, but the application still ran inside HA and required HA restarts for code changes.

That implementation remains in the branch for migration/reference only.

## 3. Intermediate remote-HA standalone design

The first standalone rewrite moved the Python application outside HA but still treated the HA calendar as the authoritative schedule destination.

That was an improvement, but still made HA a practical dependency.

## 4. Final standalone product design

```text
School Cycle Days
├── web calendar
├── SQLite
├── schedule engine
├── ICS import/cleanup
├── /calendar.ics
└── /api/v1/*
      |
      +-- optional MQTT Discovery
      +-- optional direct HA adapter
```

The SQLite `schedule_days` table is authoritative.

External calendars and automation systems consume or receive copies of that schedule.

---

# What migrates from AppDaemon

The standalone product preserves the useful behavior while removing HA as the application database.

## School-year settings

Old:

```text
input_datetime.cycle_start_day
input_datetime.cycle_end_day
```

New:

```text
SQLite settings + standalone UI
```

## Cycle labels

Old:

```text
input_text.cycle_day_1 ... cycle_day_5
```

New:

```text
SQLite settings + standalone UI
```

## Starting day

Old:

```text
input_number.cycle_day_restart_day
```

New:

```text
starting_cycle_day
```

stored locally.

## Non-school days

Old:

```text
input_text.non_school_days attributes + JSON
```

New:

```text
non_school_days SQLite table
```

Sources are tracked, for example:

```text
manual
ics:district-calendar.ics
legacy-ha
```

## Holidays

Old state is replaced by the local `holiday_days` table.

## Generated schedule

Old:

```text
calendar events were effectively the output/state
```

New:

```text
schedule_days SQLite table
```

The web calendar, REST API, and ICS feed all read this same schedule.

---

# Migrating existing HA Helper values

If the old Helpers still exist, configure the optional HA adapter:

```dotenv
SCD_HA_URL=http://homeassistant.local:8123
SCD_HA_TOKEN=<long-lived-access-token>
```

Then use:

```text
Import old HA Helpers
```

The operation is read-only against those Helpers and copies available values into SQLite.

It can import:

- school-year start/end;
- Cycle Day 1–5 labels;
- starting day;
- legacy include toggles;
- stored non-school dates;
- stored holiday dates.

After import, the standalone database becomes authoritative.

Do not continue editing the HA Helpers and expect them to remain synchronized.

---

# Migrating district/school calendar data

The original repository included:

```text
apps/cycleDays/no_school_calendar.py
```

Its important behavior is now part of the standalone web application.

Upload an arbitrary `.ics` file.

The app keeps events whose summary begins with:

```text
No School
```

and converts them into local no-school dates.

It can also produce a cleaned `.ics` containing only those events.

See:

```text
standalone_app/ICS_IMPORT_GUIDE.md
```

---

# Cutover procedure

## Phase 1 — install standalone app

Run locally or with Docker without changing AppDaemon yet.

Pure standalone `.env`:

```dotenv
SCD_DATABASE_PATH=./data/school_cycle_days.sqlite3
SCD_HOST=0.0.0.0
SCD_PORT=8088
```

No HA values are required.

## Phase 2 — seed settings

Either:

- enter values in the standalone UI; or
- temporarily configure the HA adapter and use **Import old HA Helpers**.

## Phase 3 — import non-school data

Use one or more of:

- legacy Helper import;
- external `.ics` upload;
- manual date entry;
- state holiday loader.

## Phase 4 — validate local schedule

Use the built-in month calendar.

Verify a known range for:

- cycle sequence;
- weekends;
- holidays;
- known no-school dates;
- snow-day shifting;
- correct next school day.

Also inspect:

```text
/api/v1/today
/api/v1/schedule
/calendar.ics
```

## Phase 5 — add optional integrations

Only after the standalone schedule looks correct.

Options:

- MQTT Discovery;
- REST consumers;
- ICS subscriptions;
- direct HA calendar copy during transition.

## Phase 6 — disable AppDaemon

Once the standalone output is confirmed:

1. stop the AppDaemon School Cycle Days app;
2. stop using old command Helpers;
3. keep old Helpers temporarily for rollback/reference;
4. run standalone as the production authority.

## Phase 7 — retire old HA artifacts

After a stable period, remove obsolete Helpers/AppDaemon configuration if nothing else references them.

The earlier HA-native custom integration can also be archived/removed after standalone production use is proven.

---

# Home Assistant after migration

Home Assistant should consume the app rather than own it.

Preferred choices:

## MQTT Discovery

Produces HA-native sensors for:

```text
Today
Tomorrow
Next School Day
```

## REST

HA can poll:

```text
/api/v1/today
/api/v1/tomorrow
/api/v1/next-school-day
```

## ICS

Use:

```text
/calendar.ics
```

where a calendar consumer can subscribe to it.

## Direct HA calendar publishing

Retained as an optional compatibility/transition feature, not the recommended authoritative storage model.

See:

```text
standalone_app/HOME_ASSISTANT_OPTIONAL_INTEGRATION.md
```

---

# Rollback

During migration, do not immediately delete:

- AppDaemon code;
- old Helpers;
- existing calendar data.

If standalone testing exposes a problem, stop the standalone process and re-enable the existing AppDaemon workflow.

Because the new app stores its state separately in SQLite, rollback does not require destroying the old configuration.

---

# Development behavior

Standalone development:

```bash
uvicorn school_cycle_days.main:app --reload
```

Python changes reload the standalone process.

No Home Assistant restart is required.

Run validation with:

```bash
python -m compileall school_cycle_days tests
pytest -q
```

---

# Distribution migration

The current architecture is intentionally usable by people who do not run Home Assistant.

Before v1.0, the remaining migration from "developer application" to "distributed product" should add:

- first-run onboarding;
- authentication/security;
- backup/restore;
- schema migrations;
- integration settings UI;
- release Docker images;
- CI/release automation;
- import preview/review.

See:

```text
standalone_app/PRODUCT_ARCHITECTURE_AND_DISTRIBUTION.md
```

for the full release plan.

---

# Final invariant

After migration, the following must remain true:

> Turning Home Assistant off must not prevent School Cycle Days from displaying, recalculating, exporting, or serving its school calendar.

That is the architectural boundary going forward.
