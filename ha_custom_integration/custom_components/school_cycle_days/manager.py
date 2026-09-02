"""Runtime manager for School Cycle Days.

The original project ran in AppDaemon and used Home Assistant helpers as both
configuration and application state. This manager runs inside Home Assistant.
Native services/actions can provide all runtime inputs directly; the historical
helpers remain optional fallbacks so an existing dashboard can continue to work
while it is migrated.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import holidays
from icalendar import Calendar

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


class SchoolCycleDaysManager:
    """Own School Cycle Days state and operations."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        calendar_entity: str,
        entities: dict[str, str],
        buttons: dict[str, str],
        us_state: str,
        legacy_calendar_storage_path: str | None,
    ) -> None:
        self.hass = hass
        self.calendar_entity = calendar_entity
        self.entities = entities
        self.buttons = buttons
        self.us_state = us_state
        self.legacy_calendar_storage_path = legacy_calendar_storage_path
        self.store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, Any] = {
            "non_school_days": [],
            "holiday_dates": [],
            "holiday_names": [],
        }

    async def async_initialize(self) -> None:
        """Load persisted data and initialize compatibility helpers."""
        stored = await self.store.async_load()
        if isinstance(stored, dict):
            self.data.update(stored)
        elif self.legacy_calendar_storage_path:
            await self._async_import_legacy_json_if_present()

        await self._async_publish_state()
        await self.async_refresh_calendar_list()
        await self._async_set_current_calendar()
        await self._async_message("School Cycle Days is ready.")

    def state(self, key: str, default: str = "") -> str:
        """Return a configured helper state, if that helper exists."""
        entity_id = self.entities.get(key)
        if not entity_id:
            return default
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            return default
        return state.state

    async def async_handle_button(self, action: str) -> None:
        """Dispatch an optional legacy input_button."""
        handlers = {
            "rerun": self.async_create_cycle_days,
            "list_holidays": self.async_load_holidays,
            "add_non_school_day": self.async_add_non_school_day,
            "clear_non_school_days": self.async_clear_non_school_days,
            "delete_non_school_day": self.async_delete_non_school_day,
            "delete_calendar_events": self.async_clear_calendar,
            "delete_holidays": self.async_delete_holidays,
            "add_dates_from_other_calendar": self.async_add_dates_from_other_calendar,
            "refresh_calendar_list": self.async_refresh_calendar_list,
            "delete_and_rerun": self.async_clear_and_rerun,
            "export_ics": self.async_export_ics,
        }
        handler = handlers.get(action)
        if handler is None:
            _LOGGER.warning("Unknown School Cycle Days action: %s", action)
            return
        try:
            await handler()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("School Cycle Days action failed: %s", action)
            await self._async_message(f"School Cycle Days action failed: {action}")

    async def async_add_non_school_day(self, day: str | None = None) -> None:
        """Add one non-school day.

        ``day`` is YYYY-MM-DD or MM/DD/YYYY. If omitted, fall back to the
        historical input_datetime.add_non_school_day helper.
        """
        raw = day or self.state("added_date")
        formatted = self._normalize_date(raw)
        if not formatted:
            await self._async_message("No date selected.")
            return
        days = set(self.data.get("non_school_days", []))
        if formatted in days:
            await self._async_message("This date already exists.")
            return
        days.add(formatted)
        self.data["non_school_days"] = self._sort_dates(days)
        await self._async_save_and_publish()
        await self._async_message(f"{formatted} added as a non-school day.")

    async def async_delete_non_school_day(self, day: str | None = None) -> None:
        """Delete one stored non-school day."""
        selected = self._normalize_date(day) if day else self.state("non_school_days_dropdown")
        days = list(self.data.get("non_school_days", []))
        if not selected or selected == "None" or selected not in days:
            await self._async_message("Select a non-school day to delete.")
            return
        days.remove(selected)
        self.data["non_school_days"] = self._sort_dates(days)
        await self._async_save_and_publish()
        await self._async_message(f"{selected} removed as a non-school day.")

    async def async_clear_non_school_days(self) -> None:
        self.data["non_school_days"] = []
        await self._async_save_and_publish()
        await self._async_message("Non-school days have been deleted.")

    async def async_load_holidays(self, start_date: str | None = None) -> None:
        """Load US holidays for the start year and following calendar year."""
        start_raw = start_date or self.state("start_date")
        normalized = self._date_object(start_raw)
        if normalized is None:
            await self._async_message("Set the school-year start date first.")
            return
        start_year = normalized.year
        holiday_data = holidays.US(state=self.us_state, years={start_year, start_year + 1})
        holiday_dates = [day.strftime("%m/%d/%Y") for day in holiday_data]
        holiday_names = sorted(set(str(name) for name in holiday_data.values()))
        self.data["holiday_dates"] = self._sort_dates(holiday_dates)
        self.data["holiday_names"] = holiday_names
        await self._async_save_and_publish()
        await self._async_message(
            f"Loaded {len(holiday_dates)} holiday dates for {self.us_state}."
        )

    async def async_delete_holidays(self) -> None:
        self.data["holiday_dates"] = []
        self.data["holiday_names"] = []
        await self._async_save_and_publish()
        await self._async_message("All holidays have been deleted.")

    async def async_create_cycle_days(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        cycle_days: list[str] | None = None,
        day_number: int | None = None,
        include_holidays: bool | None = None,
        include_weekends: bool | None = None,
    ) -> None:
        """Create cycle-day events.

        Every parameter is optional for backward compatibility. Missing values
        are read from the original HA helpers.
        """
        start = self._date_object(start_date or self.state("start_date"))
        end = self._date_object(end_date or self.state("end_date"))
        if start is None or end is None:
            await self._async_message("Set both start and end dates.")
            return
        if end < start:
            await self._async_message("End date must not be before start date.")
            return

        values = cycle_days or [self.state(f"cycle_day_{n}") for n in range(1, 6)]
        if len(values) != 5 or any(not value for value in values):
            await self._async_message("Provide all five cycle-day descriptions.")
            return

        if day_number is None:
            try:
                day_number = int(float(self.state("day_number", "1") or "1"))
            except ValueError:
                day_number = 1
        if day_number < 1 or day_number > 5:
            day_number = 1

        if include_holidays is None:
            include_holidays = self.state("include_holidays_in_calendar") == "on"
        if include_weekends is None:
            include_weekends = self.state("include_weekends_in_calendar") == "on"

        blocked = set(self.data.get("non_school_days", []))
        blocked.update(self.data.get("holiday_dates", []))

        school_days = non_school_days = weekend_days = 0
        current = start
        while current <= end:
            formatted = current.strftime("%m/%d/%Y")
            if current.weekday() < 5 and formatted not in blocked:
                description = values[day_number - 1]
                await self._async_create_calendar_event(
                    current,
                    f"Day {day_number} ({description})",
                    description,
                )
                school_days += 1
                day_number = 1 if day_number == 5 else day_number + 1
            elif current.weekday() < 5:
                non_school_days += 1
                if include_holidays:
                    await self._async_create_calendar_event(current, "No School", "Holiday")
            else:
                weekend_days += 1
                if include_weekends:
                    await self._async_create_calendar_event(current, "No School", "Weekend")
            current += timedelta(days=1)

        await self._async_message(
            f"School Days added: {school_days}. Non-School Days: {non_school_days}. "
            f"Weekend Days: {weekend_days}."
        )

    async def async_add_dates_from_other_calendar(
        self,
        *,
        calendar_name: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> None:
        """Import events containing 'No School' from a local-calendar ICS file."""
        if not self.legacy_calendar_storage_path:
            await self._async_message("Legacy calendar storage path is not configured.")
            return

        friendly_name = calendar_name or self.state("calendar_list")
        if not friendly_name:
            await self._async_message("Select a calendar first.")
            return

        start = self._date_object(start_date or self.state("start_date"))
        end = self._date_object(end_date or self.state("end_date"))
        if start is None or end is None:
            await self._async_message("Set both start and end dates.")
            return

        path = self._legacy_calendar_file(friendly_name)
        if not path.exists():
            await self._async_message(f"Calendar file not found: {path.name}")
            return

        imported = await self.hass.async_add_executor_job(
            self._read_no_school_dates, path, start, end
        )
        existing = set(self.data.get("non_school_days", []))
        before = len(existing)
        existing.update(imported)
        self.data["non_school_days"] = self._sort_dates(existing)
        await self._async_save_and_publish()
        await self._async_message(
            f"{len(existing) - before} non-school days added from {friendly_name}."
        )

    async def async_refresh_calendar_list(self) -> None:
        """Refresh legacy input_select calendar lists if configured/present."""
        if not self.legacy_calendar_storage_path:
            return
        root = Path(self.legacy_calendar_storage_path)
        if not root.exists():
            return
        names = await self.hass.async_add_executor_job(self._calendar_names, root)
        await self._async_set_select_options("calendar_list", names)
        await self._async_set_select_options("calendar_list_for_selection", names)

    async def async_clear_calendar(self) -> None:
        """Clear the target Local Calendar using the historical file fallback."""
        if not self.legacy_calendar_storage_path:
            await self._async_message(
                "Calendar clearing requires legacy_calendar_storage_path."
            )
            return
        path = self._calendar_entity_file(self.calendar_entity)
        if not path.exists():
            await self._async_message("Calendar is already empty or its file was not found.")
            return
        await self.hass.async_add_executor_job(path.unlink)
        await self.hass.services.async_call(
            "homeassistant",
            "reload_config_entry",
            {"entity_id": self.calendar_entity},
            blocking=True,
        )
        await self._async_message("All calendar events have been removed.")

    async def async_clear_and_rerun(self, **kwargs: Any) -> None:
        await self.async_clear_calendar()
        await self.async_create_cycle_days(**kwargs)

    async def async_export_ics(self, calendar_name: str | None = None) -> None:
        """Export one Local Calendar ICS file to /config/www."""
        if not self.legacy_calendar_storage_path:
            await self._async_message("Legacy calendar storage path is not configured.")
            return
        selected = calendar_name or self.state("calendar_list")
        if not selected:
            await self._async_message("Select a calendar first.")
            return
        source = self._legacy_calendar_file(selected)
        destination_dir = Path(self.hass.config.path("www"))
        destination = destination_dir / source.name
        if not source.exists():
            await self._async_message(f"Calendar file not found: {source.name}")
            return
        await self.hass.async_add_executor_job(destination_dir.mkdir, parents=True, exist_ok=True)
        await self.hass.async_add_executor_job(shutil.copyfile, source, destination)
        await self._async_message(f"Exported {selected} to /local/{source.name}")

    async def _async_create_calendar_event(
        self, event_date: date, summary: str, description: str
    ) -> None:
        await self.hass.services.async_call(
            "calendar",
            "create_event",
            {
                "entity_id": self.calendar_entity,
                "start_date": event_date.isoformat(),
                "end_date": (event_date + timedelta(days=1)).isoformat(),
                "summary": summary,
                "description": description,
            },
            blocking=True,
        )

    async def _async_save_and_publish(self) -> None:
        await self.store.async_save(self.data)
        await self._async_publish_state()

    async def _async_publish_state(self) -> None:
        """Publish read-only compatibility/status sensors and optional select options."""
        non_school_days = list(self.data.get("non_school_days", []))
        holiday_dates = list(self.data.get("holiday_dates", []))
        holiday_names = list(self.data.get("holiday_names", []))

        self.hass.states.async_set(
            "sensor.school_cycle_days_non_school_days",
            len(non_school_days),
            {
                "friendly_name": "School Cycle Days - Non-School Days",
                "No school days": non_school_days,
                "unit_of_measurement": "days",
                "icon": "mdi:calendar-remove",
            },
        )
        self.hass.states.async_set(
            "sensor.school_cycle_days_holidays",
            len(holiday_dates),
            {
                "friendly_name": "School Cycle Days - Holidays",
                "Holiday Dates": holiday_dates,
                "Holidays": holiday_names,
                "unit_of_measurement": "days",
                "icon": "mdi:calendar-star",
            },
        )
        await self._async_set_select_options(
            "non_school_days_dropdown", non_school_days or ["None"]
        )

    async def _async_set_select_options(self, key: str, options: list[str]) -> None:
        entity_id = self.entities.get(key)
        if not entity_id or self.hass.states.get(entity_id) is None:
            return
        await self.hass.services.async_call(
            "input_select",
            "set_options",
            {"entity_id": entity_id, "options": options or ["None"]},
            blocking=True,
        )

    async def _async_message(self, message: str) -> None:
        _LOGGER.info(message)
        entity_id = self.entities.get("system_message")
        if entity_id and self.hass.states.get(entity_id):
            await self.hass.services.async_call(
                "input_text",
                "set_value",
                {"entity_id": entity_id, "value": message[:255]},
                blocking=True,
            )
        self.hass.states.async_set(
            "sensor.school_cycle_days_status",
            message,
            {"friendly_name": "School Cycle Days Status", "icon": "mdi:school"},
        )

    async def _async_set_current_calendar(self) -> None:
        friendly = self.calendar_entity.removeprefix("calendar.").replace("_", " ").title()
        entity_id = self.entities.get("current_calendar")
        if entity_id and self.hass.states.get(entity_id):
            await self.hass.services.async_call(
                "input_text",
                "set_value",
                {"entity_id": entity_id, "value": friendly},
                blocking=True,
            )

    async def _async_import_legacy_json_if_present(self) -> None:
        path = Path(self.legacy_calendar_storage_path or "") / "school_cycle_days.json"
        if not path.exists():
            return

        def _read() -> dict[str, Any]:
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)

        legacy = await self.hass.async_add_executor_job(_read)
        self.data = {
            "non_school_days": self._normalize_legacy_list(legacy.get("No school days")),
            "holiday_dates": self._normalize_legacy_list(legacy.get("Holiday Dates")),
            "holiday_names": self._normalize_legacy_list(legacy.get("Holiday Names")),
        }
        await self.store.async_save(self.data)
        _LOGGER.info("Imported legacy school_cycle_days.json into Home Assistant Store")

    @staticmethod
    def _normalize_date(value: str | None) -> str | None:
        parsed = SchoolCycleDaysManager._date_object(value)
        return parsed.strftime("%m/%d/%Y") if parsed else None

    @staticmethod
    def _date_object(value: str | date | datetime | None) -> date | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value).strip()
        for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _normalize_legacy_list(value: Any) -> list[str]:
        if value in (None, "", [], [[]]):
            return []
        if isinstance(value, list):
            flattened: list[str] = []
            for item in value:
                if isinstance(item, list):
                    flattened.extend(str(entry) for entry in item if entry)
                elif item:
                    flattened.append(str(item))
            return flattened
        return [str(value)]

    @staticmethod
    def _sort_dates(values: Iterable[Any]) -> list[str]:
        normalized = {
            parsed
            for value in values
            if (parsed := SchoolCycleDaysManager._normalize_date(str(value))) is not None
        }
        return sorted(normalized, key=lambda value: datetime.strptime(value, "%m/%d/%Y"))

    @staticmethod
    def _calendar_names(root: Path) -> list[str]:
        names: list[str] = []
        for path in root.glob("*.ics"):
            if path.name == "local_todo.tasks.ics":
                continue
            name = path.stem
            for prefix in ("local_calendar.", "local_"):
                if name.startswith(prefix):
                    name = name[len(prefix) :]
            names.append(name.replace("_", " ").title())
        return sorted(set(names))

    def _legacy_calendar_file(self, friendly_name: str) -> Path:
        slug = friendly_name.strip().lower().replace(" ", "_")
        candidates = [
            Path(self.legacy_calendar_storage_path or "") / f"local_calendar.{slug}.ics",
            Path(self.legacy_calendar_storage_path or "") / f"local_calendar.{slug.replace('_', ' ')}.ics",
            Path(self.legacy_calendar_storage_path or "") / f"local_{slug}.ics",
        ]
        return next((path for path in candidates if path.exists()), candidates[0])

    def _calendar_entity_file(self, entity_id: str) -> Path:
        object_id = entity_id.removeprefix("calendar.")
        root = Path(self.legacy_calendar_storage_path or "")
        candidates = [
            root / f"local_calendar.{object_id}.ics",
            root / f"local_{entity_id}.ics",
            root / f"local_{object_id}.ics",
        ]
        return next((path for path in candidates if path.exists()), candidates[0])

    @staticmethod
    def _read_no_school_dates(path: Path, start: date, end: date) -> list[str]:
        with path.open("rb") as file:
            calendar = Calendar.from_ical(file.read())
        found: set[str] = set()
        for event in calendar.walk("VEVENT"):
            if "No School" not in str(event.get("SUMMARY", "")):
                continue
            start_value = event.decoded("DTSTART")
            end_value = event.decoded("DTEND")
            event_start = start_value.date() if isinstance(start_value, datetime) else start_value
            event_end = end_value.date() if isinstance(end_value, datetime) else end_value
            event_end -= timedelta(days=1)
            current = event_start
            while current <= event_end:
                if start <= current <= end:
                    found.add(current.strftime("%m/%d/%Y"))
                current += timedelta(days=1)
        return sorted(found, key=lambda value: datetime.strptime(value, "%m/%d/%Y"))
