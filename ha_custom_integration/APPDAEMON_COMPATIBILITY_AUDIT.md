# AppDaemon Compatibility Audit — Standalone Target

This audit compares the original `apps/cycleDays/createDate.py` implementation with the current rewrite work.

## Current conclusion

The **preferred target is now the standalone application** under:

```text
ha_custom_integration/standalone_app/
```

The earlier Home Assistant-native custom integration under:

```text
ha_custom_integration/custom_components/school_cycle_days/
```

is retained as a migration/reference implementation, not the preferred runtime.

The standalone app runs outside Home Assistant, stores its own state in SQLite, exposes its own web UI, and connects to HA remotely through supported REST/WebSocket APIs.

The original AppDaemon version used Home Assistant Helpers for four jobs:

1. user input;
2. application persistence/state;
3. command buttons;
4. status/output.

The standalone application replaces all four without requiring Home Assistant Helpers.

---

## Method-by-method compatibility

| AppDaemon method | Standalone equivalent | Result |
|---|---|---|
| `initialize()` | app startup + SQLite + HA client | Modernized. No AppDaemon lifecycle and no HA Helper-backed storage. |
| `deleteDates()` | selective UID deletion | Replaced. Whole-calendar `.ics` deletion is not part of normal operation. |
| `refreshCalendarList()` | `GET /api/calendars` | Replaced with HA's remote calendar discovery API. |
| `addOtherCalendarDates()` | future/import feature | Not yet a primary standalone feature. Existing HA-native implementation remains reference code. |
| `addNonSchoolday()` | web UI + SQLite `non_school_days` | Preserved and simplified. |
| `deleteNonSchoolday()` | web UI remove control + SQLite | Preserved and simplified. |
| `showHolidays()` | `load_holidays()` | Preserved using `holidays.US`, configured state, and school-year range. |
| `deleteHolidays()` | web UI clear-holidays action | Preserved. |
| `exportICS()` | not required for normal standalone operation | HA remains the calendar provider; direct `.ics` export is no longer foundational. |
| `clearNonSchooldays()` | web UI clear + SQLite | Preserved. |
| `deleteAndRerun()` | `regenerate()` | Redesigned. Deletes only owned events in the selected range, then recreates them. |
| `changeDefaultCalendar()` | HA calendar dropdown in standalone UI | Implemented correctly. Original method was incomplete/broken. |
| `listDates()` | `generate()` | Preserved and modernized. Same five-day advancement model, but HA is accessed remotely. |

---

# Original configuration mapping

## AppDaemon-only settings that disappear

These are no longer needed:

```text
module
class
bearer_token in AppDaemon config
create_event_url
calendar_event_url
calendar_path for routine operation
```

The standalone app still requires a Home Assistant credential, but it is supplied through the process environment as:

```text
SCD_HA_TOKEN
```

rather than being embedded in AppDaemon configuration.

## Calendar target

Old:

```yaml
calendar_name: calendar.school
```

New:

Choose the calendar from the standalone web UI. The selector is populated remotely from:

```text
GET /api/calendars
```

## Holiday state

Old implementation hard-coded NH in the `holidays` call.

New standalone setting:

```text
US state code
```

stored in SQLite and editable through the UI.

---

# Legacy HA Helper mapping

None of these Helpers is required by the standalone target.

| Legacy Helper | Standalone replacement |
|---|---|
| `input_datetime.cycle_start_day` | School year start field in web UI / SQLite |
| `input_datetime.cycle_end_day` | School year end field in web UI / SQLite |
| `input_datetime.add_non_school_day` | Add non-school day date field |
| `input_number.cycle_day_restart_day` | Starting cycle day field |
| `input_text.cycle_day_1` | Cycle Day 1 field |
| `input_text.cycle_day_2` | Cycle Day 2 field |
| `input_text.cycle_day_3` | Cycle Day 3 field |
| `input_text.cycle_day_4` | Cycle Day 4 field |
| `input_text.cycle_day_5` | Cycle Day 5 field |
| `input_boolean.include_holidays_in_calendar` | Create visible blocked-weekday events checkbox |
| `input_boolean.include_weekends_in_calendar` | Create visible weekend events checkbox |
| `input_select.non_school_days` | Stored non-school-day list with Remove buttons |
| `input_select.calendar_list` | HA calendar dropdown |
| `input_select.calendar_list_for_selection` | Not required |
| `input_text.non_school_days` | SQLite `non_school_days` table |
| `input_text.cycle_day_holidays` | SQLite `holiday_days` table |
| `input_text.system_message` | Standalone page messages/logging |
| `input_text.current_calendar` | Standalone `calendar_entity` setting |

---

# Legacy button mapping

The standalone UI replaces generic HA `input_button` Helpers with purpose-specific web buttons/forms.

| Legacy button | Standalone UI operation |
|---|---|
| `input_button.rerun_calendar_cycle_days` | Generate configured school year |
| `input_button.cycle_day_list_holidays` | Load / refresh holidays |
| `input_button.add_non_school_day` | Add non-school day |
| `input_button.clear_non_school_days` | Clear manual non-school days |
| `input_button.delete_non_school_day` | Remove beside selected stored date |
| `input_button.delete_calendar_events` | No routine equivalent; destructive whole-calendar clear is intentionally removed |
| `input_button.delete_holidays` | Clear holidays |
| `input_button.add_dates_from_other_calendar` | Not yet primary standalone UI functionality |
| `input_button.refresh_calendar_list` | Main page retrieves calendars remotely; no manual refresh normally required |
| `input_button.delete_and_rerun_calendar_cycle_days` | Delete generated events + regenerate range |
| `input_button.export_ics` | Not required for normal operation |

---

# Calendar creation

Original AppDaemon:

```text
requests.post(create_event_url, bearer token, JSON)
```

Standalone:

```text
POST /api/services/calendar/create_event
```

The important difference is architectural rather than protocol-level: the call now originates from an independent application rather than AppDaemon running as part of the HA environment.

---

# Calendar reading

Standalone uses:

```text
GET /api/calendars/<entity_id>?start=<timestamp>&end=<timestamp>
```

The returned events are used to identify existing generated entries before regeneration.

The app asks HA for its configured timezone first through:

```text
GET /api/config
```

so date-range queries align with the HA calendar's local-day boundaries.

---

# Calendar deletion redesign

This is the largest behavioral improvement over AppDaemon.

The original app deleted the physical calendar file because it lacked a practical per-event deletion mechanism.

Current Home Assistant exposes authenticated WebSocket calendar deletion:

```text
calendar/event/delete
```

The standalone application therefore:

1. fetches events for the requested range;
2. identifies School Cycle Days-owned events;
3. reads each event UID;
4. sends an authenticated `calendar/event/delete` command;
5. preserves unrelated events;
6. regenerates only the requested range when appropriate.

No `.ics` file deletion is needed.

---

# Event ownership

New standalone-generated events include:

```text
[school_cycle_days]
```

in the description.

This is the authoritative ownership marker going forward.

During migration, the app also recognizes old AppDaemon-generated shapes such as:

```text
Day 3 (Library)
```

and recognized legacy `No School` events.

This allows old generated events to be selectively replaced without deleting arbitrary user-created calendar entries.

---

# Persistence redesign

Original AppDaemon used:

- helper attributes;
- `school_cycle_days.json`;
- HA input-select options;
- AppDaemon runtime state.

Standalone uses SQLite:

```text
settings
non_school_days
holiday_days
```

This state survives both HA restarts and standalone-process restarts.

HA is no longer the application's database.

---

# UI requirement

The rewrite keeps the explicit requirement that routine operation must be possible through a UI.

The standalone web UI currently exposes:

- HA calendar selection;
- school-year start/end;
- Cycle Day 1–5 descriptions;
- starting cycle day;
- visible No School/weekend toggles;
- add/remove/clear non-school days;
- load/clear holidays;
- initial calendar generation;
- selective range regeneration;
- delete generated events on one date.

Normal users should not need to edit code, YAML, HA Helpers, or `.ics` files.

---

# Development improvement

AppDaemon / HA-native development:

```text
edit code
→ deploy into HA/AppDaemon
→ reload/restart runtime
→ retest
```

Standalone development:

```bash
uvicorn school_cycle_days.main:app --reload
```

then:

```text
edit code
→ save
→ Uvicorn restarts standalone app automatically
→ retest
```

No Home Assistant restart is required for School Cycle Days code changes.

---

# HA-native prototype status

The branch still contains the HA-native implementation and its native Date/Text/Number/Switch/Select/Button entities.

That work is not discarded. It remains useful as:

- migration reference;
- behavior comparison;
- fallback code;
- proof of event-deletion behavior inside HA;
- documentation of the old Helper mapping.

Do not install it as the primary implementation if testing the standalone architecture unless there is a specific compatibility reason.

---

# Recommended migration sequence

1. Keep AppDaemon production behavior unchanged.
2. Run the standalone app against a disposable HA calendar.
3. Run the standalone test suite.
4. Verify remote calendar discovery.
5. Generate a short known range.
6. Verify non-school-day cycle pauses.
7. Verify holiday behavior.
8. Verify single-date UID deletion.
9. Add an unrelated event and prove selective regeneration preserves it.
10. Verify legacy AppDaemon generated events can be selectively replaced.
11. Verify standalone state survives HA restart.
12. Disable AppDaemon before touching the production school calendar with the standalone app.
13. Cut over a small production range first.
14. Retire old HA Helpers only after the standalone workflow is stable.

For the full migration rationale, see:

```text
STANDALONE_MIGRATION_GUIDE.md
```

For the test plan, see:

```text
STANDALONE_TESTING_GUIDE.md
```
