# School Cycle Days — Standalone Application

School Cycle Days is a **standalone rotating school-calendar application**. Home Assistant is optional.

The authoritative schedule lives in SQLite and is rendered directly by the application. External calendars, MQTT, Home Assistant, Google Calendar, Outlook and webhooks are integrations around that core; none owns the schedule.

## v0.4 product capabilities

- polished standalone calendar UI;
- arbitrary-length rotating schedules (A/B, 5-day, 6-day, etc.);
- automatic snow/emergency-day cycle shifting;
- dry-run schedule preview;
- clickable per-date overrides;
- recurring closure rules;
- multiple school/child profiles;
- aggregate household view;
- public read-only share links;
- private tokenized ICS subscription feeds;
- external `.ics` upload cleanup and selective review/import;
- scheduled district ICS URL subscriptions with include/exclude matching rules;
- state holiday generation;
- conflict/validation warnings;
- audit history and snapshot-based Undo;
- optional local authentication;
- mobile/PWA shell;
- REST API;
- MQTT/Home Assistant Discovery;
- optional direct Home Assistant migration/publishing;
- diff-based Google Calendar and Microsoft Outlook synchronization;
- webhook and ntfy notifications;
- profile JSON export/backup.

See [`FEATURE_IMPLEMENTATION_MATRIX.md`](FEATURE_IMPLEMENTATION_MATRIX.md) for the feature-by-feature map to routes, storage, tests and known public-release hardening work.

## Core architecture

```text
profiles + cycles + closures + holidays + rules + overrides
                         |
                         v
                 ScheduleService
                         |
                         v
                 profile_schedule
                         |
       +-----------------+------------------+
       |                 |                  |
 standalone UI       ICS / REST       optional adapters
                                        MQTT / HA /
                                   Google / Outlook /
                                  webhook / ntfy
```

Home Assistant can be completely absent.

## Quick start

From `ha_custom_integration/standalone_app/`:

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
pip install -e '.[dev]'
cp .env.example .env
uvicorn school_cycle_days.product_app:app --reload --host 0.0.0.0 --port 8088
```

Open:

```text
http://localhost:8088
```

Useful product pages:

```text
/                    default standalone month calendar
/household           all configured profiles / add another school
/profile/<id>         full profile calendar and management UI
/login                first admin setup / login when auth is enabled
```

## Docker

```bash
docker compose up -d --build
```

The application listens on port `8088` and stores SQLite data under `/data` in the container.

Docker now launches:

```text
school_cycle_days.product_app:app
```

not the earlier compatibility-only `main:app` entry point.

## Multiple profiles and arbitrary cycles

Each school/child is a `calendar_profile`. Every profile owns its own:

- school-year dates;
- timezone/state;
- ordered `cycle_definitions`;
- manually entered and imported no-school days;
- holidays;
- per-date overrides;
- recurring closure rules;
- generated schedule;
- external sources;
- publication mappings;
- notification targets;
- audit/snapshot history;
- share/ICS tokens.

The cycle is not hard-coded to five days. Five entries are only the migration/default starting point.

## Snow days and corrections

From a profile page:

- **Snow / emergency closure** adds the closure and rebuilds the schedule. The missed cycle position moves to the next eligible school day automatically.
- **Date override** can force a no-school day or force an explicit cycle position/title/note.
- **Recurring closure** supports weekday rules, optional date ranges, month filters and nth-occurrence filters.
- **Undo** restores the latest saved snapshot for supported mutation types and rebuilds.

## Dry-run and validation

```text
GET /api/v1/profiles/<profile>/preview
GET /api/v1/profiles/<profile>/validation
```

Preview calculates candidate rows without replacing `profile_schedule`. Validation reports configuration/override conflicts.

## External `.ics` upload

The historical `no_school_calendar.py` behavior is preserved for upload compatibility:

```text
SUMMARY starts with "No School"
```

The profile workflow is safer than the old script:

1. upload the `.ics`;
2. parse/clean it;
3. display candidate dates;
4. select/deselect candidates;
5. confirm import;
6. rebuild the profile schedule.

The cleaner also repairs a trailing VEVENT missing `END:VEVENT`, expands multi-day events and skips malformed events rather than failing the entire file.

See [`ICS_IMPORT_GUIDE.md`](ICS_IMPORT_GUIDE.md).

## District ICS URL subscriptions

A profile can subscribe to an arbitrary external ICS URL.

Default include phrases:

```text
No School
School Closed
Vacation
Teacher Workday
```

Include/exclude lists are editable per source. Enabled sources refresh in a background loop controlled by:

```dotenv
SCD_SOURCE_REFRESH_SECONDS=21600
```

Manual refresh, pause/resume and removal controls are also available.

## Built-in calendar feeds

Legacy/default feed:

```text
GET /calendar.ics
```

Profile-specific private feed:

```text
GET /calendar/<slug>.ics?token=<profile_ics_token>
```

A profile can rotate its ICS token at any time, immediately invalidating the old URL.

## Public read-only sharing

Each profile has a separate read-only browser token:

```text
/share/<public_share_token>
```

This token is independent from the ICS token and can be rotated separately.

## Household view

```text
GET /household
```

Shows Today and Next School Day for every configured profile and provides the UI for creating another school/child profile.

## REST API

Stable namespace:

```text
GET /api/v1/health
GET /api/v1/today
GET /api/v1/tomorrow
GET /api/v1/next-school-day
GET /api/v1/schedule
GET /api/v1/profiles
GET /api/v1/profiles/<profile>/preview
GET /api/v1/profiles/<profile>/validation
GET /api/v1/profiles/<profile>/export
```

The profile export is a versioned JSON backup containing profile settings, cycle definitions, no-school dates, holidays, overrides, closure rules and schedule rows.

## Google Calendar and Outlook sync

External publishing is **diff based**.

`published_events` stores:

```text
profile_id
provider
local_day
external_event_id
content_hash
```

`PublicationSyncPlanner` partitions a sync into:

```text
create
update
delete
unchanged
```

Preview a publication diff:

```text
POST /profile/<profile>/publish/plan
```

Execution endpoints:

```text
POST /profile/<profile>/publish/google
POST /profile/<profile>/publish/outlook
```

The current UI accepts an already-issued OAuth access token transiently and does **not** store it. For a polished public release, add first-class OAuth authorization callbacks so ordinary users never paste access tokens.

## Notifications

Current targets:

- generic JSON webhook;
- ntfy.

The background notification loop checks hourly and sends at most one persisted “tomorrow” reminder per profile/target/day. Payloads include tomorrow and Next School Day data.

## Optional MQTT / Home Assistant Discovery

Configure:

```dotenv
SCD_MQTT_HOST=
SCD_MQTT_PORT=1883
SCD_MQTT_USERNAME=
SCD_MQTT_PASSWORD=
```

When configured, the app publishes retained discovery/state for:

```text
Today
Tomorrow
Next School Day
```

MQTT failures are isolated from the local calendar.

See [`HOME_ASSISTANT_OPTIONAL_INTEGRATION.md`](HOME_ASSISTANT_OPTIONAL_INTEGRATION.md).

## Optional direct Home Assistant adapter

For legacy migration or optional HA-calendar publication:

```dotenv
SCD_HA_URL=http://homeassistant.local:8123
SCD_HA_TOKEN=<long-lived-access-token>
```

This can:

- import values from the original HA Helpers;
- discover HA calendars;
- publish a copy into an HA calendar.

Home Assistant remains non-authoritative.

## Local authentication

Default is LAN-friendly/no-login:

```dotenv
SCD_REQUIRE_LOGIN=false
```

For protected management routes:

```dotenv
SCD_REQUIRE_LOGIN=true
SCD_SESSION_SECRET=<long-random-secret>
```

When no user exists, `/login` shows first-admin creation. Passwords are PBKDF2-SHA256 hashed and sessions are signed.

Before exposing a general release directly to the Internet, complete the hardening items in `PRODUCT_ARCHITECTURE_AND_DISTRIBUTION.md`, especially CSRF protection, HTTPS-only cookies, throttling/account recovery and OAuth UX.

## PWA/mobile

Responsive pages, `/manifest.webmanifest` and `/service-worker.js` provide an installable web-app baseline with cached GET fallback for previously viewed pages.

Before store-quality distribution, add final icon assets, richer offline/update messaging and a formal accessibility audit.

## Environment

Minimal standalone `.env`:

```dotenv
SCD_DATABASE_PATH=./data/school_cycle_days.sqlite3
SCD_HOST=0.0.0.0
SCD_PORT=8088
```

Optional product settings:

```dotenv
SCD_REQUIRE_LOGIN=false
SCD_SESSION_SECRET=
SCD_SOURCE_REFRESH_SECONDS=21600
```

See `.env.example` for HA/MQTT settings.

## Project layout

```text
standalone_app/
├── README.md
├── FEATURE_IMPLEMENTATION_MATRIX.md
├── ICS_IMPORT_GUIDE.md
├── HOME_ASSISTANT_OPTIONAL_INTEGRATION.md
├── PRODUCT_ARCHITECTURE_AND_DISTRIBUTION.md
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── school_cycle_days/
│   ├── adapters.py
│   ├── config.py
│   ├── database.py
│   ├── ha_client.py
│   ├── ics_import.py
│   ├── main.py                    # compatibility/default UI layer
│   ├── management_routes.py
│   ├── mqtt_adapter.py
│   ├── notifications.py
│   ├── product_app.py             # DISTRIBUTABLE ENTRY POINT
│   ├── product_routes.py
│   ├── publisher_routes.py
│   ├── review_routes.py
│   ├── schedule.py
│   ├── security_routes.py
│   ├── service.py
│   └── sync_engine.py
├── templates/
│   ├── index.html
│   ├── profile.html
│   ├── household.html
│   ├── shared.html
│   ├── login.html
│   └── ics_review.html
└── tests/
    ├── test_ics_import.py
    ├── test_schedule.py
    ├── test_service.py
    └── test_product_features.py
```

## Development

```bash
uvicorn school_cycle_days.product_app:app --reload --host 0.0.0.0 --port 8088
```

Python changes reload the standalone process. Home Assistant does not restart.

## Tests

Before merging or moving this into a new repository:

```bash
python -m compileall school_cycle_days tests
pytest -q
```

Then follow `../STANDALONE_TESTING_GUIDE.md` for end-to-end validation.

## Distribution direction

The project is now structured to become its own repository. Keep this core rule when extracting it:

> **School Cycle Days is a standalone school-calendar product with optional integrations.**

The remaining work for a polished public v1.0 is predominantly release/security/UX hardening rather than core scheduling capability. See [`PRODUCT_ARCHITECTURE_AND_DISTRIBUTION.md`](PRODUCT_ARCHITECTURE_AND_DISTRIBUTION.md).
