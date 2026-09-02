# School Cycle Days — Home Assistant Custom Integration

This folder is a standalone Home Assistant-native port of the existing AppDaemon application. Nothing under the existing `apps/` tree is replaced or modified.

The integration can be installed locally without HACS. HACS metadata is included so this folder can later become its own repository if desired.

See [`APPDAEMON_COMPATIBILITY_AUDIT.md`](APPDAEMON_COMPATIBILITY_AUDIT.md) for the method-by-method port and helper/entity analysis.

## Why move away from AppDaemon

The original app used Home Assistant helpers as configuration, persistence, commands, and status, then called Home Assistant back through REST with a bearer token to create calendar events.

This version runs inside Home Assistant and therefore:

- reads HA state directly;
- calls Home Assistant calendar APIs directly;
- requires no bearer token or self-REST requests;
- stores application data with Home Assistant `Store`;
- can operate with **no legacy helper entities at all**;
- keeps the existing helper/button IDs as optional compatibility fallbacks;
- can delete individual calendar events and selectively replace generated cycle-day events instead of wiping the calendar.

## Folder layout

```text
ha_custom_integration/
├── APPDAEMON_COMPATIBILITY_AUDIT.md
├── hacs.json
├── README.md
├── examples/
│   └── school_cycle_days_dashboard.yml
└── custom_components/
    └── school_cycle_days/
        ├── __init__.py
        ├── const.py
        ├── manager.py
        ├── manifest.json
        └── services.yaml
```

## Local installation

Copy:

```text
ha_custom_integration/custom_components/school_cycle_days
```

into:

```text
/config/custom_components/school_cycle_days/
```

Restart Home Assistant after changing integration Python files.

## Minimum configuration

```yaml
school_cycle_days:
  calendar_entity: calendar.school
```

For legacy JSON migration and direct Local Calendar ICS import/export/full-clear compatibility, optionally add:

```yaml
school_cycle_days:
  calendar_entity: calendar.school
  us_state: NH
  legacy_calendar_storage_path: /config/.storage
```

Normal calendar creation and **native selective event deletion do not require direct ICS-file access**.

## Do we still need the old helpers?

No. They are compatibility/UI conveniences, not integration dependencies.

Native actions can now receive all operational values directly:

```yaml
action: school_cycle_days.create_cycle_days
data:
  start_date: "2026-09-01"
  end_date: "2027-06-15"
  cycle_days:
    - Art
    - Music
    - Library
    - PE
    - STEM
  day_number: 1
  include_holidays: false
  include_weekends: false
```

If a field is omitted, the integration falls back to the matching historical helper **if that helper exists**. This allows gradual migration.

### Helpers worth keeping temporarily

For an interactive dashboard, these can still be convenient controls:

- `input_datetime.cycle_start_day`
- `input_datetime.cycle_end_day`
- `input_datetime.add_non_school_day`
- `input_number.cycle_day_restart_day`
- possibly `input_boolean.include_holidays_in_calendar`
- possibly `input_boolean.include_weekends_in_calendar`

### Strong candidates for removal

Once the dashboard uses native actions, these are no longer useful to the application itself:

- `input_text.non_school_days` — replaced by HA Store + status sensor;
- `input_text.cycle_day_holidays` — replaced by HA Store + status sensor;
- `input_text.system_message` — replaced by `sensor.school_cycle_days_status`;
- `input_text.current_calendar` — target calendar is already integration configuration;
- most `input_button.*` helpers — dashboard buttons can call integration actions directly;
- `input_select.calendar_list_for_selection` — not needed by the native workflow;
- the five `input_text.cycle_day_1` through `_5` helpers if cycle labels are supplied directly/configured elsewhere.

The exact compatibility inventory is in `APPDAEMON_COMPATIBILITY_AUDIT.md`.

## Native Home Assistant actions

```text
school_cycle_days.create_cycle_days
school_cycle_days.load_holidays
school_cycle_days.add_non_school_day
school_cycle_days.delete_non_school_day
school_cycle_days.clear_non_school_days
school_cycle_days.delete_holidays
school_cycle_days.add_dates_from_other_calendar
school_cycle_days.refresh_calendar_list
school_cycle_days.delete_event
school_cycle_days.delete_generated_events
school_cycle_days.clear_and_rerun
school_cycle_days.clear_calendar
school_cycle_days.export_ics
```

## Calendar deletion — no more full-calendar reruns

Home Assistant's calendar entity API supports event deletion internally. Local Calendar implements `async_delete_event(uid)` and advertises delete support even though HA does not currently expose a general `calendar.delete_event` automation action.

Because this custom integration runs inside Home Assistant, it can call the calendar entity directly.

### Delete one known event

```yaml
action: school_cycle_days.delete_event
data:
  uid: "EVENT-UID-HERE"
```

### Delete generated events on one day

You do **not** need the UID for the common School Cycle Days case. Use the same date for both ends of the range:

```yaml
action: school_cycle_days.delete_generated_events
data:
  start_date: "2026-12-03"
  end_date: "2026-12-03"
```

The integration queries the calendar entity, obtains the event UIDs internally, and deletes only events recognized as School Cycle Days events.

### Replace only part of the calendar

```yaml
action: school_cycle_days.clear_and_rerun
data:
  start_date: "2026-12-03"
  end_date: "2027-06-15"
  cycle_days:
    - Art
    - Music
    - Library
    - PE
    - STEM
  day_number: 3
  include_holidays: false
  include_weekends: false
```

This now means:

1. find generated School Cycle Days events from December 3 through June 15;
2. delete only those events by UID;
3. preserve unrelated events on the same calendar;
4. regenerate only that date range.

It **does not delete the calendar ICS file**.

### How generated events are identified

New events include an ownership marker in their description:

```text
[school_cycle_days]
```

For migration, selective deletion also recognizes the event shapes created by the old AppDaemon version:

- summaries beginning with `Day ` and ending in the cycle description; and
- `No School` events whose description is `Holiday` or `Weekend`.

That means selective rerun can clean up old AppDaemon-generated events as well as new ones.

### `clear_calendar` is now recovery-only

`school_cycle_days.clear_calendar` retains the old destructive Local Calendar ICS-file deletion behavior solely as a compatibility/recovery tool.

It should not be part of the normal dashboard workflow.

## Persistence

The AppDaemon version used `school_cycle_days.json` because its custom entity attributes were not durable across HA restarts.

The native integration uses Home Assistant's `Store` helper with key:

```text
school_cycle_days.data
```

It stores:

- manually added non-school days;
- holiday dates;
- holiday names.

If there is no native store yet and `legacy_calendar_storage_path` is configured, startup imports the old `school_cycle_days.json`. The old file is not modified or deleted.

## Status entities

The first port publishes:

```text
sensor.school_cycle_days_non_school_days
sensor.school_cycle_days_holidays
sensor.school_cycle_days_status
```

The list sensors expose the stored values as attributes. These replace using `input_text` attributes as an application database.

A later cleanup can convert these runtime states into proper entity-registry-backed `SensorEntity` objects.

## Existing AppDaemon button compatibility

The original functioning input-button names remain supported so the old dashboard can be used during migration, including:

```text
input_button.rerun_calendar_cycle_days
input_button.cycle_day_list_holidays
input_button.add_non_school_day
input_button.clear_non_school_days
input_button.delete_non_school_day
input_button.delete_calendar_events
input_button.delete_holidays
input_button.add_dates_from_other_calendar
input_button.refresh_calendar_list
input_button.delete_and_rerun_calendar_cycle_days
input_button.export_ics
```

`input_button.export_ics` was referenced by `createDate.py` even though it was missing from the checked-in `apps.yaml`; the native port includes it.

The old `changeDefaultCalendar()` handler was not treated as supported functionality because it simply executed an undefined `test` name and its button was not configured in `apps.yaml`.

## HACS later

For local use, HACS is unnecessary. If this becomes its own repository later, the contents of `ha_custom_integration/` are already arranged to become the repository root.

## Recommended migration/test sequence

1. Back up Home Assistant.
2. Copy `custom_components/school_cycle_days` to `/config/custom_components/`.
3. Configure a disposable Local Calendar first.
4. Restart HA and verify `sensor.school_cycle_days_status`.
5. Test `add_non_school_day` and `delete_non_school_day` using direct action data.
6. Test a 2–3 day `create_cycle_days` range.
7. Test `delete_generated_events` for a single generated date.
8. Add an unrelated manual event to the test calendar and verify `clear_and_rerun` leaves it intact.
9. Verify an old-style AppDaemon `Day N (...)` event can be found/deleted by selective deletion.
10. Only then point the integration at the production school calendar.
11. Migrate dashboard buttons from `input_button.*` helpers to direct actions.
12. Remove obsolete helper entities after nothing references them.

Do not run AppDaemon and the native integration against the same legacy buttons/calendar simultaneously, because both can respond to a button press.
