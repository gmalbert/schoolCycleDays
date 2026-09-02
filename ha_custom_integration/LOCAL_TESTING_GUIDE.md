# School Cycle Days — Local Testing Guide

This guide explains how to test the Home Assistant custom integration under `ha_custom_integration/` without disturbing the existing AppDaemon implementation.

The intended development model is:

```text
GitHub / local working copy
        ↓
/config/custom_components/school_cycle_days/
        ↓
Restart Home Assistant after Python/code changes
        ↓
Test through Home Assistant UI
```

The important distinction is:

- **Changes you make through the School Cycle Days UI entities are applied immediately and persisted by Home Assistant.**
- **Changes you make to the integration's Python/source files are not hot-reloaded into the already-running Home Assistant process.** Restart Home Assistant after changing Python, the manifest, config-flow code, or entity-platform code.

---

## 1. Use a test calendar first

Do not initially point the new integration at your production school calendar.

Create a disposable Home Assistant Local Calendar such as:

```text
calendar.school_cycle_test
```

The ideal initial arrangement is:

```text
Existing AppDaemon app
    → calendar.school

New School Cycle Days custom integration
    → calendar.school_cycle_test
```

This lets both implementations remain installed during testing without both writing to the same calendar.

Do not have AppDaemon and the custom integration pointed at the same calendar or responding to the same legacy helper buttons during normal testing.

---

## 2. Install the custom integration locally

From this repository/branch, copy:

```text
ha_custom_integration/custom_components/school_cycle_days/
```

into your Home Assistant configuration directory as:

```text
/config/custom_components/school_cycle_days/
```

The resulting directory should contain:

```text
/config/custom_components/school_cycle_days/
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
├── ui_state.py
└── translations/
    └── en.json
```

Do not copy the entire `ha_custom_integration` folder into `custom_components`.

---

## 3. Restart Home Assistant

For first installation, perform a full Home Assistant restart:

```text
Settings
→ System
→ Restart Home Assistant
```

A dashboard refresh or YAML reload is not sufficient to load a new Python custom integration.

Home Assistant's developer guidance for testing integrations under `/config/custom_components` explicitly calls for restarting Home Assistant after copying/changing integration code.

---

## 4. Check the Home Assistant logs

After restart, go to:

```text
Settings
→ System
→ Logs
```

Search for:

```text
school_cycle_days
```

Look for errors such as:

```text
Error setting up entry School Cycle Days
Error while setting up platform school_cycle_days
ImportError
ModuleNotFoundError
AttributeError
TypeError
```

If the integration does not appear in the Add Integration screen, check the logs first.

The Home Assistant frontend also caches integration/config-flow metadata aggressively. If the logs are clean but the integration is missing or labels appear stale, perform a hard browser refresh after restarting Home Assistant.

Typical browser hard refresh:

```text
Ctrl + Shift + R
```

or the browser's equivalent.

---

## 5. Add the integration from the UI

Go to:

```text
Settings
→ Devices & services
→ Add Integration
→ School Cycle Days
```

For the first test use something like:

```text
Name: School Cycle Days Test
Calendar: calendar.school_cycle_test
US state code: NH
Legacy Local Calendar storage path: leave blank initially
```

The legacy path is not required for normal event creation or selective event deletion.

Only configure the legacy storage path when testing old JSON migration, direct ICS import/export, or the recovery-only whole-calendar clear operation.

---

## 6. Verify the native UI entities

Open:

```text
Settings
→ Devices & services
→ School Cycle Days
```

The integration should expose native entities for routine configuration and operations.

Expected controls include approximately:

### Date entities

```text
School year start
School year end
Non-school day
```

### Text entities

```text
Cycle Day 1
Cycle Day 2
Cycle Day 3
Cycle Day 4
Cycle Day 5
```

### Number entity

```text
Starting cycle day
```

with a valid range of 1 through 5.

### Switch entities

```text
Include no-school weekdays
Include weekends
```

### Select entities

```text
Existing non-school day
Import/export calendar
```

### Button entities

```text
Add non-school day
Remove selected non-school day
Clear non-school days
Load holidays
Delete holidays
Generate cycle days
Regenerate selected range
Delete generated events on selected date
Refresh calendar list
Import no-school dates
Export selected calendar
```

Home Assistant may append suffixes to entity IDs if conflicting IDs already exist. Use the integration/device page as the authoritative source for the actual generated entity IDs.

---

## 7. Verify migration from existing helpers

The integration retains the old AppDaemon helper compatibility layer.

On first native setup, if native UI state has not already been persisted, the integration attempts to seed values from existing helpers such as:

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

Verify that the new native entities contain your expected existing values.

Do not remove the old helpers yet. Keep them until the native UI workflow has been fully tested.

---

## 8. Test native UI persistence

Before testing calendars, verify that native UI values persist correctly.

Change several values in the UI, for example:

```text
School year start: 2026-09-08
School year end: 2026-09-11
Cycle Day 1: Art
Cycle Day 2: Music
Cycle Day 3: Library
Cycle Day 4: PE
Cycle Day 5: STEM
Starting cycle day: 1
Include no-school weekdays: Off
Include weekends: Off
```

Then restart Home Assistant.

After restart, verify those values are still present.

These values are stored by the integration using Home Assistant's persistent storage rather than depending on manually-created Helpers.

---

## 9. Test a very small cycle-day range

Use a short weekday-only test range rather than generating an entire school year.

Example:

```text
Start: September 8, 2026
End: September 11, 2026
Starting cycle day: 1
```

Cycle descriptions:

```text
Day 1 = Art
Day 2 = Music
Day 3 = Library
Day 4 = PE
Day 5 = STEM
```

Set:

```text
Include no-school weekdays = Off
Include weekends = Off
```

Press:

```text
Generate cycle days
```

Expected test calendar events:

```text
Sep 8  → Day 1 (Art)
Sep 9  → Day 2 (Music)
Sep 10 → Day 3 (Library)
Sep 11 → Day 4 (PE)
```

Open each event and verify the summary/description are reasonable.

New events also contain an internal ownership marker in the description so the integration can distinguish its own events from unrelated calendar events during selective deletion/regeneration.

---

## 10. Test adding a non-school day

Set the native `Non-school day` date entity to a test date, for example:

```text
September 10, 2026
```

Press:

```text
Add non-school day
```

Verify:

1. the non-school-day status/count changes;
2. the date appears in the `Existing non-school day` select;
3. the value remains after restarting Home Assistant.

Then test:

```text
Remove selected non-school day
```

and confirm it disappears from the stored list/select.

---

## 11. Test holiday loading

Set a school-year start date and press:

```text
Load holidays
```

The integration should load holidays for the configured US state for both the start year and following year.

Verify the holiday status sensor/list updates.

Then test:

```text
Delete holidays
```

and confirm the holiday data clears without deleting manually-entered non-school dates.

---

## 12. Test single-date calendar deletion

This is one of the most important tests because the custom integration is specifically intended to eliminate the old whole-calendar wipe workflow.

First generate the September 8–11 test events.

Then set:

```text
Non-school day = September 10, 2026
```

Press:

```text
Delete generated events on selected date
```

Expected result:

```text
Sep 8  Day 1 remains
Sep 9  Day 2 remains
Sep 10 Day 3 is deleted
Sep 11 Day 4 remains
```

No calendar UID should need to be entered manually.

The integration queries the calendar, obtains the event UID internally, checks that the event is a School Cycle Days-generated event, and calls the calendar entity's delete API.

---

## 13. Test selective range regeneration

Recreate the test cycle if necessary.

Manually add an unrelated event to the same test calendar, for example:

```text
September 9, 2026
Dentist Appointment
```

Now set:

```text
School year start = September 10, 2026
School year end   = September 11, 2026
```

Press:

```text
Regenerate selected range
```

Expected result:

```text
Sep 8 generated cycle event          untouched
Sep 9 generated cycle event          untouched
Sep 9 Dentist Appointment            untouched
Sep 10 generated cycle event         deleted/recreated
Sep 11 generated cycle event         deleted/recreated
```

The unrelated calendar event must survive.

If it does not, stop testing against any production calendar and investigate before proceeding.

---

## 14. Test a realistic snow-day workflow

Generate a Monday-through-Friday cycle:

```text
Monday    → Day 1
Tuesday   → Day 2
Wednesday → Day 3
Thursday  → Day 4
Friday    → Day 5
```

Now simulate Wednesday becoming a snow day.

Set:

```text
Non-school day = Wednesday's date
```

Press:

```text
Add non-school day
```

Then set the regeneration start date to Wednesday and end date through the remainder of the test range.

Press:

```text
Regenerate selected range
```

Desired result:

```text
Monday    → Day 1
Tuesday   → Day 2
Wednesday → no cycle day
Thursday  → Day 3
Friday    → Day 4
```

This is the core real-world workflow the integration needs to support cleanly from the UI.

---

## 15. Verify old AppDaemon helper compatibility

Only after the native workflow works should you test legacy compatibility.

With AppDaemon disabled or otherwise isolated from the test calendar, press one or more of the existing helper buttons, such as:

```text
input_button.add_non_school_day
input_button.cycle_day_list_holidays
input_button.rerun_calendar_cycle_days
input_button.delete_and_rerun_calendar_cycle_days
```

The custom integration should still respond to the old helper/button workflow.

Do not run AppDaemon and the custom integration against the same legacy buttons simultaneously or both applications may execute.

---

# Development workflow: when do changes appear in Home Assistant?

This is the most important section when actively developing the integration.

## UI value changes: immediate

Changes made through integration-owned HA entities are immediate.

Examples:

```text
Change School year start
Change Cycle Day 3 text
Toggle Include weekends
Change Starting cycle day
Select a non-school date
```

These changes are written to the integration's persistent UI state and should immediately appear in HA.

No Home Assistant restart is required.

---

## Config Flow / Configure changes: integration reload

Changes made from:

```text
Settings
→ Devices & services
→ School Cycle Days
→ Configure
```

are config-entry/options changes.

The integration is designed to reload its config entry so new options such as the target calendar or holiday state take effect without requiring you to manually edit YAML.

If a Configure change appears stale, reload the integration or restart HA before treating it as a code defect.

---

## Python source-code changes: restart Home Assistant

Changes to files such as:

```text
__init__.py
manager.py
button.py
date.py
text.py
number.py
switch.py
select.py
entity.py
ui_state.py
config_flow.py
```

should be treated as requiring a **Home Assistant restart**.

Why:

Python modules are imported into the running Home Assistant process. Merely saving a changed `.py` file does not replace the already-imported module objects/classes in memory.

Even though the integration supports config-entry unload/reload, an integration reload is not a dependable Python source-code hot-reload mechanism because the Python modules themselves remain imported in the process.

For reliable testing:

```text
1. Edit code.
2. Save/copy the changed files to /config/custom_components/school_cycle_days/.
3. Restart Home Assistant.
4. Check logs.
5. Hard-refresh the browser if frontend/config-flow metadata looks stale.
6. Test the change.
```

---

## `manifest.json` changes: restart Home Assistant

Always restart after changing:

```text
manifest.json
```

This includes:

```text
version
requirements
config_flow
dependencies
after_dependencies
iot_class
```

Requirement/dependency changes especially require the integration to be loaded again so Home Assistant can process/install them correctly.

---

## `config_flow.py`, `strings.json`, translations: restart + possibly hard refresh

After changing:

```text
config_flow.py
strings.json
translations/en.json
```

restart Home Assistant.

The Home Assistant frontend caches config-flow/integration localization data aggressively, so if old labels or an old setup form remain visible after restart, hard-refresh the browser.

Do not assume the source update failed until you have done both:

```text
Home Assistant restart
+
Browser hard refresh
```

---

## `services.yaml` changes

For dependable development, restart Home Assistant after modifying `services.yaml`.

The actual registered service handlers live in Python; `services.yaml` primarily supplies UI descriptions/schema metadata shown by Home Assistant. A restart avoids stale service UI metadata while testing.

---

## Dashboard YAML changes

Changes to a Lovelace/dashboard YAML configuration are separate from Python integration changes.

Depending on how your dashboard is managed, a browser refresh or dashboard reload may be sufficient.

A Home Assistant Core restart is generally not required just because you changed the example dashboard YAML.

---

## GitHub changes are not automatically deployed to Home Assistant

Pushing a commit to this GitHub branch does **not** automatically update the files already installed under:

```text
/config/custom_components/school_cycle_days/
```

Unless you later build an automated deployment/HACS update workflow, these are separate copies.

So after changing code in your local Git clone/GitHub branch, you must get the updated files into HA's `custom_components` directory before restarting.

A typical manual development loop is:

```text
Edit local repo
    ↓
Commit/push if desired
    ↓
Copy/sync changed custom component files into HA /config/custom_components/school_cycle_days
    ↓
Restart Home Assistant
    ↓
Check logs
    ↓
Test in UI
```

---

# Faster local development options

If you plan to iterate frequently, manually copying files every time will become tedious.

Useful approaches include:

1. **Edit the integration directly in `/config/custom_components/school_cycle_days/`** using Studio Code Server, then copy/commit the finished changes back into the repository.
2. **Use a file-sync command/script** from your development machine to the HA config share, then restart HA.
3. If your HA config is available as a network share, keep a scripted `robocopy`, `rsync`, or similar one-command deployment step.
4. Later, when the integration has its own HACS-ready repository, use HACS for versioned installs/updates. HACS is useful for releases, but it is not as convenient as direct file sync for rapid edit/restart/test development.

For this project, a file-sync + restart workflow is probably the best balance between keeping the source in Git and testing quickly in your real HA instance.

---

# Recommended test checklist

Use this as a compact acceptance checklist.

## Installation

- [ ] Files exist under `/config/custom_components/school_cycle_days/`.
- [ ] Home Assistant restarted successfully.
- [ ] No `school_cycle_days` setup errors in logs.
- [ ] School Cycle Days appears under Add Integration.
- [ ] Integration can be configured entirely from the UI.

## Native entities

- [ ] Start/end/non-school Date entities work.
- [ ] Five cycle Text entities work.
- [ ] Starting-cycle Number entity is constrained to 1–5.
- [ ] Holiday/weekend Switch entities work.
- [ ] Select entities populate correctly.
- [ ] Button entities execute correctly.
- [ ] Native settings survive HA restart.

## Data

- [ ] Existing helper values seed the native controls on first migration.
- [ ] Add non-school date works.
- [ ] Remove non-school date works.
- [ ] Clear non-school dates works.
- [ ] Load holidays works.
- [ ] Delete holidays does not erase manually-added non-school dates.

## Calendar

- [ ] Generate short cycle range works.
- [ ] Generated summaries are correct.
- [ ] Delete generated events on one date removes only that date.
- [ ] Selective range regeneration works.
- [ ] Unrelated calendar events survive regeneration.
- [ ] Snow-day cycle shift works correctly.
- [ ] Existing AppDaemon-style generated events can be selectively recognized/deleted.

## Compatibility

- [ ] Old helper buttons still work when AppDaemon is disabled/isolated.
- [ ] Production calendar has not been used until all test-calendar cases pass.

---

# Troubleshooting information to capture

If something fails, collect:

1. the exact button/control/action used;
2. the date/cycle values visible in the UI;
3. the target calendar entity ID;
4. the full Home Assistant traceback from Settings → System → Logs;
5. whether HA had been restarted after the last Python change;
6. whether the browser was hard-refreshed after config-flow/string changes;
7. whether the copied files under `/config/custom_components/school_cycle_days/` actually contain the latest code.

The complete traceback is much more useful than the final one-line error message.

---

# Bottom line

For normal use after installation, the goal is **UI-only operation**:

```text
Change dates/labels/settings in Home Assistant UI
→ press native School Cycle Days buttons
→ calendar updates
```

For development, the expected loop is:

```text
Change Python/source code
→ deploy/copy source into /config/custom_components
→ restart Home Assistant
→ hard-refresh browser when needed
→ test in UI
```

Do not expect Git commits or Python file saves to appear live in the running Home Assistant process without a restart.
