"""Runtime manager for School Cycle Days.

This module contains the application logic that previously lived in AppDaemon.
It runs inside Home Assistant and therefore reads entity state directly from
``hass.states`` and calls Home Assistant services directly rather than making
REST requests back into the same Home Assistant instance.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import holidays
from icalendar import Calendar

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION

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
        """Load persisted data and publish initial HA state."""
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
        """Return the state for a configured Home Assistant entity."""
        entity_id = self.entities.get(key)
        if not entity_id:
            return default
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            return default
        return state.state

    async def async_handle_button(self, action: str) -> None:
        """Dispatch one of the optional legacy helper buttons."""
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
        }
        handler = handlers.get(action)
        if handler is None:
            _LOGGER.warning("Unknown School Cycle Days action: %s", action)
            return
        try:
            await handler()
        except Exception:  # noqa: BLE001 - surface failures in HA and logs
            _LOGGER.exception("School Cycle Days action failed: %s", action)
            await self._async_message(f"School Cycle Days action failed: {action}")

    async def async_add_non_school_day(self) -> None:
        raw = self.state("added_date")
        if not raw:
            await self._async_message("No date selected.")
            return
        formatted = datetime.strptime(raw, "%Y-%m-%d").strftime("%m/%d/%Y")
        days = set(self.data.get("non_school_days", []))
        if formatted in days:
            await self._async_message("This date already exists.")
            return
        days.add(formatted)
        self.data["non_school_days"] = self._sort_dates(days)
        await self._async_save_and_publish()
        await self._async_message(f"{formatted} added as a non-school day.")

    async def async_delete_non_school_day(self) -> None:
        selected = self.state("non_school_days_dropdown")
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

    async def async_load_holidays(self) -> None:
        start_raw = self.state("start_date")
        if not start_raw:
            await self._async_message("Set the school-year start date first.")
            return
        start_year = datetime.strptime(start_raw, "%Y-%m-%d").year
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

    async def async_create_cycle_days(self) -> None:
        start_raw = self.state("start_date")
        end_raw = self.state("end_date")
        if not start_raw or not end_raw:
            await self._async_message("Set both start and end dates.")
            return

        start = datetime.strptime(start_raw, "%Y-%m-%d").date()
        end = datetime.strptime(end_raw, "%Y-%m-%d").date()
        if end < start:
            await self._async_message("End date must not be before start date.")
            return

        cycle_days = [self.state(f"cycle_day_{n}") for n in range(1, 6)]
        if any(not value for value in cycle_days):
            await self._async_message("Configure all five cycle-day descriptions first.")
            return

        day_number = int(float(self.state("day_number", "1") or "1"))
        if day_number < 1 or day_number > 5:
            day_number = 1

        blocked = set(self.data.get("non_school_days", []))
        blocked.update(self.data.get("holiday_dates", []))
        include_holidays = self.state("include_holidays_in_calendar") == "on"
        include_weekends = self.state("include_weekends_in_calendar") == "on"

        school_days = non_school_days = weekend_days = 0
        current = start
        while current <= end:
            formatted = current.strftime("%m/%d/%Y")
            if current.weekday() < 5 and formatted not in blocked:
                description = cycle_days[day_number - 1]
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

    async def async_add_dates_from_other_calendar(self) -> None:
        """Import 'No School' events from a local-calendar ICS file.

        This keeps compatibility with the original AppDaemon workflow. It only
        applies when ``legacy_calendar_storage_path`` points at HA's Local
        Calendar storage directory.
        """
        if not self.legacy_calendar_storage_path:
            await self._async_message("Legacy calendar storage path is not configured.")
            return

        friendly_name = self.state("calendar_list")
        if not friendly_name:
            await self._async_message("Select a calendar first.")
            return

        path = self._legacy_calendar_file(friendly_name)
        if not path.exists():
            await self._async_message(f"Calendar file not found: {path.name}")
            return

        start = datetime.strptime(self.state("start_date"), "%Y-%m-%d").date()
        end = datetime.strptime(self.state("end_date"), "%Y-%m-%d").date()
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
        if not self.legacy_calendar_storage_path:
            return
        root = Path(self.legacy_calendar_storage_path)
        if not root.exists():
            return
        names = await self.hass.async_add_executor_job(self._calendar_names, root)
        await self._async_set_select_options("calendar_list", names)
        await self._async_set_select_options("calendar_list_for_selection", names)

    async def async_clear_calendar(self) -> None:
        """Clear the selected Local Calendar using the legacy file fallback."""
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

    async def async_clear_and_rerun(self) -> None:
        await self.async_clear_calendar()
        await self.async_create_cycle_days()

    async def async_export_ics(self) -> None:
        if not self.legacy_calendar_storage_path:
            await self._async_message("Legacy calendar storage path is not configured.")
            return
        selected = self.state("calendar_list")
        if not selected:
            await self._async_message("Select a calendar first.")
            return
        source = self._legacy_calendar_file(selected)
        destination = Path(self.hass.config.path("www")) / source.name
        if not source.exists():
            await self._async_message(f"Calendar file not found: {source.name}")
            return
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
        if not entity_id:
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
    def _sort_dates(values: Any) -> list[str]:
        unique = {str(value) for value in values if value and str(value) != "None"}
        return sorted(unique, key=lambda value: datetime.strptime(value, "%m/%d/%Y"))

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
            event_end -= timedelta(days=1)  # RFC5545 all-day DTEND is exclusive.
            current = event_start
            while current <= event_end:
                if start <= current <= end:
                    found.add(current.strftime("%m/%d/%Y"))
                current += timedelta(days=1)
        return sorted(found, key=lambda value: datetime.strptime(value, "%m/%d/%Y"))
