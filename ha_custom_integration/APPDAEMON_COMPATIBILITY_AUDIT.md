# AppDaemon Compatibility and Native-UI Audit

This audit compares `apps/cycleDays/createDate.py` with the Home Assistant custom integration under `ha_custom_integration/`.

## Conclusion

The integration does **not** require the old manually-created Home Assistant Helpers to function. They remain supported as a migration/compatibility layer, while normal operation is now designed around integration-owned native Home Assistant entities.

The AppDaemon version used Helpers for four jobs:

1. user input;
2. application persistence/state;
3. command buttons;
4. status/output.

The native integration now replaces those with:

- native Date/Text/Number/Switch/Select entities for user-editable values;
- Home Assistant `Store` for persistent application/UI state;
- native Button entities for routine actions;
- integration status/list states for output;
- a Config Flow and Options Flow for target-calendar and integration-level settings.

The old Helpers can therefore be removed gradually after the native dashboard is proven.

## Method-by-method compatibility

| AppDaemon method | Native equivalent | Result |
|---|---|---|
| `initialize()` | config-entry setup + `async_initialize()` | Preserved and modernized. Uses HA Store, no REST token, initializes compatibility listeners, and creates native entities through platform forwarding. |
| `deleteDates()` | `async_clear_calendar()` | Preserved only as a legacy destructive recovery fallback. Normal reruns no longer use it. |
| `refreshCalendarList()` | `async_refresh_calendar_list()` plus native calendar-list refresh | Preserved for old dropdowns and native import/export selection. |
| `addOtherCalendarDates()` | `async_add_dates_from_other_calendar()` | Preserved. Native UI supplies selected calendar and date range; old Helper dropdown remains a fallback. |
| `addNonSchoolday()` | `async_add_non_school_day()` | Preserved. Native Date + Button UI replaces the old input_datetime/input_button pair. |
| `deleteNonSchoolday()` | `async_delete_non_school_day()` | Preserved. Native Select + Button UI replaces the old dropdown/button pair. |
| `showHolidays()` | `async_load_holidays()` | Preserved. Still loads the school-year start year plus the following year; state is configurable through the integration. |
| `deleteHolidays()` | `async_delete_holidays()` | Preserved and exposed as a native button. |
| `exportICS()` | `async_export_ics()` | Preserved for Local Calendar compatibility. `input_button.export_ics` compatibility remains even though checked-in `apps.yaml` omitted it. |
| `clearNonSchooldays()` | `async_clear_non_school_days()` | Preserved, but corrected so clearing manually-entered dates does not erase holiday state. |
| `deleteAndRerun()` | `async_clear_and_rerun()` | Redesigned. Deletes only School Cycle Days events in the selected range and regenerates only that range. Unrelated calendar events are preserved. |
| `changeDefaultCalendar()` | Config Flow / Options Flow | The broken old method itself was not ported. Calendar selection is now implemented correctly in the HA integration configuration UI. |
| `listDates()` | `async_create_cycle_days()` | Preserved and modernized. Same five-day advancement rules, but native HA calendar calls replace REST. |

## Config Flow / UI configuration

A new install should not require `configuration.yaml`.

The integration is added through:

```text
Settings → Devices & services → Add Integration → School Cycle Days
```

The setup/configure UI owns integration-level settings such as:

- target calendar;
- US state code for holiday generation;
- optional legacy Local Calendar storage path.

Existing `school_cycle_days:` YAML is treated as an import/migration source and creates a normal config entry.

## Native entity replacements

### Input values

| Legacy Helper | Native integration entity |
|---|---|
| `input_datetime.cycle_start_day` | `date.school_cycle_days_school_year_start` |
| `input_datetime.cycle_end_day` | `date.school_cycle_days_school_year_end` |
| `input_datetime.add_non_school_day` | `date.school_cycle_days_non_school_day` |
| `input_number.cycle_day_restart_day` | `number.school_cycle_days_starting_cycle_day` |
| `input_text.cycle_day_1` | `text.school_cycle_days_cycle_day_1` |
| `input_text.cycle_day_2` | `text.school_cycle_days_cycle_day_2` |
| `input_text.cycle_day_3` | `text.school_cycle_days_cycle_day_3` |
| `input_text.cycle_day_4` | `text.school_cycle_days_cycle_day_4` |
| `input_text.cycle_day_5` | `text.school_cycle_days_cycle_day_5` |
| `input_boolean.include_holidays_in_calendar` | `switch.school_cycle_days_include_no_school_weekdays` |
| `input_boolean.include_weekends_in_calendar` | `switch.school_cycle_days_include_weekends` |
| `input_select.non_school_days` | `select.school_cycle_days_existing_non_school_day` |
| `input_select.calendar_list` | `select.school_cycle_days_import_export_calendar` |
| `input_select.calendar_list_for_selection` | no longer required by the native workflow |

The exact entity IDs are generated by Home Assistant and may receive a suffix if an entity with the same ID already exists.

### Command buttons

| Legacy button | Native integration button |
|---|---|
| `input_button.rerun_calendar_cycle_days` | `button.school_cycle_days_generate_cycle_days` |
| `input_button.cycle_day_list_holidays` | `button.school_cycle_days_load_holidays` |
| `input_button.add_non_school_day` | `button.school_cycle_days_add_non_school_day` |
| `input_button.clear_non_school_days` | `button.school_cycle_days_clear_non_school_days` |
| `input_button.delete_non_school_day` | `button.school_cycle_days_remove_selected_non_school_day` |
| `input_button.delete_holidays` | `button.school_cycle_days_delete_holidays` |
| `input_button.add_dates_from_other_calendar` | `button.school_cycle_days_import_no_school_dates` |
| `input_button.refresh_calendar_list` | `button.school_cycle_days_refresh_calendar_list` |
| `input_button.delete_and_rerun_calendar_cycle_days` | `button.school_cycle_days_regenerate_selected_range` |
| `input_button.export_ics` | `button.school_cycle_days_export_selected_calendar` |
| `input_button.delete_calendar_events` | **no normal native equivalent**; full-calendar deletion is intentionally not exposed as a routine native button |

There is also a new UI operation with no safe equivalent in the old app:

```text
button.school_cycle_days_delete_generated_events_on_selected_date
```

This removes only School Cycle Days events on the date selected in the native non-school-date entity.

## One-time migration of existing values

The first time the config entry starts without an existing native UI Store, it reads current values from the old Helpers when available:

- start/end dates;
- add-non-school date;
- starting cycle day;
- all five cycle descriptions;
- include-holidays/include-weekends toggles;
- selected legacy calendar.

Those values seed the native entities and are then stored independently under the integration's own HA Store key.

This lets the old and new dashboards coexist during testing without requiring manual re-entry of the school-year configuration.

## State/output helpers

| Legacy helper | Native replacement |
|---|---|
| `input_text.non_school_days` | HA Store + `sensor.school_cycle_days_non_school_days` |
| `input_text.cycle_day_holidays` | HA Store + `sensor.school_cycle_days_holidays` |
| `input_text.system_message` | `sensor.school_cycle_days_status` |
| `input_text.current_calendar` | target calendar in the config entry |

The old status Helpers remain optional compatibility targets; they are not authoritative storage anymore.

## Calendar deletion redesign

Home Assistant's calendar entity model exposes `async_delete_event(uid)`. The integration checks the target calendar's advertised `DELETE_EVENT` feature before attempting deletion.

The native integration provides:

- `school_cycle_days.delete_event` — delete one event by UID;
- `school_cycle_days.delete_generated_events` — discover events in a date range and delete only School Cycle Days events;
- the native **Delete generated events on selected date** button — date-based UI deletion without entering a UID;
- `school_cycle_days.clear_and_rerun` / **Regenerate selected range** — selectively replace generated events in the chosen range;
- `school_cycle_days.clear_calendar` — destructive ICS fallback retained only for recovery/legacy Local Calendar use.

Newly-created events contain an ownership marker in their description. Selective deletion also recognizes the event shapes created by the AppDaemon implementation so existing generated entries can be migrated.

## Legacy input-button compatibility

All functioning old button IDs are still listened to:

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
- `input_button.export_ics`

There is no compatibility button for the old `changeDefaultCalendar()` implementation because the original method was incomplete (`test` raises `NameError`) and `apps.yaml` did not configure such a button.

## AppDaemon-only configuration removed

These are no longer required:

- `bearer_token`;
- `create_event_url`;
- `calendar_event_url`;
- AppDaemon `module` / `class` configuration.

`calendar_name` is replaced by the Config Flow's target-calendar selector.

`calendar_path` is narrowed to the optional `legacy_calendar_storage_path`, needed only for old JSON migration and direct ICS import/export/full-clear compatibility. Normal event creation and selective deletion do not require direct filesystem access.

## Recommended migration sequence

1. Install the custom integration while retaining the old Helpers.
2. Add School Cycle Days through Settings → Devices & services.
3. Confirm the native entities were seeded with the old Helper values.
4. Test the native dashboard against a disposable calendar.
5. Verify single-date event deletion and selective range regeneration.
6. Disable the AppDaemon app before using the production calendar/buttons.
7. Switch the dashboard to the native integration entities.
8. Remove old Helpers only after they are no longer referenced anywhere.
9. Keep `clear_calendar` out of the routine UI; it is a recovery operation only.
