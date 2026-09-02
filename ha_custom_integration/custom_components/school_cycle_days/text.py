"""Text controls for School Cycle Days."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SETTING_CYCLE_PREFIX
from .entity import SchoolCycleDaysEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    ui = hass.data[DOMAIN][entry.entry_id]["ui"]
    async_add_entities(
        [
            SchoolCycleDaysText(
                entry,
                ui,
                f"{SETTING_CYCLE_PREFIX}{index}",
                f"Cycle day {index}",
            )
            for index in range(1, 6)
        ]
    )


class SchoolCycleDaysText(SchoolCycleDaysEntity, TextEntity):
    """A cycle-day description editable from the UI."""

    _attr_native_min = 1
    _attr_native_max = 100

    def __init__(self, entry, ui_state, key: str, name: str) -> None:
        super().__init__(entry, ui_state, key)
        self._attr_name = name

    @property
    def native_value(self) -> str:
        return str(self.ui_state.get(self.key, ""))

    async def async_set_value(self, value: str) -> None:
        await self.ui_state.async_set(self.key, value.strip())
