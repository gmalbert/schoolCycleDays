"""Persistent UI-editable state for School Cycle Days."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_CYCLE_DAYS,
    DOMAIN,
    SETTING_ADDED_DATE,
    SETTING_CYCLE_PREFIX,
    SETTING_DAY_NUMBER,
    SETTING_END_DATE,
    SETTING_INCLUDE_HOLIDAYS,
    SETTING_INCLUDE_WEEKENDS,
    SETTING_SELECTED_CALENDAR,
    SETTING_SELECTED_NON_SCHOOL_DAY,
    SETTING_START_DATE,
)

SIGNAL_UI_UPDATED = f"{DOMAIN}_ui_updated"
UI_STORAGE_VERSION = 1


class SchoolCycleDaysUIState:
    """Store values that users edit through native Home Assistant entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        *,
        legacy_calendar_storage_path: str | None,
    ) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.legacy_calendar_storage_path = legacy_calendar_storage_path
        self.store: Store[dict[str, Any]] = Store(
            hass, UI_STORAGE_VERSION, f"{DOMAIN}.ui.{entry_id}"
        )
        today = dt_util.now().date()
        self.values: dict[str, Any] = {
            SETTING_START_DATE: today.isoformat(),
            SETTING_END_DATE: (today + timedelta(days=280)).isoformat(),
            SETTING_ADDED_DATE: today.isoformat(),
            SETTING_DAY_NUMBER: 1,
            SETTING_INCLUDE_HOLIDAYS: False,
            SETTING_INCLUDE_WEEKENDS: False,
            SETTING_SELECTED_CALENDAR: "",
            SETTING_SELECTED_NON_SCHOOL_DAY: "",
            **{
                f"{SETTING_CYCLE_PREFIX}{index}": label
                for index, label in enumerate(DEFAULT_CYCLE_DAYS, start=1)
            },
        }

    async def async_load(self) -> bool:
        """Load UI state. Return True when native state already existed."""
        stored = await self.store.async_load()
        if isinstance(stored, dict):
            self.values.update(stored)
            return True
        return False

    async def async_seed_from_legacy(self, manager: Any) -> None:
        """Seed first-run native controls from the user's existing HA helpers."""
        simple = {
            SETTING_START_DATE: manager.state("start_date"),
            SETTING_END_DATE: manager.state("end_date"),
            SETTING_ADDED_DATE: manager.state("added_date"),
            SETTING_SELECTED_CALENDAR: manager.state("calendar_list"),
        }
        for key, value in simple.items():
            if value:
                self.values[key] = value

        restart = manager.state("day_number")
        if restart:
            try:
                self.values[SETTING_DAY_NUMBER] = max(1, min(5, int(float(restart))))
            except ValueError:
                pass

        for index in range(1, 6):
            value = manager.state(f"cycle_day_{index}")
            if value:
                self.values[f"{SETTING_CYCLE_PREFIX}{index}"] = value

        include_holidays = manager.state("include_holidays_in_calendar")
        include_weekends = manager.state("include_weekends_in_calendar")
        if include_holidays:
            self.values[SETTING_INCLUDE_HOLIDAYS] = include_holidays == "on"
        if include_weekends:
            self.values[SETTING_INCLUDE_WEEKENDS] = include_weekends == "on"

        await self.store.async_save(self.values)

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    async def async_set(self, key: str, value: Any) -> None:
        self.values[key] = value
        await self.store.async_save(self.values)
        async_dispatcher_send(self.hass, SIGNAL_UI_UPDATED, self.entry_id)

    @callback
    def cycle_days(self) -> list[str]:
        return [
            str(self.values.get(f"{SETTING_CYCLE_PREFIX}{index}", ""))
            for index in range(1, 6)
        ]

    def calendar_names(self) -> list[str]:
        """Return legacy Local Calendar names available for import/export."""
        if not self.legacy_calendar_storage_path:
            return []
        root = Path(self.legacy_calendar_storage_path)
        if not root.exists():
            return []
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
