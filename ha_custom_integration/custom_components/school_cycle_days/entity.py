"""Base entities for School Cycle Days."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .ui_state import SIGNAL_UI_UPDATED, SchoolCycleDaysUIState


class SchoolCycleDaysEntity(Entity):
    """Base class for integration-owned UI entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        ui_state: SchoolCycleDaysUIState,
        key: str,
    ) -> None:
        self.entry = entry
        self.ui_state = ui_state
        self.key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="School Cycle Days",
            model="Home Assistant Custom Integration",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UI_UPDATED,
                self._handle_ui_update,
            )
        )

    def _handle_ui_update(self, entry_id: str) -> None:
        if entry_id == self.entry.entry_id:
            self.async_write_ha_state()
