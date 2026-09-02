"""Date controls for School Cycle Days."""

from __future__ import annotations

from datetime import date

from homeassistant.components.date import DateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SETTING_ADDED_DATE, SETTING_END_DATE, SETTING_START_DATE
from .entity import SchoolCycleDaysEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    ui = hass.data[DOMAIN][entry.entry_id]["ui"]
    async_add_entities(
        [
            SchoolCycleDaysDate(entry, ui, SETTING_START_DATE, "School year start"),
            SchoolCycleDaysDate(entry, ui, SETTING_END_DATE, "School year end"),
            SchoolCycleDaysDate(entry, ui, SETTING_ADDED_DATE, "Non-school day"),
        ]
    )


class SchoolCycleDaysDate(SchoolCycleDaysEntity, DateEntity):
    """A date editable from the Home Assistant UI."""

    def __init__(self, entry, ui_state, key: str, name: str) -> None:
        super().__init__(entry, ui_state, key)
        self._attr_name = name

    @property
    def native_value(self) -> date | None:
        value = self.ui_state.get(self.key)
        return date.fromisoformat(value) if value else None

    async def async_set_value(self, value: date) -> None:
        await self.ui_state.async_set(self.key, value.isoformat())
