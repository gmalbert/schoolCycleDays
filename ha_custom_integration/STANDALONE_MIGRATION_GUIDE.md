# School Cycle Days — Standalone Migration Guide

## Purpose

This document describes the architectural migration from the original AppDaemon application, through the interim Home Assistant custom-integration prototype, to the preferred standalone application.

The end-state goal is:

> School Cycle Days runs as its own application, has its own UI and persistence, and connects to Home Assistant remotely only for calendar operations.

Routine operation must remain UI-first. Editing Python, YAML, Home Assistant Helpers, or calendar files is not part of the normal workflow.

---

## Architecture history

### 1. Original AppDaemon application

```text
Home Assistant Helpers
        |
        v
AppDaemon CycleDays
        |
        | REST + bearer token
        v
Home Assistant
        |
        v
Local Calendar .ics
```

Problems:

- application state spread across HA Helpers and AppDaemon-created attributes;
- bearer-token REST calls back into the same HA instance;
- AppDaemon development/deployment friction;
- direct `.ics` manipulation;
- whole-calendar deletion to correct cycle entries;
- UI and business logic tightly coupled to Home Assistant entities.

### 2. Interim HA-native custom integration

```text
HA native Date/Text/Number/Switch/Select/Button entities
        |
        v
school_cycle_days custom integration
        |
        v
HA CalendarEntity
```

Improvements:

- no AppDaemon;
- no self-REST calls;
- native Home Assistant UI entities;
- application persistence through HA Store;
- direct per-event deletion by UID;
- selective regeneration.

Remaining drawback:

- every Python development change still requires Home Assistant to reload/restart;
- application lifecycle is tied to HA;
- UI is constrained by generic HA entity controls;
- application code runs inside HA's process and API lifecycle.

### 3. Preferred standalone architecture

```text
Standalone FastAPI application
├── purpose-built web UI
├── cycle engine
├── SQLite
├── non-school days
├── holidays
└── HA client
        |
        | REST + WebSocket
        v
Home Assistant
        |
        v
calendar.* provider
```

This is now the target architecture.

---

# Why a custom HA bridge is not required

The initial standalone design assumed a small Home Assistant custom integration would still be necessary for calendar deletion.

That assumption was corrected after reviewing current Home Assistant Core.

Current HA exposes a built-in authenticated WebSocket command:

```text
calendar/event/delete
```

and its calendar REST endpoint returns event details, including `uid` when provided by the calendar entity.

The standalone app can therefore:

1. retrieve events remotely;
2. identify School Cycle Days events;
3. obtain their UIDs;
4. delete individual events through Home Assistant's own WebSocket API.

There is no need for a School Cycle Days bridge integration on current HA.

This is preferable because it eliminates another installation artifact and keeps School Cycle Days entirely outside Home Assistant.

---

# Component ownership after migration

| Concern | Original AppDaemon | HA-native prototype | Standalone target |
|---|---|---|---|
| UI | HA Helpers/dashboard | HA entities/dashboard | Standalone web UI |
| School-year settings | HA Helpers | HA native entities | SQLite + web form |
| Cycle labels | HA `input_text` | HA `text` entities | SQLite + web form |
| Non-school days | helper attributes + JSON | HA Store | SQLite |
| Holidays | helper attributes + JSON | HA Store | SQLite |
| Business logic | AppDaemon | HA custom integration | standalone service layer |
| Calendar list | `.ics` scan / HA | HA | HA REST `/api/calendars` |
| Create event | REST self-call | HA internal service | HA REST service call |
| Read events | `.ics` / HA | HA entity API | HA calendar REST endpoint |
| Delete event | delete `.ics` | `async_delete_event()` | HA WebSocket `calendar/event/delete` |
| App restart | AppDaemon | HA restart/reload | standalone restart only |
| Hot reload | awkward | no | `uvicorn --reload` |

---

# Files from the HA-native prototype

The branch intentionally still contains:

```text
ha_custom_integration/custom_components/school_cycle_days/
```

Do not delete this yet.

It is useful for:

- behavior comparison;
- migration reference;
- fallback testing;
- mapping old HA Helper names;
- verifying logic parity.

It is no longer the preferred runtime.

Once standalone production use has been validated, a later cleanup can move it to something like:

```text
legacy/ha_native_prototype/
```

or remove it entirely.

That cleanup should happen only after the standalone app has passed the production-calendar migration tests.

---

# Standalone application files

Primary code:

```text
ha_custom_integration/standalone_app/
```

Important modules:

```text
school_cycle_days/config.py
```

Environment configuration. The HA token lives outside the database and outside Git.

```text
school_cycle_days/database.py
```

SQLite persistence for settings, manual non-school days, and holidays.

```text
school_cycle_days/ha_client.py
```

Home Assistant boundary. This is where REST/WebSocket implementation details live.

```text
school_cycle_days/service.py
```

Business logic. This module should remain usable independently of FastAPI.

```text
school_cycle_days/main.py
```

FastAPI/UI routes.

```text
templates/index.html
```

Current purpose-built browser UI.

---

# Remote HA API contract

## Connection test

```http
GET /api/
Authorization: Bearer <token>
```

## HA configuration / timezone

```http
GET /api/config
```

The standalone app uses HA's configured timezone when constructing calendar query ranges.

## Calendar discovery

```http
GET /api/calendars
```

This populates the UI calendar selector.

## Event retrieval

```http
GET /api/calendars/<entity_id>?start=<timestamp>&end=<timestamp>
```

Used before selective deletion/regeneration.

## Event creation

```http
POST /api/services/calendar/create_event
```

The app sends all-day start/end dates, summary, description, and the selected `calendar.*` entity.

## Event deletion

Connect:

```text
ws://HA/api/websocket
```

or:

```text
wss://HA/api/websocket
```

Authenticate:

```json
{
  "type": "auth",
  "access_token": "..."
}
```

Delete:

```json
{
  "id": 1,
  "type": "calendar/event/delete",
  "entity_id": "calendar.school",
  "uid": "EVENT_UID"
}
```

---

# Event ownership and safe deletion

The standalone app marks newly-created events with:

```text
[school_cycle_days]
```

inside the event description.

Selective deletion accepts an event as app-owned when:

1. the ownership marker exists; or
2. it matches the legacy AppDaemon `Day N (...)` summary pattern; or
3. it is a recognized legacy `No School` event.

The app must never delete an arbitrary event just because it occurs inside the requested regeneration range.

This is the critical safety property of the new design.

---

# Migration plan

## Phase 1 — standalone test deployment

Keep production AppDaemon untouched.

Run the standalone app against:

```text
calendar.school_cycle_test
```

Test:

- connectivity;
- UI settings;
- persistence;
- cycle generation;
- manual non-school days;
- holidays;
- event UID retrieval;
- single-date deletion;
- partial regeneration;
- unrelated event preservation.

## Phase 2 — compare behavior

For a known short date range, compare the generated result from AppDaemon with the standalone engine.

Confirm:

- same weekday advancement;
- same cycle order;
- same handling of non-school days;
- same holiday behavior you actually want to preserve;
- same starting-day behavior.

Do not preserve legacy bugs merely for parity.

## Phase 3 — seed standalone settings

Enter the current production values in the standalone UI:

- production calendar entity;
- school-year range;
- Cycle Day 1–5 labels;
- restart/starting day;
- state;
- non-school dates;
- holiday data.

A later enhancement can automate importing these values from HA Helpers, but manual UI entry is acceptable during the first standalone validation because it is a one-time migration rather than ongoing maintenance.

## Phase 4 — production calendar read-only verification

Before creating/deleting anything, select the production calendar and verify the app can list calendars/events and identify which existing events it considers generated.

A future UI improvement should add a dry-run/preview mode before production cutover.

## Phase 5 — cutover

1. stop/disable AppDaemon CycleDays;
2. ensure HA-native prototype is not active against the same calendar;
3. back up the current calendar if desired;
4. use standalone selective regeneration on a limited production range;
5. verify unrelated events remain;
6. extend to the remainder of the school year.

## Phase 6 — retire old HA Helpers

Only after the standalone app has been stable should the old School Cycle Days Helpers/buttons be removed.

They are no longer part of the target architecture.

---

# Development workflow after migration

This is one of the largest improvements.

## Python development

Run:

```bash
uvicorn school_cycle_days.main:app --reload
```

Edit:

```text
main.py
service.py
ha_client.py
database.py
config.py
```

Uvicorn detects Python-file changes and restarts the standalone process.

**Home Assistant does not need to restart.**

## HTML/UI changes

Edit:

```text
templates/index.html
```

Refresh the browser.

## Environment changes

Edit:

```text
.env
```

Then restart the standalone process because environment settings are cached at process startup.

## Docker deployment

After code updates:

```bash
docker compose up -d --build
```

Again, no HA restart.

---

# Token/security migration

The standalone app needs a Home Assistant credential.

For this private application, use a dedicated Long-Lived Access Token supplied as:

```text
SCD_HA_TOKEN
```

Do not store it in SQLite or commit it.

If the app is later distributed to other users, replace this with HA OAuth rather than instructing general users to paste long-lived tokens.

---

# Features deliberately not carried forward

The target architecture does not need:

- AppDaemon `apps.yaml` configuration;
- AppDaemon module/class declaration;
- bearer-token values stored in AppDaemon secrets specifically for self-calls;
- `create_event_url` configuration;
- `calendar_event_url` configuration;
- physical calendar path for normal operation;
- `.ics` deletion to clear events;
- HA Helpers as the application database;
- custom attributes attached to `input_text` entities;
- generic HA command-button Helpers for routine app actions.

---

# Recommended future standalone enhancements

After the initial migration works, the highest-value improvements are:

1. **Dry-run/preview regeneration** — show exactly what will be deleted/created before applying.
2. **Automatic snow-day shift** — choose a snow day and have the app determine the correct cycle continuation automatically.
3. **Calendar preview/table** — show generated schedule inside the standalone UI before pushing to HA.
4. **Import existing HA Helper values** — one-click migration from the legacy configuration.
5. **Audit log** — record each create/delete/regenerate operation locally.
6. **Database backup/export** — simple JSON or SQLite backup from the UI.
7. **Authentication for the standalone UI** if exposed outside a trusted LAN/VPN.
8. **OAuth** if the app becomes generally distributed.
9. **Health/status page** for HA connectivity and token permissions.
10. **API tests against a disposable HA calendar** in CI or a local test HA instance.

---

# Final target

The final operating model should be:

```text
Browser
   |
   v
School Cycle Days web app
   |
   +-- local SQLite state
   +-- school/calendar business logic
   |
   +---- authenticated HA REST/WebSocket ----> Home Assistant calendar
```

No AppDaemon.

No mandatory School Cycle Days custom integration inside HA.

No routine code/YAML editing.

No whole-calendar deletion.

No Home Assistant restart when developing the application.
