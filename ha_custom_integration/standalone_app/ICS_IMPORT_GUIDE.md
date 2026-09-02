# External ICS Import and No-School Calendar Cleanup

## Purpose

The standalone School Cycle Days app can import an arbitrary `.ics` calendar file directly from your computer. The file does **not** need to already exist in Home Assistant.

The workflow is based on the original:

```text
apps/cycleDays/no_school_calendar.py
```

That script scanned every `VEVENT` in an ICS file and retained only events whose `SUMMARY` began with:

```text
No School
```

It then wrote those events into a new clean `.ics` calendar.

The standalone app carries that behavior forward and integrates it into the browser UI.

---

# UI workflow

Open the standalone app and use:

```text
Import an external .ics school calendar
```

Choose an `.ics` file from your computer.

Two operations are available.

## Clean + import No School dates

This operation:

1. reads the uploaded ICS file;
2. scans its `VEVENT` components;
3. keeps only events whose summary begins with `No School`;
4. discards all other events;
5. converts the dates covered by matching events into standalone non-school days;
6. deduplicates dates already present in SQLite;
7. records newly imported dates with an `ics:<filename>` source.

The original file is never modified.

Example input calendar:

```text
No School - Teacher Workshop       2026-10-09
Football Game                      2026-10-10
No School - Veterans Day           2026-11-11
Parent Conference                  2026-11-18
```

Imported non-school dates:

```text
2026-10-09
2026-11-11
```

The football game and parent conference are ignored.

---

## Download cleaned .ics only

This performs the same filtering but does **not** change the standalone database.

Instead, the browser downloads a new file named approximately:

```text
original_filename_no_school_clean.ics
```

The output calendar contains only matching `No School` events.

This replaces the manual output-file step from the original `no_school_calendar.py` utility.

---

# Matching rule

The original script used this conceptual rule:

```python
SUMMARY:No School...
```

The standalone version intentionally keeps the same behavior.

A matching summary must **begin** with `No School`.

These match:

```text
No School
No School - Teacher Workshop
No School: Winter Break
no school - weather closure
```

Matching is case-insensitive.

These do not match:

```text
District No School Notice
Possible No School Day
School Closed
Teacher Workshop
```

This narrow rule is deliberate so unrelated calendar entries are not accidentally converted into blocked school dates.

A later enhancement could make the matching phrases configurable, but the migration version preserves the original script's intent.

---

# Multi-day events

ICS all-day events use an exclusive `DTEND` value.

For example:

```text
DTSTART;VALUE=DATE:20261223
DTEND;VALUE=DATE:20261227
SUMMARY:No School - Winter Break
```

means the event covers:

```text
2026-12-23
2026-12-24
2026-12-25
2026-12-26
```

All covered dates are imported as non-school dates.

Duplicate dates are collapsed automatically.

---

# Malformed final VEVENT repair

The original script specifically handled an ICS file that ended while still inside a `VEVENT` and automatically appended:

```text
END:VEVENT
```

The standalone importer preserves that recovery behavior.

If the final event is missing `END:VEVENT`, the importer repairs the trailing event before attempting to parse it.

The UI reports when this repair occurred.

This repair is intentionally limited to the final unterminated `VEVENT`; it does not attempt broad speculative repair of arbitrary corrupt ICS syntax.

---

# Clean-calendar output

The generated clean calendar contains a fresh VCALENDAR wrapper:

```text
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//School Cycle Days Clean Calendar//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
...
END:VCALENDAR
```

Only matching `VEVENT` components are included.

Existing event details such as UID, description, start/end dates, and other VEVENT properties are preserved by the `icalendar` parser when possible.

---

# Database behavior

Imported dates are stored in the existing `non_school_days` table.

A date imported from:

```text
district-calendar.ics
```

receives a source similar to:

```text
ics:district-calendar.ics
```

If that date already exists, the import skips it rather than replacing the existing source metadata.

This means a manually-entered date is not relabeled merely because the same date later appears in an ICS import.

---

# File safety

The browser upload is read into memory only for processing.

The app:

- does not modify the source file;
- does not require the file to live on the HA host;
- does not write the uploaded original into Home Assistant;
- does not add the uploaded calendar as a HA calendar entity;
- limits uploads to 5 MB in the current implementation.

Only the cleaned dates are persisted to SQLite when using **Clean + import No School dates**.

---

# Relationship to Home Assistant

ICS cleanup/import is entirely independent of Home Assistant.

This operation works even if HA is temporarily offline because it only needs:

```text
browser upload -> standalone parser -> SQLite
```

Home Assistant is needed later when the app generates, deletes, or regenerates events in the configured target `calendar.*` entity.

---

# Implementation

Parser:

```text
school_cycle_days/ics_import.py
```

Web route:

```text
POST /ics/process
```

UI:

```text
templates/index.html
```

Dependency:

```text
icalendar>=6.1,<7.0
```

---

# Tests

Focused tests live in:

```text
tests/test_ics_import.py
```

They cover:

- retaining only summaries that begin with `No School`;
- excluding unrelated events;
- multi-day all-day event expansion;
- missing final `END:VEVENT` repair;
- case-insensitive matching;
- rejecting summaries where `No School` appears later rather than at the beginning.

Run:

```bash
pytest -q tests/test_ics_import.py
```

or the entire standalone suite:

```bash
pytest -q
```

---

# Recommended real-world test

Before importing your production district calendar:

1. export or download the district `.ics` file;
2. use **Download cleaned .ics only** first;
3. open the cleaned file in a text editor or calendar application;
4. verify it contains only the expected `No School` events;
5. upload the original file again and choose **Clean + import No School dates**;
6. inspect the standalone Non-school days list;
7. verify all expected dates appear and unrelated calendar events do not.

This gives you a visual verification step before any imported dates affect cycle generation.
