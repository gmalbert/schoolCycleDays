# School Cycle Days — Home Assistant Custom Integration

This folder is a standalone Home Assistant-native port of the existing AppDaemon application. Nothing under the existing `apps/` tree is replaced or modified.

The integration is intentionally usable **locally** without publishing it through HACS. HACS metadata is included so this folder can also be split into its own repository later if desired.

## What changed from AppDaemon

The original application talks to Home Assistant through AppDaemon and, for calendar creation, makes REST calls back into Home Assistant using a bearer token.

This port runs inside Home Assistant Core and therefore:

- reads helper/entity state directly through `hass.states`;
- calls Home Assistant actions directly through `hass.services.async_call`;
- does not require a bearer token or `requests`;
- persists non-school days and holidays with Home Assistant's `Store` helper;
- retains compatibility with the existing helper/button workflow;
- additionally exposes native `school_cycle_days.*` actions so the input buttons can eventually be removed;
- keeps legacy Local Calendar `.ics` file manipulation isolated to import/export/calendar-clear compatibility functions.

## Folder layout

```text
ha_custom_integration/
├── hacs.json
├── README.md
└── custom_components/
    └── school_cycle_days/
        ├── __init__.py
        ├── const.py
        ├── manager.py
        ├── manifest.json
        └── services.yaml
```

## Local installation

Copy this directory:

```text
ha_custom_integration/custom_components/school_cycle_days
```

into your Home Assistant configuration directory so that HA has:

```text
/config/custom_components/school_cycle_days/
```

Do **not** copy the entire `ha_custom_integration` directory into `custom_components`.

Restart Home Assistant after installing or changing Python files.

## configuration.yaml

The minimum configuration is:

```yaml
school_cycle_days:
  calendar_entity: calendar.school
```

The integration defaults to the same helper entity IDs used by the current AppDaemon application.

For compatibility with Local Calendar importing, exporting, and the existing "delete all events" behavior, also configure the directory containing the Local Calendar `.ics` files:

```yaml
school_cycle_days:
  calendar_entity: calendar.school
  us_state: NH
  legacy_calendar_storage_path: /config/.storage
```

Depending on your Home Assistant installation, the physical configuration path may appear as `/homeassistant/.storage` instead. Use the path that actually contains your Local Calendar `.ics` files.

### Override helper entity IDs

You only need to list helpers whose IDs differ from the defaults:

```yaml
school_cycle_days:
  calendar_entity: calendar.school
  us_state: NH
  legacy_calendar_storage_path: /config/.storage

  entities:
    start_date: input_datetime.cycle_start_day
    end_date: input_datetime.cycle_end_day
    cycle_day_1: input_text.cycle_day_1
    cycle_day_2: input_text.cycle_day_2
    cycle_day_3: input_text.cycle_day_3
    cycle_day_4: input_text.cycle_day_4
    cycle_day_5: input_text.cycle_day_5
```

The full default entity mapping is in `const.py`.

### Override button entity IDs

The existing input buttons are supported so the old dashboard can continue to drive the application:

```yaml
school_cycle_days:
  calendar_entity: calendar.school
  buttons:
    rerun: input_button.rerun_calendar_cycle_days
    list_holidays: input_button.cycle_day_list_holidays
```

The full default mapping is in `const.py`.

## Native Home Assistant actions

The integration registers these actions:

```text
school_cycle_days.create_cycle_days
school_cycle_days.load_holidays
school_cycle_days.add_non_school_day
school_cycle_days.delete_non_school_day
school_cycle_days.clear_non_school_days
school_cycle_days.delete_holidays
school_cycle_days.add_dates_from_other_calendar
school_cycle_days.refresh_calendar_list
school_cycle_days.clear_calendar
school_cycle_days.clear_and_rerun
school_cycle_days.export_ics
```

For example, a dashboard button or automation can call:

```yaml
action: school_cycle_days.create_cycle_days
```

That means the legacy `input_button` helpers are no longer technically required once the dashboard is migrated.

## Entity-state access

Because this runs inside Home Assistant, reading another entity requires no REST API and no authentication token:

```python
state = self.hass.states.get("input_datetime.cycle_start_day")
if state is not None:
    value = state.state
```

The manager wraps this with:

```python
start_date = self.state("start_date")
```

## Persistence

The AppDaemon version stored state in `school_cycle_days.json` because AppDaemon-created entity attributes were not durable across HA restarts.

This port instead uses Home Assistant's native `Store` helper. The data is persisted under HA's `.storage` system with a `school_cycle_days.data` storage key.

If no native store exists yet and `legacy_calendar_storage_path` is configured, startup looks for the old:

```text
school_cycle_days.json
```

and imports:

- `No school days`
- `Holiday Dates`
- `Holiday Names`

into the new Store automatically.

The old JSON file is **not deleted or changed**.

## New status entities

For compatibility and visibility, the integration publishes:

```text
sensor.school_cycle_days_non_school_days
sensor.school_cycle_days_holidays
sensor.school_cycle_days_status
```

The first two expose the stored lists as attributes:

```text
sensor.school_cycle_days_non_school_days
  No school days: [...]

sensor.school_cycle_days_holidays
  Holiday Dates: [...]
  Holidays: [...]
```

These replace the old practice of trying to attach application-managed attributes to `input_text` helpers.

## Calendar creation

The AppDaemon version performs an HTTP POST to Home Assistant's REST API using a bearer token.

The custom integration instead calls Home Assistant directly:

```python
await hass.services.async_call(
    "calendar",
    "create_event",
    {
        "entity_id": "calendar.school",
        "start_date": "2026-09-01",
        "end_date": "2026-09-02",
        "summary": "Day 1 (Art)",
        "description": "Art",
    },
    blocking=True,
)
```

No token, network request, or self-HTTP configuration is needed.

## Calendar deletion caveat

The current calendar entity API supports event deletion internally, but Home Assistant still does not expose a universal `calendar.delete_event` action suitable for this workflow.

For that reason, `school_cycle_days.clear_calendar` retains the old Local Calendar workaround: it deletes the applicable Local Calendar `.ics` file and asks Home Assistant to reload the calendar config entry.

That behavior is only enabled when `legacy_calendar_storage_path` is configured and should only be used with a Home Assistant Local Calendar whose backing file you intend to clear.

Longer term, this method should be replaced when HA exposes a stable public calendar-delete action appropriate for bulk deletion.

## Existing AppDaemon code

The original implementation remains untouched at:

```text
/apps/cycleDays/
```

This makes it possible to test the custom integration alongside the existing implementation and roll back simply by removing the custom integration/configuration.

Do not run both implementations against the same buttons/calendar at the same time during normal use, because both will respond to the same button presses and can create duplicate calendar events.

## HACS later

The folder contains `hacs.json`, but the current repository layout is deliberately conservative because the AppDaemon project remains at the repository root.

If you decide to make the custom integration its own HACS repository later, the contents of `ha_custom_integration/` can become the new repository root. The resulting repository would already have the expected structure:

```text
custom_components/school_cycle_days/
hacs.json
README.md
```

For purely local use, HACS is unnecessary.

## Recommended test sequence

1. Back up Home Assistant.
2. Copy `custom_components/school_cycle_days` into `/config/custom_components/`.
3. Add the minimal `school_cycle_days:` configuration.
4. Restart HA and confirm there are no integration load errors.
5. Confirm `sensor.school_cycle_days_status` says the integration is ready.
6. Test adding and deleting a non-school day.
7. Test holiday generation.
8. Use a short 2–3 day date range and a test Local Calendar to test cycle-day creation.
9. Only after validating creation, test the calendar-clear function against that test calendar.
10. Disable/remove the AppDaemon version before pointing the new integration at the production calendar/buttons.

## Known first-port limitations

- Configuration is YAML-first rather than a config flow. This is intentional for the initial local-use port.
- The three status sensors are runtime states rather than entity-registry-backed `SensorEntity` objects. A later cleanup can move them to a proper `sensor.py` platform.
- Local ICS import/export/clear depends on Home Assistant Local Calendar's on-disk representation and is therefore compatibility code rather than the preferred HA API path.
- The cycle is currently fixed at five days, matching the existing application.
- This branch has not been exercised against your live Home Assistant instance; test against a disposable/test calendar first.
