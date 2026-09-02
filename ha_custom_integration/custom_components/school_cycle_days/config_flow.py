"""Config flow for School Cycle Days."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import (
    CONF_BUTTONS,
    CONF_CALENDAR_ENTITY,
    CONF_ENTITIES,
    CONF_LEGACY_CALENDAR_STORAGE_PATH,
    CONF_US_STATE,
    DEFAULT_CALENDAR_ENTITY,
    DEFAULT_NAME,
    DEFAULT_US_STATE,
    DOMAIN,
)


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)
            ): str,
            vol.Required(
                CONF_CALENDAR_ENTITY,
                default=defaults.get(CONF_CALENDAR_ENTITY, DEFAULT_CALENDAR_ENTITY),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="calendar")
            ),
            vol.Required(
                CONF_US_STATE, default=defaults.get(CONF_US_STATE, DEFAULT_US_STATE)
            ): str,
            vol.Optional(
                CONF_LEGACY_CALENDAR_STORAGE_PATH,
                default=defaults.get(CONF_LEGACY_CALENDAR_STORAGE_PATH, ""),
            ): str,
        }
    )


class SchoolCycleDaysConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a School Cycle Days config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Create the integration from the Home Assistant UI."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            data = dict(user_input)
            if not data.get(CONF_LEGACY_CALENDAR_STORAGE_PATH):
                data.pop(CONF_LEGACY_CALENDAR_STORAGE_PATH, None)
            return self.async_create_entry(title=data[CONF_NAME], data=data)

        return self.async_show_form(step_id="user", data_schema=_schema())

    async def async_step_import(self, import_data: dict[str, Any]):
        """Import transitional YAML configuration without losing helper maps."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        data = {
            CONF_NAME: import_data.get(CONF_NAME, DEFAULT_NAME),
            CONF_CALENDAR_ENTITY: import_data[CONF_CALENDAR_ENTITY],
            CONF_US_STATE: import_data.get(CONF_US_STATE, DEFAULT_US_STATE),
        }
        if import_data.get(CONF_LEGACY_CALENDAR_STORAGE_PATH):
            data[CONF_LEGACY_CALENDAR_STORAGE_PATH] = import_data[
                CONF_LEGACY_CALENDAR_STORAGE_PATH
            ]
        if import_data.get(CONF_ENTITIES):
            data[CONF_ENTITIES] = import_data[CONF_ENTITIES]
        if import_data.get(CONF_BUTTONS):
            data[CONF_BUTTONS] = import_data[CONF_BUTTONS]
        return self.async_create_entry(title=data[CONF_NAME], data=data)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return SchoolCycleDaysOptionsFlow(config_entry)


class SchoolCycleDaysOptionsFlow(config_entries.OptionsFlow):
    """Allow integration-level settings to be changed in the UI."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            options = dict(user_input)
            if not options.get(CONF_LEGACY_CALENDAR_STORAGE_PATH):
                options.pop(CONF_LEGACY_CALENDAR_STORAGE_PATH, None)
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(step_id="init", data_schema=_schema(current))
