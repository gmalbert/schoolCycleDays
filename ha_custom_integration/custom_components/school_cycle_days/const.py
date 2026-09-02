"""Constants for School Cycle Days."""

from __future__ import annotations

DOMAIN = "school_cycle_days"
STORAGE_KEY = f"{DOMAIN}.data"
STORAGE_VERSION = 2

DEFAULT_NAME = "School Cycle Days"
DEFAULT_CALENDAR_ENTITY = "calendar.school"
DEFAULT_US_STATE = "NH"

CONF_NAME = "name"
CONF_CALENDAR_ENTITY = "calendar_entity"
CONF_STORAGE_PATH = "storage_path"
CONF_US_STATE = "us_state"
CONF_ENTITIES = "entities"
CONF_BUTTONS = "buttons"
CONF_LEGACY_CALENDAR_STORAGE_PATH = "legacy_calendar_storage_path"

PLATFORMS = ["button", "date", "number", "select", "switch", "text"]

# Integration-owned UI settings. These are persisted by the manager and exposed
# as native Home Assistant entities, so normal operation never requires YAML.
SETTING_START_DATE = "start_date"
SETTING_END_DATE = "end_date"
SETTING_ADDED_DATE = "added_date"
SETTING_DAY_NUMBER = "day_number"
SETTING_INCLUDE_HOLIDAYS = "include_holidays"
SETTING_INCLUDE_WEEKENDS = "include_weekends"
SETTING_SELECTED_CALENDAR = "selected_calendar"
SETTING_SELECTED_NON_SCHOOL_DAY = "selected_non_school_day"
SETTING_CYCLE_PREFIX = "cycle_day_"

DEFAULT_CYCLE_DAYS = ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5"]

# Compatibility defaults for the helper-driven AppDaemon UI. None is required
# by the native integration; they are fallback inputs/listeners only.
ENTITY_KEYS = {
    "non_school_days": "input_text.non_school_days",
    "added_date": "input_datetime.add_non_school_day",
    "cycle_day_holidays": "input_text.cycle_day_holidays",
    "start_date": "input_datetime.cycle_start_day",
    "end_date": "input_datetime.cycle_end_day",
    "cycle_day_1": "input_text.cycle_day_1",
    "cycle_day_2": "input_text.cycle_day_2",
    "cycle_day_3": "input_text.cycle_day_3",
    "cycle_day_4": "input_text.cycle_day_4",
    "cycle_day_5": "input_text.cycle_day_5",
    "day_number": "input_number.cycle_day_restart_day",
    "non_school_days_dropdown": "input_select.non_school_days",
    "calendar_list": "input_select.calendar_list",
    "calendar_list_for_selection": "input_select.calendar_list_for_selection",
    "include_holidays_in_calendar": "input_boolean.include_holidays_in_calendar",
    "include_weekends_in_calendar": "input_boolean.include_weekends_in_calendar",
    "system_message": "input_text.system_message",
    "current_calendar": "input_text.current_calendar",
}

BUTTON_ENTITY_KEYS = {
    "rerun": "input_button.rerun_calendar_cycle_days",
    "list_holidays": "input_button.cycle_day_list_holidays",
    "add_non_school_day": "input_button.add_non_school_day",
    "clear_non_school_days": "input_button.clear_non_school_days",
    "delete_non_school_day": "input_button.delete_non_school_day",
    "delete_calendar_events": "input_button.delete_calendar_events",
    "delete_holidays": "input_button.delete_holidays",
    "add_dates_from_other_calendar": "input_button.add_dates_from_other_calendar",
    "refresh_calendar_list": "input_button.refresh_calendar_list",
    "delete_and_rerun": "input_button.delete_and_rerun_calendar_cycle_days",
    "export_ics": "input_button.export_ics",
}
