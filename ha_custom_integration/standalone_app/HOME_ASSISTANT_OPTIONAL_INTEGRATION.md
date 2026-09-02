# Optional Home Assistant Integration

School Cycle Days does **not** require Home Assistant.

The standalone application owns its schedule, database, web calendar, REST API, and ICS feed. Home Assistant is only an optional consumer or migration target.

## Recommended integration order

1. **MQTT Discovery** — best HA-native experience when an MQTT broker is available.
2. **REST API** — simple platform-neutral read-only sensors.
3. **ICS subscription** — display the School Cycle Days calendar in a calendar consumer.
4. **Direct HA adapter** — retained primarily for legacy migration and copying generated events into an HA calendar.

---

## MQTT Discovery

Configure the standalone app:

```dotenv
SCD_MQTT_HOST=192.168.1.10
SCD_MQTT_PORT=1883
SCD_MQTT_USERNAME=school_cycle_days
SCD_MQTT_PASSWORD=replace_me
SCD_MQTT_DISCOVERY_PREFIX=homeassistant
SCD_MQTT_BASE_TOPIC=school_cycle_days
```

When configured, schedule rebuilds publish retained Home Assistant Discovery definitions and state for:

```text
sensor.school_cycle_days_today
sensor.school_cycle_days_tomorrow
sensor.school_cycle_days_next_school_day
```

Exact entity IDs can vary if Home Assistant already has entities using those IDs.

Each state message is JSON containing:

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

The sensor state is the `title`; the entire JSON object is also exposed as attributes.

MQTT is best-effort. A broker outage does not prevent the local calendar from rebuilding.

The UI also exposes a manual MQTT publish route:

```text
POST /integrations/mqtt/publish
```

for troubleshooting/re-announcing discovery.

---

## REST API as external sensors

Always available:

```text
GET /api/v1/today
GET /api/v1/tomorrow
GET /api/v1/next-school-day
GET /api/v1/schedule
```

Home Assistant can poll these endpoints, but the exact HA configuration mechanism may vary by release and user preference.

The REST API is intentionally not HA-specific, so Node-RED, scripts, dashboards, mobile apps, or other automation systems can use the same endpoints.

Example response:

```json
{
  "day": "2026-09-10",
  "kind": "no_school",
  "cycle_day": null,
  "title": "No School",
  "detail": "No School",
  "source": "non_school_day"
}
```

---

## ICS feed

Always available:

```text
GET /calendar.ics
```

This is the preferred calendar-display integration because School Cycle Days remains authoritative.

The ICS feed can also be consumed by applications other than HA.

Settings control whether exported/subscribed feeds include:

- No School events;
- weekend entries.

School cycle days are always included.

---

## Legacy Helper migration

If migrating from the original AppDaemon setup, optional direct HA credentials can be configured:

```dotenv
SCD_HA_URL=http://homeassistant.local:8123
SCD_HA_TOKEN=<long-lived-access-token>
```

Then use:

```text
Import old HA Helpers
```

in the standalone UI.

This copies legacy values into the standalone database. It does not make HA authoritative.

The migration reads values such as:

```text
input_datetime.cycle_start_day
input_datetime.cycle_end_day
input_text.cycle_day_1 ... cycle_day_5
input_number.cycle_day_restart_day
input_boolean.include_holidays_in_calendar
input_boolean.include_weekends_in_calendar
input_text.non_school_days
input_text.cycle_day_holidays
```

---

## Direct HA calendar publishing

The app still contains an optional direct publisher for transition/testing.

When HA credentials are configured, the UI can copy generated cycle-day events into a selected HA calendar.

This is intentionally secondary to:

```text
standalone schedule -> ICS/API/MQTT consumers
```

because direct copying introduces duplicate-state concerns and calendar-event lifecycle management.

Do not treat the HA copy as authoritative.

---

## Security

Do not commit:

```text
SCD_HA_TOKEN
SCD_MQTT_PASSWORD
```

For a private LAN deployment, environment variables are acceptable.

Before a general public release, integration credentials should move into a deliberate secrets/settings mechanism rather than requiring ordinary users to edit `.env` files.

---

## Architectural invariant

The application must still start and provide its complete calendar experience when all of these are blank:

```dotenv
SCD_HA_URL=
SCD_HA_TOKEN=
SCD_MQTT_HOST=
```

Any feature that violates that invariant belongs in an optional adapter rather than the core product.
