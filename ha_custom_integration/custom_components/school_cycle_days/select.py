"""Select controls for School Cycle Days."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    SETTING_SELECTED_CALENDAR,
    SETTING_SELECTED_NON_SCHOOL_DAY,
)
from .entity import SchoolCycleDaysEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SchoolCycleDaysNonSchoolSelect(entry, runtime["ui"], runtime["manager"]),
            SchoolCycleDaysCalendarSelect(entry, runtime["ui"]),
        ]
    )


class SchoolCycleDaysNonSchoolSelect(SchoolCycleDaysEntity, SelectEntity):
    """Select one stored non-school day for removal."""

    _attr_name = "Existing non-school day"

    def __init__(self, entry, ui_state, manager) -> None:
        super().__init__(entry, ui_state, SETTING_SELECTED_NON_SCHOOL_DAY)
        self.manager = manager

    @property
    def options(self) -> list[str]:
        values = list(self.manager.data.get("non_school_days", []))
        return values or ["None"]

    @property
    def current_option(self) -> str | None:
        selected = str(self.ui_state.get(self.key, ""))
        return selected if selected in self.options else self.options[0]

    async def async_select_option(self, option: str) -> None:
        await self.ui_state.async_set(self.key, option)


class SchoolCycleDaysCalendarSelect(SchoolCycleDaysEntity, SelectEntity):
    """Select a Local Calendar file for import/export compatibility operations."""

    _attr_name = "Import/export calendar"

    def __init__(self, entry, ui_state) -> None:
        super().__init__(entry, ui_state, SETTING_SELECTED_CALENDAR)

    @property
    def options(self) -> list[str]:
        return self.ui_state.calendar_names() or ["None"]

    @property
    def current_option(self) -> str | None:
        selected = str(self.ui_state.get(self.key, ""))
        return selected if selected in self.options else self.options[0]

    async def async_select_option(self, option: str) -> None:
        await self.ui_state.async_set(self.key, option)
