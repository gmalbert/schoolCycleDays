"""Standalone schedule generation and export.

This module has no Home Assistant dependency. It turns app-owned settings,
non-school dates, and holidays into the authoritative schedule stored in SQLite.
"""

from __future__ import annotations

from calendar import Calendar as MonthCalendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from icalendar import Calendar, Event

from .database import Database


@dataclass(slots=True)
class ScheduleSummary:
    school_days: int
    non_school_days: int
    weekend_days: int
    start: date
    end: date


class ScheduleService:
    """Build and expose the standalone School Cycle Days calendar."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def rebuild(self) -> ScheduleSummary:
        settings = self.database.get_settings()
        start = self._required_date(settings, "school_year_start")
        end = self._required_date(settings, "school_year_end")
        if end < start:
            raise ValueError("School year end must not be before school year start")

        labels = [str(settings.get(f"cycle_day_{index}") or "").strip() for index in range(1, 6)]
        if any(not label for label in labels):
            raise ValueError("All five cycle-day descriptions are required")

        cycle_day = int(settings.get("starting_cycle_day") or 1)
        if cycle_day not in range(1, 6):
            cycle_day = 1

        blocked = self.database.blocked_days()
        holidays = self.database.holiday_map()
        rows: list[dict[str, Any]] = []
        counts = {"school": 0, "non_school": 0, "weekend": 0}

        current = start
        while current <= end:
            iso = current.isoformat()
            if current.weekday() >= 5:
                counts["weekend"] += 1
                rows.append(
                    {
                        "day": iso,
                        "kind": "weekend",
                        "cycle_day": None,
                        "title": "Weekend",
                        "detail": "",
                        "source": "generated",
                    }
                )
            elif iso in blocked:
                counts["non_school"] += 1
                detail = holidays.get(iso, "No School")
                rows.append(
                    {
                        "day": iso,
                        "kind": "no_school",
                        "cycle_day": None,
                        "title": "No School",
                        "detail": detail,
                        "source": "holiday" if iso in holidays else "non_school_day",
                    }
                )
            else:
                label = labels[cycle_day - 1]
                counts["school"] += 1
                rows.append(
                    {
                        "day": iso,
                        "kind": "school",
                        "cycle_day": cycle_day,
                        "title": f"Day {cycle_day}",
                        "detail": label,
                        "source": "generated",
                    }
                )
                cycle_day = 1 if cycle_day == 5 else cycle_day + 1
            current += timedelta(days=1)

        self.database.replace_schedule(rows)
        return ScheduleSummary(
            school_days=counts["school"],
            non_school_days=counts["non_school"],
            weekend_days=counts["weekend"],
            start=start,
            end=end,
        )

    def rows(self, start: date | None = None, end: date | None = None) -> list[dict[str, Any]]:
        return self.database.list_schedule(
            start.isoformat() if start else None,
            end.isoformat() if end else None,
        )

    def today(self, day: date | None = None) -> dict[str, Any]:
        target = day or date.today()
        row = self.database.schedule_day(target.isoformat())
        return row or {
            "day": target.isoformat(),
            "kind": "outside_school_year",
            "cycle_day": None,
            "title": "Outside configured school year",
            "detail": "",
            "source": "system",
        }

    def next_school_day(self, after: date | None = None) -> dict[str, Any] | None:
        start = (after or date.today()) + timedelta(days=1)
        for row in self.database.list_schedule(start=start.isoformat()):
            if row["kind"] == "school":
                return row
        return None

    def month_grid(self, year: int, month: int) -> dict[str, Any]:
        calendar = MonthCalendar(firstweekday=6)  # Sunday-first visual calendar.
        weeks: list[list[dict[str, Any]]] = []
        today = date.today()
        for week in calendar.monthdatescalendar(year, month):
            week_rows: list[dict[str, Any]] = []
            for day in week:
                schedule = self.database.schedule_day(day.isoformat())
                week_rows.append(
                    {
                        "date": day,
                        "iso": day.isoformat(),
                        "in_month": day.month == month,
                        "is_today": day == today,
                        "schedule": schedule,
                    }
                )
            weeks.append(week_rows)
        return {"year": year, "month": month, "weeks": weeks}

    def to_ics(self) -> bytes:
        settings = self.database.get_settings()
        calendar = Calendar()
        calendar.add("prodid", "-//School Cycle Days//Standalone Calendar//EN")
        calendar.add("version", "2.0")
        calendar.add("calscale", "GREGORIAN")
        calendar.add("x-wr-calname", "School Cycle Days")

        include_no_school = bool(settings.get("include_no_school_events", False))
        include_weekends = bool(settings.get("include_weekend_events", False))
        for row in self.database.list_schedule():
            if row["kind"] == "weekend" and not include_weekends:
                continue
            if row["kind"] == "no_school" and not include_no_school:
                continue
            event = Event()
            day = date.fromisoformat(row["day"])
            event.add("dtstart", day)
            event.add("dtend", day + timedelta(days=1))
            if row["kind"] == "school":
                event.add("summary", f"{row['title']} ({row['detail']})")
                event.add("description", row["detail"])
            else:
                event.add("summary", row["title"])
                event.add("description", row["detail"])
            event.add("uid", f"school-cycle-days-{row['day']}@local")
            event.add("dtstamp", datetime.utcnow())
            calendar.add_component(event)
        return calendar.to_ical()

    @staticmethod
    def _required_date(settings: dict[str, Any], key: str) -> date:
        raw = str(settings.get(key) or "")
        if not raw:
            raise ValueError(f"{key.replace('_', ' ').title()} is required")
        return date.fromisoformat(raw)
