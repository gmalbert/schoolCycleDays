# School Cycle Days
Populate local Home Assistant calendar with school "specials" based on cycle days using Appdaemon

This app seeks to provide a way to keep track of school specials based on cycle days rather than days of the week. Each time there's a snow day or in-service day, etc., the cycle days stop, and then they start back up when school is back in sessions. This is very difficult to keep up with. This relies heavily on Home Assistant created entities, and using the HA interface to trigger different tasks. Below are the helpers that need to be created. Because HA does not have a way to programmaticallly delete events, the delete events button deletes the physical calendar file (.ics), and then it's recreated when adding a new calendar entry.

