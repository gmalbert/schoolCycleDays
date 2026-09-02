# School Cycle Days — Home Assistant Custom Integration

This folder is a standalone Home Assistant-native port of the existing AppDaemon application. Nothing under the existing `apps/` tree is replaced or modified.

The design goal is now explicitly **UI-first**: after installation, routine configuration and school-calendar corrections should be possible entirely from Home Assistant's UI. Editing Python, YAML, service data, or `.ics` files is not part of the normal workflow.

See [`APPDAEMON_COMPATIBILITY_AUDIT.md`](APPDAEMON_COMPATIBILITY_AUDIT.md) for the method-by-method AppDaemon compatibility review.

For installation, local development, restart/reload behavior, and a complete acceptance-test sequence, see [`LOCAL_TESTING_GUIDE.md`](LOCAL_TESTING_GUIDE.md).

## What this version changes

The original AppDaemon app used manually-created HA Helpers for configuration, commands, display state, and persistence. It also called HA back through REST with a bearer token.

This version:

- runs inside Home Assistant;
- installs through a normal **Config Flow** under Settings → Devices & services;
- exposes native `date`, `text`, `number`, `switch`, `select`, and `button` entities;
- persists native UI values with Home Assistant `Store`;
- uses HA calendar APIs directly rather than REST calls back into HA;
- supports targeted calendar-event deletion by UID;
- can delete/rebuild only School Cycle Days events in a selected date range;
- preserves the old Helper/button workflow as a compatibility layer during migration;
- imports the current values of the old Helpers into the native UI on first setup when those Helpers exist.

## Folder layout

```text
ha_custom_integration/
├── APPDAEMON_COMPATIBILITY_AUDIT.md
├── LOCAL_TESTING_GUIDE.md
├── hacs.json
├── README.md
├── examples/
│   └── school_cycle_days_dashboard.yml
└── custom_components/
    └── school_cycle_days/
        ├── __init__.py
        ├── button.py
        ├── config_flow.py
        ├── const.py
        ├── date.py
        ├── entity.py
        ├── manager.py
        ├── manifest.json
        ├── number.py
        ├── select.py
        ├── services.yaml
        ├── strings.json
        ├── switch.py
        ├── text.py
        ├── translations/
        │   └── en.json
        └── ui_state.py
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

Restart Home Assistant.

Then go to:

```text
Settings → Devices & services → Add Integration → School Cycle Days
```

Choose:

- the target Home Assistant calendar;
- the US state code used for holiday generation;
- optionally, the legacy Local Calendar storage path for old ICS import/export/recovery compatibility.

No `configuration.yaml` entry is required for a new installation.

## Existing YAML installations

The transitional `school_cycle_days:` YAML configuration is still accepted. When HA loads it, the integration starts an import flow and converts it into a normal config entry.

This is a migration path, not the intended long-term configuration method.

## Native UI entities

The integration creates its own Home Assistant device and UI controls.

### Dates

Expected entity names:

```text
date.school_cycle_days_school_year_start
date.school_cycle_days_school_year_end
date.school_cycle_days_non_school_day
```

These let you change the school-year range and choose a date to add/remove/correct directly from the dashboard.

### Cycle-day labels

```text
text.school_cycle_days_cycle_day_1
text.school_cycle_days_cycle_day_2
text.school_cycle_days_cycle_day_3
text.school_cycle_days_cycle_day_4
text.school_cycle_days_cycle_day_5
```

Changing Art/Music/Library/etc. no longer requires editing an AppDaemon file or manually maintaining `input_text` Helpers.

### Starting cycle day

```text
number.school_cycle_days_starting_cycle_day
```

This is constrained to 1–5 in the UI.

### Calendar-generation options

```text
switch.school_cycle_days_include_no_school_weekdays
switch.school_cycle_days_include_weekends
```

### Selects

```text
select.school_cycle_days_existing_non_school_day
select.school_cycle_days_import_export_calendar
```

The first is used to remove a stored non-school day. The second is used only for legacy Local Calendar ICS import/export compatibility.

### Action buttons

Expected native buttons include:

```text
button.school_cycle_days_add_non_school_day
button.school_cycle_days_remove_selected_non_school_day
button.school_cycle_days_clear_non_school_days
button.school_cycle_days_load_holidays
button.school_cycle_days_delete_holidays
button.school_cycle_days_generate_cycle_days
button.school_cycle_days_regenerate_selected_range
button.school_cycle_days_delete_generated_events_on_selected_date
button.school_cycle_days_refresh_calendar_list
button.school_cycle_days_import_no_school_dates
button.school_cycle_days_export_selected_calendar
```

The example dashboard at `examples/school_cycle_days_dashboard.yml` uses these native controls.

## Normal UI workflow

### Beginning of the school year

1. Set **School year start**.
2. Set **School year end**.
3. Enter the five cycle-day labels.
4. Set **Starting cycle day**.
5. Load holidays if desired.
6. Press **Generate cycle days**.

No code or YAML is needed.

### Snow day / newly discovered non-school day

1. Set **Non-school day** to the affected date.
2. Press **Add non-school day**.
3. Change **School year start** to the first date whose generated cycle needs replacing, if necessary.
4. Set **Starting cycle day** to the cycle day that should apply to the first eligible school day in that range.
5. Press **Regenerate selected range**.

The integration deletes only School Cycle Days events in that date range and rebuilds them. Unrelated events on the calendar are left alone.

### Remove one generated calendar entry

1. Set **Non-school day** to the date containing the generated event.
2. Press **Delete generated events on selected date**.

The integration queries the calendar for that date, gets the underlying UID, and calls the calendar entity's delete API. You do not have to know or enter the UID.

## Calendar deletion

Home Assistant's calendar entity API supports deletion through `async_delete_event(uid)`. The public automation service surface still does not expose a general `calendar.delete_event` action, but a custom integration running inside HA can call the calendar entity directly.

The integration therefore exposes two levels of deletion:

```text
school_cycle_days.delete_event
```

Deletes exactly one known UID.

```text
school_cycle_days.delete_generated_events
```

Queries a date range, identifies events owned by School Cycle Days, obtains their UIDs, and deletes only those events.

New events contain the marker:

```text
[school_cycle_days]
```

The migration logic also recognizes the `Day N (...)` and `No School` event shapes created by the old AppDaemon app.

### Full calendar deletion

`school_cycle_days.clear_calendar` remains only as a legacy/recovery operation for Local Calendar installations. It should not be used for normal reruns.

## Persistence

Two HA Store records are used:

```text
school_cycle_days.data
school_cycle_days.ui.<config-entry-id>
```

The first stores application data:

- manually-entered non-school dates;
- holiday dates;
- holiday names.

The second stores the values edited with the native UI entities:

- school-year start/end;
- selected non-school date;
- cycle-day labels;
- restart day;
- include-holidays/include-weekends toggles;
- select choices.

These survive HA restarts without requiring manually-created Helpers.

## Migration from the existing Helpers

The old Helpers remain supported as fallbacks and the old `input_button.*` entities remain listened to.

On the first startup where no native UI Store exists, the integration reads the current values of these existing Helpers when available:

```text
input_datetime.cycle_start_day
input_datetime.cycle_end_day
input_datetime.add_non_school_day
input_number.cycle_day_restart_day
input_text.cycle_day_1
input_text.cycle_day_2
input_text.cycle_day_3
input_text.cycle_day_4
input_text.cycle_day_5
input_boolean.include_holidays_in_calendar
input_boolean.include_weekends_in_calendar
input_select.calendar_list
```

Those values seed the native integration entities, so migration should not require re-entering the school-year setup.

The original legacy buttons also remain supported:

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

Do not run AppDaemon and the native integration against the same legacy buttons/calendar simultaneously; both can respond to the same press.

## Helpers that can eventually be removed

Once your dashboard is using the native School Cycle Days entities, the old Helpers are no longer required by the application.

That includes the old configuration controls:

```text
input_datetime.cycle_start_day
input_datetime.cycle_end_day
input_datetime.add_non_school_day
input_number.cycle_day_restart_day
input_text.cycle_day_1
input_text.cycle_day_2
input_text.cycle_day_3
input_text.cycle_day_4
input_text.cycle_day_5
input_boolean.include_holidays_in_calendar
input_boolean.include_weekends_in_calendar
```

and the old application-state/display Helpers:

```text
input_text.non_school_days
input_text.cycle_day_holidays
input_text.system_message
input_text.current_calendar
input_select.non_school_days
input_select.calendar_list
input_select.calendar_list_for_selection
```

as well as the old command `input_button.*` Helpers.

Keep them until the native workflow has been tested on your HA instance; compatibility is deliberately retained so removal can be gradual.

## Advanced Home Assistant actions

The native buttons are intended for routine use, but the integration still exposes scriptable actions for automations and debugging:

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

## Recommended migration/test sequence

1. Back up Home Assistant.
2. Copy the integration into `/config/custom_components/school_cycle_days/`.
3. Restart HA.
4. Add **School Cycle Days** from Settings → Devices & services.
5. Initially select a disposable/test Local Calendar.
6. Confirm the integration device exposes the native Date/Text/Number/Switch/Select/Button entities.
7. Verify the date/cycle values were seeded from your old Helpers.
8. Test adding and removing one non-school day from the UI.
9. Generate a short 2–3 day range.
10. Delete one generated date using the native delete button.
11. Add an unrelated manual event to the test calendar and verify **Regenerate selected range** leaves it untouched.
12. Point the integration at the production school calendar through **Configure**.
13. Move your dashboard to the native entities.
14. Disable the AppDaemon app.
15. Remove obsolete Helpers only after nothing references them.

For the full test matrix, troubleshooting steps, and detailed restart/reload behavior during development, use [`LOCAL_TESTING_GUIDE.md`](LOCAL_TESTING_GUIDE.md).

## Local vs HACS use

For your own installation, HACS is not required. Copying the `custom_components/school_cycle_days` directory into HA is sufficient.

If the integration later becomes its own repository, the contents of `ha_custom_integration/` are already arranged to become that repository's root.
