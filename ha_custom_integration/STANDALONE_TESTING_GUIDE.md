# School Cycle Days — Standalone Testing Guide

This is the test plan for the preferred standalone architecture.

The older `LOCAL_TESTING_GUIDE.md` applies to the interim HA-native custom integration. Use **this** guide for the standalone app.

## Safety rule

Do not begin with the production school calendar.

Create a disposable HA Local Calendar such as:

```text
calendar.school_cycle_test
```

Keep AppDaemon pointed at the production calendar while the standalone app points at the test calendar.

---

# 1. Get the branch

```bash
git fetch origin
git switch update/move-to-python-custom-integration
git pull
```

Move to:

```bash
cd ha_custom_integration/standalone_app
```

---

# 2. Create the HA token

In Home Assistant:

```text
Profile → Security → Long-Lived Access Tokens → Create Token
```

Use a dedicated token for School Cycle Days.

Do not commit it.

---

# 3. Create `.env`

Windows Git Bash:

```bash
cp .env.example .env
```

Edit:

```dotenv
SCD_HA_URL=http://homeassistant.local:8123
SCD_HA_TOKEN=YOUR_TOKEN
SCD_DATABASE_PATH=./data/school_cycle_days.sqlite3
SCD_VERIFY_SSL=true
SCD_HOST=0.0.0.0
SCD_PORT=8088
```

If `homeassistant.local` does not resolve from the machine running the app, use HA's LAN IP instead.

---

# 4. Python development setup

Requires Python 3.12+.

```bash
python --version
python -m venv .venv
source .venv/Scripts/activate
pip install -e '.[dev]'
```

Run unit tests:

```bash
pytest -q
```

The initial test suite covers:

- cycle advancement;
- non-school-day pause behavior;
- generated-event ownership matching;
- unrelated event preservation;
- delete-then-regenerate behavior.

Run syntax compilation separately if desired:

```bash
python -m compileall school_cycle_days tests
```

---

# 5. Start development server

```bash
uvicorn school_cycle_days.main:app --reload --host 0.0.0.0 --port 8088
```

Open:

```text
http://localhost:8088
```

## Code update behavior

With `--reload`:

- editing Python normally restarts the standalone process automatically;
- Home Assistant does not restart;
- Home Assistant does not need a custom-component reload;
- your SQLite state remains on disk;
- browser template changes normally need only a page refresh.

Changes to `.env` require stopping/restarting Uvicorn because environment settings are loaded at process startup.

---

# 6. Test connectivity first

Open:

```text
http://localhost:8088/health
```

Expected:

```json
{
  "status": "ok",
  "home_assistant": "connected"
}
```

If it fails:

- verify HA URL;
- verify token;
- verify the app host can reach HA;
- check HTTP vs HTTPS;
- check certificate validation;
- test the token manually with curl if necessary.

Example:

```bash
curl \
  -H "Authorization: Bearer $SCD_HA_TOKEN" \
  -H "Content-Type: application/json" \
  "$SCD_HA_URL/api/"
```

---

# 7. Verify calendar discovery

Open the main UI.

The **Home Assistant calendar** dropdown should list HA calendar entities.

Select only:

```text
calendar.school_cycle_test
```

If the calendar list is empty but `/health` succeeds, verify that the token's HA user can read the calendar entity.

---

# 8. Configure a tiny test range

Use four weekdays, for example:

```text
Start: 2026-09-08
End:   2026-09-11
```

Cycle labels:

```text
Day 1: Art
Day 2: Music
Day 3: Library
Day 4: PE
Day 5: STEM
```

Starting cycle day:

```text
1
```

Leave visible No School and weekend entries off initially.

Press:

```text
Save settings
```

Refresh the page and confirm the values remain. This tests SQLite persistence.

---

# 9. Test initial generation

Press:

```text
Generate configured school year
```

Expected HA test-calendar entries:

```text
Sep 8  — Day 1 (Art)
Sep 9  — Day 2 (Music)
Sep 10 — Day 3 (Library)
Sep 11 — Day 4 (PE)
```

Open one event and confirm its description contains:

```text
[school_cycle_days]
```

This marker is critical for safe future deletion.

---

# 10. Test application persistence

Stop Uvicorn with Ctrl+C.

Restart:

```bash
uvicorn school_cycle_days.main:app --reload --host 0.0.0.0 --port 8088
```

Confirm settings still appear.

Add a manual non-school date, restart again, and confirm the date remains.

This verifies School Cycle Days state is independent of HA restart/state restoration.

---

# 11. Test non-school-day cycle pause

First remove/recreate the test events as needed so the range is clean.

Add:

```text
2026-09-09
```

as a non-school day.

Regenerate the four-day range.

Expected sequence:

```text
Sep 8  — Day 1 (Art)
Sep 9  — no cycle-day event
Sep 10 — Day 2 (Music)
Sep 11 — Day 3 (Library)
```

The cycle must pause, not advance, on the blocked date.

---

# 12. Test single-day deletion

Choose a date containing a generated event, e.g.:

```text
2026-09-10
```

Use:

```text
Delete generated events on this date
```

Expected:

- the generated event on Sep 10 disappears;
- Sep 8 and Sep 11 remain;
- no `.ics` file is deleted;
- no HA restart occurs.

This validates remote UID retrieval + WebSocket deletion.

---

# 13. Verify UID availability

The deletion test implicitly verifies that the selected calendar provider returns event UIDs.

If deletion reports zero despite a generated event being present, inspect the HA REST response manually:

```bash
curl \
  -H "Authorization: Bearer $SCD_HA_TOKEN" \
  "$SCD_HA_URL/api/calendars/calendar.school_cycle_test?start=2026-09-10T00:00:00-04:00&end=2026-09-11T00:00:00-04:00"
```

Look for:

```json
"uid": "..."
```

Also confirm the event description contains the ownership marker.

---

# 14. Critical unrelated-event preservation test

Create a manual event in the same HA test calendar:

```text
Sep 10 — Dentist Appointment
```

Its description should **not** contain `[school_cycle_days]`.

Regenerate a range that includes Sep 10.

Expected:

```text
Dentist Appointment remains.
School Cycle Days entries are replaced.
```

If the unrelated event disappears, stop testing and do not use the production calendar.

---

# 15. Test legacy AppDaemon event recognition

Create or retain an old-style event that looks like:

```text
Day 3 (Library)
```

without the new marker.

Run selective regeneration over that date.

The standalone migration logic should recognize the historical event shape and delete it before creating the replacement.

This is intentionally migration compatibility; new events should rely on the explicit ownership marker instead.

---

# 16. Test holidays

Configure:

```text
US state: NH
```

and a school-year range spanning the dates you want.

Press:

```text
Load / refresh holidays
```

Verify holidays appear in the UI.

Generate/regenerate across a known holiday and confirm the cycle does not advance on that blocked weekday.

If **Create visible No School events** is enabled, confirm a No School event appears with the School Cycle Days marker.

---

# 17. Test weekends

Use a range spanning a weekend.

With visible weekend events disabled:

- no weekend events should be created;
- the cycle should not advance.

Enable visible weekend events and regenerate.

Expected weekend entries:

```text
No School
```

with a description containing:

```text
Weekend
[school_cycle_days]
```

---

# 18. Realistic snow-day test

Generate a normal week:

```text
Mon Day 1
Tue Day 2
Wed Day 3
Thu Day 4
Fri Day 5
```

Then add Wednesday as a non-school day.

Regenerate Wednesday through Friday.

Set the starting cycle day for that replacement range appropriately.

Expected end state:

```text
Mon Day 1
Tue Day 2
Wed blocked
Thu Day 3
Fri Day 4
```

A future enhancement should calculate the continuation automatically so you do not have to set the restart day manually.

---

# 19. HA restart independence test

With the standalone app still running, restart Home Assistant.

Expected:

- standalone process stays alive;
- web UI and SQLite data remain available;
- HA-dependent operations fail while HA is down;
- after HA returns, operations work again without restarting the standalone app.

This validates the main architectural benefit.

---

# 20. Standalone restart independence test

Restart the standalone app while leaving HA alone.

Expected:

- HA remains fully functional;
- existing calendar entries remain;
- standalone settings/non-school days/holidays survive because they are in SQLite;
- connection resumes after standalone startup.

---

# 21. Docker test

Stop local Uvicorn first if it uses port 8088.

Run:

```bash
docker compose up -d --build
```

Check:

```bash
docker compose ps
docker compose logs -f
```

Open:

```text
http://localhost:8088
```

Confirm the same database persists under:

```text
./data/
```

when the container is recreated.

---

# 22. Production cutover gate

Do not select the production calendar until all of these pass:

- [ ] unit tests pass;
- [ ] `/health` succeeds;
- [ ] calendar discovery works;
- [ ] settings survive restart;
- [ ] short generation works;
- [ ] non-school day pauses the cycle;
- [ ] holidays behave correctly;
- [ ] single-day deletion works;
- [ ] event UID is available;
- [ ] unrelated event survives regeneration;
- [ ] legacy AppDaemon cycle event can be selectively replaced;
- [ ] HA restart does not lose standalone state;
- [ ] standalone restart does not affect HA;
- [ ] Docker or chosen deployment method is stable.

---

# 23. Production cutover

When ready:

1. disable AppDaemon CycleDays;
2. ensure the HA-native prototype is not active against the production calendar;
3. back up the calendar/data if desired;
4. point standalone settings at the production `calendar.*` entity;
5. perform a small selective regeneration first;
6. verify unrelated events;
7. expand to the remaining school year.

Do not have multiple School Cycle Days implementations mutating the production calendar simultaneously.

---

# 24. Development update cycle

## Plain Python

With:

```bash
uvicorn school_cycle_days.main:app --reload
```

workflow is:

```text
edit Python
→ save
→ Uvicorn automatically restarts app
→ refresh/use UI
```

No Home Assistant restart.

## Git update

```bash
git pull
```

If using editable local Python and Uvicorn reload, updated source is immediately used after the process reloads.

If dependencies in `pyproject.toml` changed:

```bash
pip install -e '.[dev]'
```

again.

## Docker

```bash
git pull
docker compose up -d --build
```

No HA restart.

---

# 25. Useful troubleshooting checks

## Test REST auth

```bash
curl -H "Authorization: Bearer $SCD_HA_TOKEN" "$SCD_HA_URL/api/"
```

## List calendars

```bash
curl -H "Authorization: Bearer $SCD_HA_TOKEN" "$SCD_HA_URL/api/calendars"
```

## App health

```bash
curl http://localhost:8088/health
```

## Unit tests

```bash
pytest -q
```

## Syntax

```bash
python -m compileall school_cycle_days tests
```

## Docker logs

```bash
docker compose logs -f
```

---

# Expected result

When this test plan passes, School Cycle Days should be operationally independent of HA while still using HA as the calendar endpoint:

```text
Standalone web UI / SQLite / Python logic
               |
               | remote authenticated APIs
               v
        Home Assistant calendar
```

No AppDaemon.

No mandatory School Cycle Days custom integration.

No whole-calendar deletion.

No HA restart during normal School Cycle Days development.
