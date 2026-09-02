"""Business logic for the standalone School Cycle Days application."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import holidays

from .database import Database
from .ha_client import HomeAssistantClient

GENERATED_MARKER = "[school_cycle_days]"


class SchoolCycleDaysService:
    """Own cycle logic independently of Home Assistant."""

    def __init__(self, database: Database, ha: HomeAssistantClient) -> None:
        self.database = database
        self.ha = ha

    def settings(self) -> dict[str, Any]:
        return self.database.get_settings()

    def update_settings(self, values: dict[str, Any]) -> None:
        self.database.update_settings(values)

    def add_non_school_day(self, day: str) -> None:
        parsed = date.fromisoformat(day)
        self.database.add_non_school_day(parsed.isoformat(), source="manual")

    def delete_non_school_day(self, day: str) -> None:
        self.database.delete_non_school_day(date.fromisoformat(day).isoformat())

    def clear_non_school_days(self) -> None:
        self.database.clear_non_school_days()

    def load_holidays(self) -> int:
        settings = self.settings()
        start = self._require_date(settings, "school_year_start")
        end = self._require_date(settings, "school_year_end")
        state = str(settings.get("us_state") or "NH")
        values = holidays.US(state=state, years=range(start.year, end.year + 1))
        selected = [
            (holiday_date.isoformat(), str(name))
            for holiday_date, name in values.items()
            if start <= holiday_date <= end
        ]
        selected.sort(key=lambda item: item[0])
        self.database.replace_holidays(selected)
        return len(selected)

    def clear_holidays(self) -> None:
        self.database.clear_holidays()

    async def generate(self, *, start: date | None = None, end: date | None = None) -> dict[str, int]:
        settings = self.settings()
        start = start or self._require_date(settings, "school_year_start")
        end = end or self._require_date(settings, "school_year_end")
        if end < start:
            raise ValueError("School year end must not be before start")

        calendar = str(settings.get("calendar_entity") or "")
        if not calendar:
            raise ValueError("Select a Home Assistant calendar first")

        cycle_days = [str(settings.get(f"cycle_day_{index}") or "").strip() for index in range(1, 6)]
        if any(not value for value in cycle_days):
            raise ValueError("All five cycle-day descriptions are required")

        day_number = int(settings.get("starting_cycle_day") or 1)
        if day_number not in range(1, 6):
            day_number = 1

        blocked = self.database.blocked_days()
        include_no_school = bool(settings.get("include_no_school_events", False))
        include_weekends = bool(settings.get("include_weekend_events", False))

        counts = {"school_days": 0, "non_school_days": 0, "weekend_days": 0}
        current = start
        while current <= end:
            iso = current.isoformat()
            next_day = (current + timedelta(days=1)).isoformat()
            if current.weekday() < 5 and iso not in blocked:
                description = cycle_days[day_number - 1]
                await self.ha.create_event(
                    calendar,
                    start_date=iso,
                    end_date=next_day,
                    summary=f"Day {day_number} ({description})",
                    description=f"{description}\n{GENERATED_MARKER}",
                )
                counts["school_days"] += 1
                day_number = 1 if day_number == 5 else day_number + 1
            elif current.weekday() < 5:
                counts["non_school_days"] += 1
                if include_no_school:
                    await self.ha.create_event(
                        calendar,
                        start_date=iso,
                        end_date=next_day,
                        summary="No School",
                        description=f"Holiday / Non-School Day\n{GENERATED_MARKER}",
                    )
            else:
                counts["weekend_days"] += 1
                if include_weekends:
                    await self.ha.create_event(
                        calendar,
                        start_date=iso,
                        end_date=next_day,
                        summary="No School",
                        description=f"Weekend\n{GENERATED_MARKER}",
                    )
            current += timedelta(days=1)
        return counts

    async def regenerate(self, *, start: date | None = None, end: date | None = None) -> dict[str, Any]:
        settings = self.settings()
        start = start or self._require_date(settings, "school_year_start")
        end = end or self._require_date(settings, "school_year_end")
        deleted = await self.delete_generated_events(start, end)
        created = await self.generate(start=start, end=end)
        return {"deleted": deleted, **created}

    async def delete_generated_events(self, start: date, end: date) -> int:
        settings = self.settings()
        calendar = str(settings.get("calendar_entity") or "")
        if not calendar:
            raise ValueError("Select a Home Assistant calendar first")

        ha_config = await self.ha.config()
        timezone_name = str(ha_config.get("time_zone") or "UTC")
        timezone = ZoneInfo(timezone_name)
        start_dt = datetime.combine(start, time.min, tzinfo=timezone)
        end_dt = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone)
        events = await self.ha.events(calendar, start_dt.isoformat(), end_dt.isoformat())

        deleted = 0
        for event in events:
            if not self._is_generated_event(event):
                continue
            uid = event.get("uid")
            if not uid:
                continue
            await self.ha.delete_event(
                calendar,
                str(uid),
                recurrence_id=event.get("recurrence_id"),
            )
            deleted += 1
        return deleted

    async def delete_generated_events_on_day(self, day: date) -> int:
        return await self.delete_generated_events(day, day)

    @staticmethod
    def _is_generated_event(event: dict[str, Any]) -> bool:
        summary = str(event.get("summary") or "")
        description = str(event.get("description") or "")
        if GENERATED_MARKER in description:
            return True
        # Compatibility with events written by the original AppDaemon version.
        if summary.startswith("Day ") and "(" in summary and summary.endswith(")"):
            return True
        return summary == "No School" and description in {
            "Holiday",
            "Weekend",
            "Holiday / Non-School Day",
        }

    @staticmethod
    def _require_date(settings: dict[str, Any], key: str) -> date:
        raw = str(settings.get(key) or "")
        if not raw:
            raise ValueError(f"{key.replace('_', ' ').title()} is required")
        return date.fromisoformat(raw)
