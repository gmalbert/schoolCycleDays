"""ICS cleanup/import helpers based on the original no_school_calendar.py behavior."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from icalendar import Calendar


@dataclass(slots=True)
class NoSchoolEvent:
    """A cleaned No School VEVENT extracted from an uploaded calendar."""

    summary: str
    start: date
    end: date
    raw_event: bytes

    @property
    def dates(self) -> list[date]:
        """Return every calendar date covered by the event.

        ICS DTEND is exclusive for all-day events. Timed events are treated as
        belonging to their DTSTART date unless they cross midnight.
        """
        values: list[date] = []
        current = self.start
        while current < self.end:
            values.append(current)
            current += timedelta(days=1)
        return values or [self.start]


@dataclass(slots=True)
class NoSchoolImportResult:
    """Result of cleaning an uploaded ICS file."""

    events: list[NoSchoolEvent]
    clean_ics: bytes
    repaired_final_event: bool = False

    @property
    def dates(self) -> list[date]:
        return sorted({day for event in self.events for day in event.dates})


def clean_no_school_calendar(raw: bytes) -> NoSchoolImportResult:
    """Keep only VEVENTs whose SUMMARY begins with ``No School``.

    This intentionally preserves the original helper script's matching rule,
    while accepting case differences and malformed files whose final VEVENT is
    missing END:VEVENT. The returned ICS is a fresh, valid calendar containing
    only matching events.
    """
    text = raw.decode("utf-8-sig", errors="replace")
    event_blocks, repaired = _extract_event_blocks(text)
    matching: list[NoSchoolEvent] = []

    output = Calendar()
    output.add("prodid", "-//School Cycle Days Clean Calendar//EN")
    output.add("version", "2.0")
    output.add("calscale", "GREGORIAN")
    output.add("method", "PUBLISH")

    for block in event_blocks:
        wrapped = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
            + block.strip("\r\n")
            + "\r\nEND:VCALENDAR\r\n"
        ).encode("utf-8")
        try:
            parsed = Calendar.from_ical(wrapped)
        except Exception:
            continue
        for component in parsed.walk("VEVENT"):
            summary = str(component.get("summary", "")).strip()
            if not summary.lower().startswith("no school"):
                continue
            start, end = _event_dates(component)
            output.add_component(component)
            matching.append(
                NoSchoolEvent(
                    summary=summary,
                    start=start,
                    end=end,
                    raw_event=component.to_ical(),
                )
            )

    return NoSchoolImportResult(
        events=matching,
        clean_ics=output.to_ical(),
        repaired_final_event=repaired,
    )


def _extract_event_blocks(text: str) -> tuple[list[str], bool]:
    """Extract VEVENT blocks and repair a trailing unterminated event."""
    lines = text.splitlines(keepends=True)
    inside = False
    current: list[str] = []
    blocks: list[str] = []
    repaired = False

    for line in lines:
        stripped = line.strip()
        if stripped == "BEGIN:VEVENT":
            inside = True
            current = [line]
            continue
        if not inside:
            continue
        current.append(line)
        if stripped == "END:VEVENT":
            blocks.append("".join(current))
            current = []
            inside = False

    if inside and current:
        if current[-1] and not current[-1].endswith(("\n", "\r")):
            current[-1] += "\r\n"
        current.append("END:VEVENT\r\n")
        blocks.append("".join(current))
        repaired = True

    return blocks, repaired


def _event_dates(component) -> tuple[date, date]:
    """Normalize VEVENT DTSTART/DTEND into an exclusive date range."""
    start_value = component.decoded("dtstart")
    end_prop = component.get("dtend")
    end_value = component.decoded("dtend") if end_prop is not None else None

    start_date = _as_date(start_value)
    if end_value is None:
        return start_date, start_date + timedelta(days=1)

    end_date = _as_date(end_value)
    if end_date <= start_date:
        end_date = start_date + timedelta(days=1)
    return start_date, end_date


def _as_date(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value
