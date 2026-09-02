"""Number controls for School Cycle Days."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SETTING_DAY_NUMBER
from .entity import SchoolCycleDaysEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    ui = hass.data[DOMAIN][entry.entry_id]["ui"]
    async_add_entities([SchoolCycleDaysRestartDay(entry, ui)])


class SchoolCycleDaysRestartDay(SchoolCycleDaysEntity, NumberEntity):
    """Starting cycle day control."""

    _attr_name = "Starting cycle day"
    _attr_native_min_value = 1
    _attr_native_max_value = 5
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, entry, ui_state) -> None:
        super().__init__(entry, ui_state, SETTING_DAY_NUMBER)

    @property
    def native_value(self) -> float:
        return float(self.ui_state.get(self.key, 1))

    async def async_set_native_value(self, value: float) -> None:
        await self.ui_state.async_set(self.key, int(value))
