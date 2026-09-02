"""School Cycle Days Home Assistant custom integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    BUTTON_ENTITY_KEYS,
    CONF_BUTTONS,
    CONF_CALENDAR_ENTITY,
    CONF_ENTITIES,
    CONF_LEGACY_CALENDAR_STORAGE_PATH,
    CONF_NAME,
    CONF_US_STATE,
    DEFAULT_CALENDAR_ENTITY,
    DEFAULT_NAME,
    DEFAULT_US_STATE,
    DOMAIN,
    ENTITY_KEYS,
    PLATFORMS,
)
from .manager import SchoolCycleDaysManager
from .ui_state import SchoolCycleDaysUIState

_LOGGER = logging.getLogger(__name__)

ENTITY_MAP_SCHEMA = vol.Schema({vol.Optional(key): cv.entity_id for key in ENTITY_KEYS})
BUTTON_MAP_SCHEMA = vol.Schema({vol.Optional(key): cv.entity_id for key in BUTTON_ENTITY_KEYS})

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
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
DELETE_EVENT_SCHEMA = vol.Schema({vol.Required("uid"): cv.string})
DELETE_RANGE_SCHEMA = vol.Schema(
    {
        vol.Optional("start_date"): cv.string,
        vol.Optional("end_date"): cv.string,
    }
)

SERVICE_DEFINITIONS: dict[str, tuple[str, vol.Schema | None]] = {
    "create_cycle_days": ("async_create_cycle_days", CREATE_SCHEMA),
    "load_holidays": ("async_load_holidays", HOLIDAY_SCHEMA),
    "add_non_school_day": ("async_add_non_school_day", DATE_SCHEMA),
    "delete_non_school_day": ("async_delete_non_school_day", DATE_SCHEMA),
    "clear_non_school_days": ("async_clear_non_school_days", None),
    "delete_holidays": ("async_delete_holidays", None),
    "add_dates_from_other_calendar": ("async_add_dates_from_other_calendar", CALENDAR_IMPORT_SCHEMA),
    "refresh_calendar_list": ("async_refresh_calendar_list", None),
    "delete_event": ("async_delete_event", DELETE_EVENT_SCHEMA),
    "delete_generated_events": ("async_delete_generated_events", DELETE_RANGE_SCHEMA),
    "clear_calendar": ("async_clear_calendar", None),
    "clear_and_rerun": ("async_clear_and_rerun", CREATE_SCHEMA),
    "export_ics": ("async_export_ics", CALENDAR_NAME_SCHEMA),
}


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up YAML migration support.

    YAML is no longer the primary configuration mechanism. If present, it is
    imported into a normal config entry so subsequent configuration is UI-based.
    """
    hass.data.setdefault(DOMAIN, {})
    raw_config = config.get(DOMAIN)
    if raw_config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=dict(raw_config),
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Set up School Cycle Days from a UI config entry."""
    hass.data.setdefault(DOMAIN, {})
    config = {**entry.data, **entry.options}
    entities = {**ENTITY_KEYS, **entry.data.get(CONF_ENTITIES, {})}
    buttons = {**BUTTON_ENTITY_KEYS, **entry.data.get(CONF_BUTTONS, {})}

    manager = SchoolCycleDaysManager(
        hass,
        calendar_entity=config[CONF_CALENDAR_ENTITY],
        entities=entities,
        buttons=buttons,
        us_state=config.get(CONF_US_STATE, DEFAULT_US_STATE),
        legacy_calendar_storage_path=config.get(CONF_LEGACY_CALENDAR_STORAGE_PATH),
    )
    ui_state = SchoolCycleDaysUIState(
        hass,
        entry.entry_id,
        legacy_calendar_storage_path=config.get(CONF_LEGACY_CALENDAR_STORAGE_PATH),
    )
    await ui_state.async_load()
    await manager.async_initialize()

    runtime: dict[str, Any] = {"manager": manager, "ui": ui_state, "unsubs": []}
    hass.data[DOMAIN][entry.entry_id] = runtime

    _register_services(hass, manager)
    runtime["unsubs"] = _register_button_listeners(hass, manager)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    _LOGGER.info("School Cycle Days config entry loaded")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Unload a School Cycle Days config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False
    runtime = hass.data[DOMAIN].pop(entry.entry_id, {})
    for unsub in runtime.get("unsubs", []):
        unsub()
    for service_name in SERVICE_DEFINITIONS:
        hass.services.async_remove(DOMAIN, service_name)
    return True


async def _async_entry_updated(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> None:
    """Apply options changed through Settings > Devices & services > Configure."""
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant, manager: SchoolCycleDaysManager) -> None:
    """Expose advanced/scriptable operations in addition to native buttons."""
    for service_name, (method_name, schema) in SERVICE_DEFINITIONS.items():
        if hass.services.has_service(DOMAIN, service_name):
            continue

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
) -> list[Any]:
    """Listen to original input_button helpers for drop-in compatibility."""
    unsubs: list[Any] = []
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
            if old_state is None or new_state is None or old_state.state == new_state.state:
                return
            _LOGGER.debug("Legacy button %s triggered action %s", entity_id, action)
            hass.async_create_task(manager.async_handle_button(action))

        unsubs.append(async_track_state_change_event(hass, [entity_id], _button_changed))
    return unsubs
