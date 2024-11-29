# School Cycle Days
Populate local Home Assistant calendar with school "specials" based on cycle days using Appdaemon

This app seeks to provide a way to keep track of school specials based on cycle days rather than days of the week. The app is based on a five cycle day system where school "specials" (art, music, library, etc.) run on the same cycle day but not the same day of the week each week. Each time there's a snow day or in-service day, etc., the cycle days stop, and then they start back up when school is back in sessions. This is very difficult to keep up with. 

This relies heavily on Home Assistant (HA) created entities, and using the HA interface to trigger different tasks. Below are the helpers that need to be created. Because HA does not (yet) have a way to programatically delete events, the delete events button deletes the physical calendar file (.ics), and then it's recreated when adding a new calendar entry.

## Installation

This app is driven off of HA entities: input_datetime, input_text, and input_button. All of the entities were created through the HA helpers. The intent was to have HA store the values so they were readable to the user and persisted after restarts. 

Each of these helper entities are explained in detail at the top of the application. You will need to create the following entities (the ones I created are listed):

1. non_school_days: input_text.non_school_days
2. added_date: input_datetime.add_non_school_day
3. cycle_day_holidays: input_text.cycle_day_holidays
4. start_date : input_datetime.cycle_start_day
5. end_date : input_datetime.cycle_end_day
6. cycle_day_1: input_text.cycle_day_1
7. cycle_day_2: input_text.cycle_day_2
8. cycle_day_3: input_text.cycle_day_3
9. cycle_day_4: input_text.cycle_day_4
10. cycle_day_5: input_text.cycle_day_5
11. day_number: input_number.cycle_day_restart_day
12. button_entity_for_adding_dates: input_button.rerun_calendar_cycle_days
13. button_entity_to_list_holidays: input_button.cycle_day_list_holidays
14. button_entity_to_add_non_school_day: input_button.add_non_school_day
15. button_entity_to_clear_non_school_days: input_button.clear_non_school_days
16. button_entity_to_delete_non_school_day: input_button.delete_non_school_day
17. button_entity_to_delete_calendar_events: input_button.delete_calendar_events
18. button_entity_to_delete_holidays: input_button.delete_holidays
19. system_message: input_text.system_message

If you change any of the names (the text above before the :), you'll need to replace them in the code. I did my best not to hard code anything, and instead use ```self.args["INPUT NAME"]```.

## Main screen
This is the main input/status screen. From here, you can add and delete non-school days, add and delete holidays, and finally, add those cycle days and their associated specials to your local HA calendar. 

![alt text](https://github.com/gmalbert/schoolCycleDays/blob/main/main_screen.JPG "Main screen")

## Cycle Days
This is where you add non-school days (in-service, snow days, etc.). Any manually added days will be added to the holidays in your selected region.
![alt text](https://github.com/gmalbert/schoolCycleDays/blob/main/cycle_days.JPG "Cycle Days")

## Holidays

## Example calendar event
![alt text](https://github.com/gmalbert/schoolCycleDays/blob/main/calendar_event.JPG "Sample calendar entry")
