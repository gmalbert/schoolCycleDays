"""Button entities for School Cycle Days."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    SETTING_ADDED_DATE,
    SETTING_DAY_NUMBER,
    SETTING_END_DATE,
    SETTING_INCLUDE_HOLIDAYS,
    SETTING_INCLUDE_WEEKENDS,
    SETTING_SELECTED_CALENDAR,
    SETTING_SELECTED_NON_SCHOOL_DAY,
    SETTING_START_DATE,
)
from .entity import SchoolCycleDaysEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    manager = runtime["manager"]
    ui = runtime["ui"]
    async_add_entities(
        [
            SchoolCycleDaysButton(entry, ui, "add_non_school_day", "Add non-school day", lambda: _add_non_school(manager, ui)),
            SchoolCycleDaysButton(entry, ui, "remove_non_school_day", "Remove selected non-school day", lambda: _remove_non_school(manager, ui)),
            SchoolCycleDaysButton(entry, ui, "clear_non_school_days", "Clear non-school days", lambda: _clear_non_school(manager, ui)),
            SchoolCycleDaysButton(entry, ui, "load_holidays", "Load holidays", lambda: manager.async_load_holidays(start_date=ui.get(SETTING_START_DATE))),
            SchoolCycleDaysButton(entry, ui, "delete_holidays", "Delete holidays", manager.async_delete_holidays),
            SchoolCycleDaysButton(entry, ui, "generate", "Generate cycle days", lambda: _generate(manager, ui, replace=False)),
            SchoolCycleDaysButton(entry, ui, "regenerate", "Regenerate selected range", lambda: _generate(manager, ui, replace=True)),
            SchoolCycleDaysButton(entry, ui, "delete_selected_date_events", "Delete generated events on selected date", lambda: manager.async_delete_generated_events(start_date=ui.get(SETTING_ADDED_DATE), end_date=ui.get(SETTING_ADDED_DATE))),
            SchoolCycleDaysButton(entry, ui, "refresh_calendars", "Refresh calendar list", lambda: _refresh_calendars(manager, ui)),
            SchoolCycleDaysButton(entry, ui, "import_calendar", "Import no-school dates", lambda: _import_calendar(manager, ui)),
            SchoolCycleDaysButton(entry, ui, "export_calendar", "Export selected calendar", lambda: manager.async_export_ics(calendar_name=_selected_calendar(ui))),
        ]
    )


class SchoolCycleDaysButton(SchoolCycleDaysEntity, ButtonEntity):
    """A user-facing operation button."""

    def __init__(self, entry, ui_state, key: str, name: str, handler: Callable[[], Awaitable[object]]) -> None:
        super().__init__(entry, ui_state, key)
        self._attr_name = name
        self._handler = handler

    async def async_press(self) -> None:
        await self._handler()


async def _add_non_school(manager, ui) -> None:
    await manager.async_add_non_school_day(day=ui.get(SETTING_ADDED_DATE))
    await ui.async_set(SETTING_SELECTED_NON_SCHOOL_DAY, "")


async def _remove_non_school(manager, ui) -> None:
    await manager.async_delete_non_school_day(day=ui.get(SETTING_SELECTED_NON_SCHOOL_DAY))
    await ui.async_set(SETTING_SELECTED_NON_SCHOOL_DAY, "")


async def _clear_non_school(manager, ui) -> None:
    await manager.async_clear_non_school_days()
    await ui.async_set(SETTING_SELECTED_NON_SCHOOL_DAY, "")


async def _generate(manager, ui, *, replace: bool) -> None:
    kwargs = {
        "start_date": ui.get(SETTING_START_DATE),
        "end_date": ui.get(SETTING_END_DATE),
        "cycle_days": ui.cycle_days(),
        "day_number": int(ui.get(SETTING_DAY_NUMBER, 1)),
        "include_holidays": bool(ui.get(SETTING_INCLUDE_HOLIDAYS, False)),
        "include_weekends": bool(ui.get(SETTING_INCLUDE_WEEKENDS, False)),
    }
    if replace:
        await manager.async_clear_and_rerun(**kwargs)
    else:
        await manager.async_create_cycle_days(**kwargs)


async def _refresh_calendars(manager, ui) -> None:
    await ui.async_refresh_calendar_names()
    await manager.async_refresh_calendar_list()


async def _import_calendar(manager, ui) -> None:
    await manager.async_add_dates_from_other_calendar(
        calendar_name=_selected_calendar(ui),
        start_date=ui.get(SETTING_START_DATE),
        end_date=ui.get(SETTING_END_DATE),
    )
    await ui.async_set(SETTING_SELECTED_NON_SCHOOL_DAY, "")


def _selected_calendar(ui) -> str | None:
    selected = str(ui.get(SETTING_SELECTED_CALENDAR, ""))
    return None if selected in {"", "None"} else selected
