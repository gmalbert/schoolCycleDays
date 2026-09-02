"""Switch controls for School Cycle Days."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SETTING_INCLUDE_HOLIDAYS, SETTING_INCLUDE_WEEKENDS
from .entity import SchoolCycleDaysEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    ui = hass.data[DOMAIN][entry.entry_id]["ui"]
    async_add_entities(
        [
            SchoolCycleDaysSwitch(entry, ui, SETTING_INCLUDE_HOLIDAYS, "Include no-school weekdays"),
            SchoolCycleDaysSwitch(entry, ui, SETTING_INCLUDE_WEEKENDS, "Include weekends"),
        ]
    )


class SchoolCycleDaysSwitch(SchoolCycleDaysEntity, SwitchEntity):
    """A persistent boolean setting."""

    def __init__(self, entry, ui_state, key: str, name: str) -> None:
        super().__init__(entry, ui_state, key)
        self._attr_name = name

    @property
    def is_on(self) -> bool:
        return bool(self.ui_state.get(self.key, False))

    async def async_turn_on(self, **kwargs) -> None:
        await self.ui_state.async_set(self.key, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.ui_state.async_set(self.key, False)
