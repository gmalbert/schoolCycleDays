"""School Cycle Days Home Assistant custom integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    BUTTON_ENTITY_KEYS,
    CONF_CALENDAR_ENTITY,
    CONF_ENTITIES,
    CONF_US_STATE,
    DEFAULT_CALENDAR_ENTITY,
    DEFAULT_US_STATE,
    DOMAIN,
    ENTITY_KEYS,
)
from .manager import SchoolCycleDaysManager

_LOGGER = logging.getLogger(__name__)

CONF_BUTTONS = "buttons"
CONF_LEGACY_CALENDAR_STORAGE_PATH = "legacy_calendar_storage_path"

ENTITY_MAP_SCHEMA = vol.Schema({vol.Optional(key): cv.entity_id for key in ENTITY_KEYS})
BUTTON_MAP_SCHEMA = vol.Schema({vol.Optional(key): cv.entity_id for key in BUTTON_ENTITY_KEYS})

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_CALENDAR_ENTITY, default=DEFAULT_CALENDAR_ENTITY): cv.entity_id,
                vol.Optional(CONF_US_STATE, default=DEFAULT_US_STATE): cv.string,
                vol.Optional(CONF_LEGACY_CALENDAR_STORAGE_PATH): cv.string,
                vol.Optional(CONF_ENTITIES, default={}): ENTITY_MAP_SCHEMA,
                vol.Optional(CONF_BUTTONS, default={}): BUTTON_MAP_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_HANDLERS = {
    "create_cycle_days": "async_create_cycle_days",
    "load_holidays": "async_load_holidays",
    "add_non_school_day": "async_add_non_school_day",
    "delete_non_school_day": "async_delete_non_school_day",
    "clear_non_school_days": "async_clear_non_school_days",
    "delete_holidays": "async_delete_holidays",
    "add_dates_from_other_calendar": "async_add_dates_from_other_calendar",
    "refresh_calendar_list": "async_refresh_calendar_list",
    "clear_calendar": "async_clear_calendar",
    "clear_and_rerun": "async_clear_and_rerun",
    "export_ics": "async_export_ics",
}


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up School Cycle Days from configuration.yaml."""
    raw_config = config.get(DOMAIN)
    if raw_config is None:
        return True

    entities = {**ENTITY_KEYS, **raw_config.get(CONF_ENTITIES, {})}
    buttons = {**BUTTON_ENTITY_KEYS, **raw_config.get(CONF_BUTTONS, {})}

    manager = SchoolCycleDaysManager(
        hass,
        calendar_entity=raw_config[CONF_CALENDAR_ENTITY],
        entities=entities,
        buttons=buttons,
        us_state=raw_config[CONF_US_STATE],
        legacy_calendar_storage_path=raw_config.get(CONF_LEGACY_CALENDAR_STORAGE_PATH),
    )
    hass.data[DOMAIN] = manager

    await manager.async_initialize()
    _register_services(hass, manager)
    _register_button_listeners(hass, manager)

    _LOGGER.info("School Cycle Days custom integration loaded")
    return True


def _register_services(hass: HomeAssistant, manager: SchoolCycleDaysManager) -> None:
    """Expose application operations as Home Assistant actions."""

    for service_name, method_name in SERVICE_HANDLERS.items():

        async def _handle_service(
            call: ServiceCall,
            *,
            method_name: str = method_name,
        ) -> None:
            del call
            method = getattr(manager, method_name)
            await method()

        hass.services.async_register(DOMAIN, service_name, _handle_service)


def _register_button_listeners(
    hass: HomeAssistant, manager: SchoolCycleDaysManager
) -> None:
    """Listen to existing input_button helpers for drop-in compatibility."""

    for action, entity_id in manager.buttons.items():
        if not entity_id:
            continue

        @callback
        def _button_changed(
            event: Event,
            *,
            action: str = action,
            entity_id: str = entity_id,
        ) -> None:
            old_state = event.data.get("old_state")
            new_state = event.data.get("new_state")
            if old_state is None or new_state is None:
                return
            if old_state.state == new_state.state:
                return
            _LOGGER.debug("Button %s triggered School Cycle Days action %s", entity_id, action)
            hass.async_create_task(manager.async_handle_button(action))

        async_track_state_change_event(hass, [entity_id], _button_changed)
