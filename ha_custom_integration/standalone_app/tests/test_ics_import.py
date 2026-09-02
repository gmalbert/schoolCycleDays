from __future__ import annotations

from school_cycle_days.ics_import import clean_no_school_calendar


def test_keeps_only_no_school_events_and_extracts_dates():
    raw = b"""BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:1\r\nDTSTART;VALUE=DATE:20261009\r\nDTEND;VALUE=DATE:20261010\r\nSUMMARY:No School - Teacher Workshop\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nUID:2\r\nDTSTART;VALUE=DATE:20261010\r\nDTEND;VALUE=DATE:20261011\r\nSUMMARY:Football Game\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"""

    result = clean_no_school_calendar(raw)

    assert len(result.events) == 1
    assert [day.isoformat() for day in result.dates] == ["2026-10-09"]
    clean = result.clean_ics.decode("utf-8")
    assert "No School - Teacher Workshop" in clean
    assert "Football Game" not in clean


def test_multiday_no_school_event_expands_to_each_covered_date():
    raw = b"""BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:break\r\nDTSTART;VALUE=DATE:20261223\r\nDTEND;VALUE=DATE:20261227\r\nSUMMARY:No School - Winter Break\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"""

    result = clean_no_school_calendar(raw)

    assert [day.isoformat() for day in result.dates] == [
        "2026-12-23",
        "2026-12-24",
        "2026-12-25",
        "2026-12-26",
    ]


def test_repairs_final_event_missing_end_vevent():
    raw = b"""BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:3\nDTSTART;VALUE=DATE:20270115\nSUMMARY:No School - Weather\n"""

    result = clean_no_school_calendar(raw)

    assert result.repaired_final_event is True
    assert len(result.events) == 1
    assert [day.isoformat() for day in result.dates] == ["2027-01-15"]


def test_matching_is_case_insensitive_but_must_start_with_no_school():
    raw = b"""BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:4\r\nDTSTART;VALUE=DATE:20270201\r\nSUMMARY:no school - closure\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nUID:5\r\nDTSTART;VALUE=DATE:20270202\r\nSUMMARY:District No School Notice\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"""

    result = clean_no_school_calendar(raw)

    assert len(result.events) == 1
    assert result.events[0].summary == "no school - closure"
