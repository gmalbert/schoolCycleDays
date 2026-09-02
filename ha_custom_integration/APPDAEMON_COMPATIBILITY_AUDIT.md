# AppDaemon Compatibility and Helper Audit

This audit compares `apps/cycleDays/createDate.py` with the native Home Assistant integration under `ha_custom_integration/`.

## Conclusion

The integration does **not** need the old Home Assistant helpers to function. They are retained only as an optional compatibility/UI layer.

The AppDaemon version used helpers for four jobs:

1. user input;
2. application persistence/state;
3. command buttons;
4. status/output.

The native integration can replace all four:

- action/service fields provide inputs;
- Home Assistant `Store` persists application state;
- `school_cycle_days.*` actions replace `input_button` command helpers;
- native status sensors expose output.

Existing helpers can therefore be removed gradually after the dashboard is migrated.

## Method-by-method compatibility

| AppDaemon method | Native equivalent | Result |
|---|---|---|
| `initialize()` | `async_initialize()` plus HA setup | Preserved and modernized. Uses HA Store, no REST token, initializes optional compatibility helpers. |
| `deleteDates()` | `async_clear_calendar()` | Preserved only as a legacy destructive fallback. Normal reruns no longer use it. |
| `refreshCalendarList()` | `async_refresh_calendar_list()` | Preserved for compatibility with the old dropdown UI. |
| `addOtherCalendarDates()` | `async_add_dates_from_other_calendar()` | Preserved and improved. Calendar/start/end can be supplied directly. |
| `addNonSchoolday()` | `async_add_non_school_day()` | Preserved and improved. Accepts `day` directly and persists in HA Store. |
| `deleteNonSchoolday()` | `async_delete_non_school_day()` | Preserved and improved. Accepts `day` directly. |
| `showHolidays()` | `async_load_holidays()` | Preserved. Still loads the school-year start year plus the following year; state is configurable. |
| `deleteHolidays()` | `async_delete_holidays()` | Preserved. |
| `exportICS()` | `async_export_ics()` | Preserved. `input_button.export_ics` compatibility is included even though the checked-in `apps.yaml` omitted it. |
| `clearNonSchooldays()` | `async_clear_non_school_days()` | Preserved, but corrected so clearing manually entered days does not unintentionally erase holiday state. |
| `deleteAndRerun()` | `async_clear_and_rerun()` | Improved substantially. Deletes only generated School Cycle Days events in the requested range, then regenerates that range. It does not wipe the whole calendar. |
| `changeDefaultCalendar()` | none | Intentionally not ported as behavior. Original method only prints text then executes bare `test`, which raises `NameError`; `apps.yaml` also omitted its button setting. |
| `listDates()` | `async_create_cycle_days()` | Preserved and modernized. Same five-day advancement rules and optional weekend/no-school entries, but uses native HA calls rather than REST. |

## Calendar deletion redesign

Home Assistant's calendar entity model supports `async_delete_event(uid)`. Local Calendar currently advertises `CREATE_EVENT`, `DELETE_EVENT`, and `UPDATE_EVENT` support. Home Assistant does not expose delete/update as ordinary calendar actions, but this custom integration runs inside HA and can access the target calendar entity directly.

The native integration therefore provides:

- `school_cycle_days.delete_event` — delete one event by UID;
- `school_cycle_days.delete_generated_events` — discover events in a date range and delete only events owned by School Cycle Days;
- `school_cycle_days.clear_and_rerun` — selectively delete generated events in a range and regenerate only that range;
- `school_cycle_days.clear_calendar` — old destructive ICS-file deletion retained only as a fallback/manual recovery action.

Newly created events contain a private ownership marker in their description. For migration, selective deletion also recognizes the old AppDaemon event shapes (`Day N (...)` and `No School` events with Holiday/Weekend descriptions).

To remove generated events from a **single day**, call `delete_generated_events` with the same `start_date` and `end_date`.

## Helper inventory

### Input helpers

These are all optional now.

| Legacy helper | Native replacement |
|---|---|
| `input_datetime.add_non_school_day` | `add_non_school_day: day` |
| `input_datetime.cycle_start_day` | `start_date` action field |
| `input_datetime.cycle_end_day` | `end_date` action field |
| `input_text.cycle_day_1` through `input_text.cycle_day_5` | five-element `cycle_days` action field |
| `input_number.cycle_day_restart_day` | `day_number` action field |
| `input_boolean.include_holidays_in_calendar` | `include_holidays` action field |
| `input_boolean.include_weekends_in_calendar` | `include_weekends` action field |
| `input_select.non_school_days` | `delete_non_school_day: day` |
| `input_select.calendar_list` | `calendar_name` action field |
| `input_select.calendar_list_for_selection` | not required by the native workflow |

### State/output helpers

| Legacy helper | Native replacement |
|---|---|
| `input_text.non_school_days` | HA Store + `sensor.school_cycle_days_non_school_days` |
| `input_text.cycle_day_holidays` | HA Store + `sensor.school_cycle_days_holidays` |
| `input_text.system_message` | `sensor.school_cycle_days_status` |
| `input_text.current_calendar` | configured `calendar_entity`; legacy helper is optional display compatibility only |

### Legacy input buttons

All functioning old button IDs remain understood as compatibility triggers:

- `input_button.rerun_calendar_cycle_days`
- `input_button.cycle_day_list_holidays`
- `input_button.add_non_school_day`
- `input_button.clear_non_school_days`
- `input_button.delete_non_school_day`
- `input_button.delete_calendar_events`
- `input_button.delete_holidays`
- `input_button.add_dates_from_other_calendar`
- `input_button.refresh_calendar_list`
- `input_button.delete_and_rerun_calendar_cycle_days`
- `input_button.export_ics` (referenced in `createDate.py`; missing from checked-in `apps.yaml`)

There is no compatibility button for `changeDefaultCalendar()` because the original function is incomplete/broken and no entity ID was defined in `apps.yaml`.

## AppDaemon-only configuration removed

These are no longer necessary:

- `bearer_token`
- `create_event_url`
- `calendar_event_url`
- AppDaemon `module` / `class` configuration

`calendar_name` becomes the native integration's `calendar_entity` setting.

The old `calendar_path` concept is narrowed to `legacy_calendar_storage_path`, which is only needed for legacy JSON migration and direct ICS import/export/full-clear compatibility. Normal event creation and selective event deletion do not require direct ICS access.

## Recommended migration strategy

1. Install the custom integration while retaining existing helpers.
2. Verify the old dashboard/buttons still trigger the expected behavior.
3. Switch the dangerous old delete-and-rerun workflow to the new selective `clear_and_rerun` behavior.
4. Migrate dashboard buttons to direct `school_cycle_days.*` actions.
5. Replace helper-based inputs with action fields or integration-owned UI entities as desired.
6. Remove obsolete helpers only after the dashboard no longer references them.
7. Keep `clear_calendar` out of the normal UI; it should be a recovery tool, not the normal rerun mechanism.
