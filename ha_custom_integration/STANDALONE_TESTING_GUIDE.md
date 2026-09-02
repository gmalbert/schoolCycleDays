# School Cycle Days — Standalone Testing Guide

This is the acceptance test plan for the **HA-independent standalone product**.

The older `LOCAL_TESTING_GUIDE.md` applies only to the interim HA-native custom integration.

The most important rule is:

> Test the standalone calendar with Home Assistant completely unconfigured first.

Optional integrations are tested only after the local calendar, SQLite schedule, REST API, and ICS feed pass.

---

# 1. Get the branch

```bash
git fetch origin
git switch update/move-to-python-custom-integration
git pull
```

Then:

```bash
cd ha_custom_integration/standalone_app
```

---

# 2. Create the environment

## Windows Git Bash

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -e '.[dev]'
```

## Linux/macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Copy the example environment:

```bash
cp .env.example .env
```

For the first test, leave all integration values blank:

```dotenv
SCD_DATABASE_PATH=./data/school_cycle_days.sqlite3
SCD_HOST=0.0.0.0
SCD_PORT=8088

SCD_HA_URL=
SCD_HA_TOKEN=
SCD_MQTT_HOST=
```

This is deliberate.

If the app does not work in this state, the architecture has regressed.

---

# 3. Run static/unit validation

```bash
python -m compileall school_cycle_days tests
pytest -q
```

Core tests should not require Home Assistant.

Current test areas include:

- cycle advancement;
- no-school-day pause behavior;
- weekend behavior;
- standalone schedule rows;
- local ICS generation;
- external ICS filtering;
- malformed trailing VEVENT repair;
- legacy generated-event recognition for the optional HA adapter.

Do not continue to production data if syntax or unit tests fail.

---

# 4. Start the standalone app

```bash
uvicorn school_cycle_days.main:app --reload --host 0.0.0.0 --port 8088
```

Open:

```text
http://localhost:8088
```

Expected:

- app loads even though HA is blank;
- no HA connection error is required for the app to function;
- month calendar is visible;
- settings panel is visible;
- `.ics` import is visible;
- non-school-day management is visible;
- holiday controls are visible;
- outputs/integrations panel is visible.

---

# 5. Verify health endpoint without HA

Open:

```text
http://localhost:8088/api/v1/health
```

Expected shape:

```json
{
  "status": "ok",
  "standalone": true,
  "home_assistant_configured": false,
  "mqtt_configured": false,
  "schedule_rows": 0
}
```

`schedule_rows` may be non-zero if you already configured the app.

The critical fields are:

```text
status = ok
standalone = true
```

with HA disabled.

---

# 6. Configure a small deterministic school range

Use the UI:

```text
School year start: 2026-09-08
School year end:   2026-09-14

Cycle Day 1: Art
Cycle Day 2: Music
Cycle Day 3: Library
Cycle Day 4: PE
Cycle Day 5: STEM

Starting cycle day: 1
```

For this test, clear/leave empty:

- non-school days;
- holidays.

Save.

Expected school days:

```text
Tue Sep 8  -> Day 1 Art
Wed Sep 9  -> Day 2 Music
Thu Sep 10 -> Day 3 Library
Fri Sep 11 -> Day 4 PE
Sat Sep 12 -> Weekend
Sun Sep 13 -> Weekend
Mon Sep 14 -> Day 5 STEM
```

The month calendar should display these results directly.

---

# 7. Verify cycle progression through the API

Open:

```text
/api/v1/schedule?start=2026-09-08&end=2026-09-14
```

Verify:

- each date exists exactly once;
- school rows have `kind=school`;
- weekend rows have `kind=weekend`;
- cycle-day values are 1,2,3,4,5 only on school dates;
- weekends do not advance the cycle.

---

# 8. Test manual no-school day / snow-day shifting

Add:

```text
2026-09-10
```

as a non-school day.

The schedule should automatically recalculate to:

```text
Sep 8  -> Day 1 Art
Sep 9  -> Day 2 Music
Sep 10 -> No School
Sep 11 -> Day 3 Library
Sep 12 -> Weekend
Sep 13 -> Weekend
Sep 14 -> Day 4 PE
```

This is the central business rule.

Verify it both:

- visually in the standalone calendar;
- through `/api/v1/schedule`.

Then remove Sep 10 and confirm the cycle returns to the original sequence.

---

# 9. Test holiday generation

Set a school-year range that includes a known state holiday.

Press:

```text
Load / refresh holidays
```

Verify:

- holiday appears in the Holidays list;
- matching date becomes No School in the standalone schedule;
- cycle progression pauses on that date;
- clearing holidays removes the holiday block after recalculation.

Holiday state should remain independent from manually/imported non-school days.

---

# 10. Test external ICS import

Use an `.ics` containing both unrelated and matching events, for example:

```ics
BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:1
DTSTART;VALUE=DATE:20260921
DTEND;VALUE=DATE:20260922
SUMMARY:No School - Teacher Workshop
END:VEVENT
BEGIN:VEVENT
UID:2
DTSTART;VALUE=DATE:20260922
DTEND;VALUE=DATE:20260923
SUMMARY:Soccer Game
END:VEVENT
BEGIN:VEVENT
UID:3
DTSTART;VALUE=DATE:20260923
DTEND;VALUE=DATE:20260924
SUMMARY:No School
END:VEVENT
END:VCALENDAR
```

Upload through:

```text
Import district/school calendar
```

Choose:

```text
Import No School dates
```

Expected imported dates:

```text
2026-09-21
2026-09-23
```

Expected excluded date:

```text
2026-09-22
```

because `Soccer Game` does not begin with `No School`.

Verify the local calendar immediately recalculates.

---

# 11. Test cleaned ICS download

Upload the same file but choose:

```text
Download cleaned .ics
```

Open the downloaded file.

Expected:

- valid VCALENDAR wrapper;
- only matching `No School...` VEVENTs;
- unrelated events omitted;
- no database changes from download-only mode.

---

# 12. Test malformed final event repair

Prepare an ICS whose last matching VEVENT lacks:

```text
END:VEVENT
```

Upload it.

Expected:

- importer does not crash;
- final event is repaired;
- matching date is imported;
- UI message notes that the final VEVENT was repaired.

This carries forward the behavior of the original `no_school_calendar.py` utility.

---

# 13. Test multi-day no-school event

ICS example:

```ics
BEGIN:VEVENT
DTSTART;VALUE=DATE:20261223
DTEND;VALUE=DATE:20261228
SUMMARY:No School - Winter Break
END:VEVENT
```

Because ICS all-day `DTEND` is exclusive, expected covered dates are:

```text
2026-12-23
2026-12-24
2026-12-25
2026-12-26
2026-12-27
```

The app should deduplicate any dates that already exist.

---

# 14. Test built-in month calendar UX

Verify desktop layout:

- seven-column calendar grid;
- clear month heading;
- previous/next month navigation;
- Today marker;
- cycle day title visible;
- cycle label visible;
- No School visually distinct;
- weekends visually distinct;
- out-of-month dates subdued.

Resize browser/mobile view.

Verify:

- no horizontal page overflow;
- cards remain readable;
- controls remain usable;
- month navigation remains accessible.

Also test browser light and dark appearance.

---

# 15. Test Today / Next School Day summaries

For a date within a configured test schedule, verify:

```text
/api/v1/today
```

matches the UI Today card.

Verify:

```text
/api/v1/next-school-day
```

matches the UI Next School Day card.

If today is Friday and the weekend follows, next-school-day should skip Saturday/Sunday.

If an intervening Monday is No School, it should skip Monday as well.

---

# 16. Test standalone ICS feed

Open:

```text
/calendar.ics
```

Expected:

- valid VCALENDAR;
- school cycle events included;
- deterministic UIDs;
- dates match local schedule;
- no HA connection required.

Toggle:

```text
Include No School events in exported/subscribed ICS feeds
```

and verify No School entries appear/disappear accordingly.

Toggle weekend inclusion and verify the same for weekend entries.

---

# 17. Test persistence

After configuring the app and generating schedule data:

1. stop uvicorn;
2. start it again;
3. refresh the browser.

Expected:

- settings persist;
- imported/manual no-school dates persist;
- holidays persist;
- generated schedule persists;
- calendar renders without requiring re-entry.

Delete the SQLite database only when intentionally resetting the test environment.

---

# 18. Test Docker without HA

From `standalone_app/`:

```bash
docker compose up -d --build
```

Do not define HA/MQTT variables.

Expected:

- container starts;
- `http://localhost:8088` works;
- `/api/v1/health` reports standalone=true;
- calendar can be configured and used;
- `./data` contains the persistent database.

Then:

```bash
docker compose restart
```

Verify persistence.

---

# 19. Optional MQTT / Home Assistant Discovery test

Only after all standalone tests pass.

Configure:

```dotenv
SCD_MQTT_HOST=<broker>
SCD_MQTT_PORT=1883
SCD_MQTT_USERNAME=<optional>
SCD_MQTT_PASSWORD=<optional>
```

Restart the standalone app because environment configuration is read at process startup.

Rebuild the calendar.

Expected retained discovery/state topics create HA sensors for:

```text
Today
Tomorrow
Next School Day
```

Verify sensor attributes include:

```text
day
kind
cycle_day
title
detail
source
```

Stop the MQTT broker temporarily.

Change/rebuild the standalone schedule.

Expected:

- local rebuild still succeeds;
- web calendar still works;
- REST API still works;
- ICS still works.

This verifies integration failure isolation.

---

# 20. Optional direct HA adapter test

Only needed for migration/direct-copy users.

Configure:

```dotenv
SCD_HA_URL=http://homeassistant.local:8123
SCD_HA_TOKEN=<token>
```

Restart app.

Verify:

- HA calendar list appears in optional integration section;
- legacy Helper import is available;
- app still reads local `schedule_days` as authority.

If testing direct calendar publishing, use a disposable HA calendar first.

Do not point AppDaemon and standalone direct-publish operations at the same production calendar simultaneously.

---

# 21. Test legacy Helper import

With original Helpers still present, press:

```text
Import old HA Helpers
```

Verify imported standalone values against HA:

- start/end dates;
- five cycle labels;
- starting cycle day;
- include toggles;
- stored non-school dates;
- stored holidays where available.

Then change a standalone setting.

Expected:

- standalone changes locally;
- old HA Helper does not become authoritative again.

---

# 22. API error cases

Test:

```text
/api/v1/schedule?start=bad-date
```

Expected:

```text
HTTP 400
```

with explanatory JSON.

Test next-school-day after the configured school year ends.

Expected:

```text
HTTP 404
```

rather than a fabricated date.

---

# 23. File upload safety checks

Try uploading:

- non-`.ics` filename;
- >5 MB file;
- empty file;
- ICS with no matching No School events;
- ICS containing malformed unrelated events.

Expected:

- clear UI message;
- app remains running;
- existing schedule/database remains intact.

---

# 24. Acceptance checklist

The standalone architecture is acceptable for production testing when all of these pass:

- [ ] app starts with HA/MQTT blank;
- [ ] settings save locally;
- [ ] cycle sequence is correct;
- [ ] weekends do not advance cycle;
- [ ] manual No School date shifts later cycle days;
- [ ] holidays pause cycle;
- [ ] arbitrary ICS import retains only `SUMMARY:No School...` events;
- [ ] cleaned ICS download works;
- [ ] malformed final VEVENT repair works;
- [ ] multi-day import works;
- [ ] month calendar is readable/responsive;
- [ ] Today/Next School Day cards are correct;
- [ ] `/api/v1/*` outputs are correct;
- [ ] `/calendar.ics` is valid;
- [ ] SQLite survives restart;
- [ ] Docker works with no HA variables;
- [ ] optional MQTT failure does not break core;
- [ ] optional HA adapter remains non-authoritative;
- [ ] AppDaemon can be disabled without losing standalone operation.

---

# 25. Development reload behavior

When using:

```bash
uvicorn school_cycle_days.main:app --reload
```

Python source changes trigger an application-process reload.

Home Assistant never needs to restart because School Cycle Days source changed.

Template changes generally require only browser refresh.

Changes to `.env` require restarting the standalone process.

Docker code changes require:

```bash
docker compose up -d --build
```

They do not require an HA restart.

---

# 26. Before distribution to other users

This acceptance plan validates current functionality, but a general public release also needs productization testing for:

- first-run onboarding;
- authentication;
- CSRF protection;
- backup/restore;
- schema migrations;
- upgrade from one released version to the next;
- Docker multi-architecture images;
- integration credential handling;
- API compatibility across versions.

See:

```text
standalone_app/PRODUCT_ARCHITECTURE_AND_DISTRIBUTION.md
```

for the full v1.0 release criteria.
