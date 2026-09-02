"""School Cycle Days Home Assistant custom integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

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

CREATE_SCHEMA = vol.Schema(
    {
        vol.Optional("start_date"): cv.string,
        vol.Optional("end_date"): cv.string,
        vol.Optional("cycle_days"): vol.All([cv.string], vol.Length(min=5, max=5)),
        vol.Optional("day_number"): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
        vol.Optional("include_holidays"): cv.boolean,
        vol.Optional("include_weekends"): cv.boolean,
    }
)
DATE_SCHEMA = vol.Schema({vol.Optional("day"): cv.string})
HOLIDAY_SCHEMA = vol.Schema({vol.Optional("start_date"): cv.string})
CALENDAR_IMPORT_SCHEMA = vol.Schema(
    {
        vol.Optional("calendar_name"): cv.string,
        vol.Optional("start_date"): cv.string,
        vol.Optional("end_date"): cv.string,
    }
)
CALENDAR_NAME_SCHEMA = vol.Schema({vol.Optional("calendar_name"): cv.string})

SERVICE_DEFINITIONS: dict[str, tuple[str, vol.Schema | None]] = {
    "create_cycle_days": ("async_create_cycle_days", CREATE_SCHEMA),
    "load_holidays": ("async_load_holidays", HOLIDAY_SCHEMA),
    "add_non_school_day": ("async_add_non_school_day", DATE_SCHEMA),
    "delete_non_school_day": ("async_delete_non_school_day", DATE_SCHEMA),
    "clear_non_school_days": ("async_clear_non_school_days", None),
    "delete_holidays": ("async_delete_holidays", None),
    "add_dates_from_other_calendar": ("async_add_dates_from_other_calendar", CALENDAR_IMPORT_SCHEMA),
    "refresh_calendar_list": ("async_refresh_calendar_list", None),
    "clear_calendar": ("async_clear_calendar", None),
    "clear_and_rerun": ("async_clear_and_rerun", CREATE_SCHEMA),
    "export_ics": ("async_export_ics", CALENDAR_NAME_SCHEMA),
}


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up School Cycle Days from configuration.yaml."""
    raw_config = config.get(DOMAIN)
    if raw_config is None:
        return True

    # Defaults retain the exact helper ids from the AppDaemon app, but the
    # manager only uses a helper when a native service call omits that value.
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

    for service_name, (method_name, schema) in SERVICE_DEFINITIONS.items():

        async def _handle_service(
            call: ServiceCall,
            *,
            method_name: str = method_name,
        ) -> None:
            method = getattr(manager, method_name)
            await method(**dict(call.data))

        hass.services.async_register(
            DOMAIN,
            service_name,
            _handle_service,
            schema=schema,
        )


def _register_button_listeners(
    hass: HomeAssistant, manager: SchoolCycleDaysManager
) -> None:
    """Listen to the original input_button helpers for drop-in compatibility."""

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
