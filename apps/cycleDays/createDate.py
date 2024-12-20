# This app seeks to provide a way to keep track of school specials based on cycle days rather than days of the week.
# Each time there's a snow day or in-service day, etc., the cycle days stop, and then they start back up when school is back in sessions. This is very difficult to keep up with.
# This relies heavily on Home Assistant created entities, and using the HA interface to trigger different tasks. Below are the helpers that need to be created.
# Because HA does not have a way to programatically delete events, the delete events button deletes the physical calendar file (.ics), and then it's recreated when adding a new calendar entry.

# Holds all of the non-school days (in-service, snow days, etc.) in a long list in its attribute.
# 	non_school_days: input_text.non_school_days

# Date input to pick a day to add to the list of non-school days.
#  	added_date: input_datetime.add_non_school_day

# List of all  holidays
#	cycle_day_holidays: input_text.cycle_day_holidays

# Date to begin the cycle days on the calendar.
#  	start_date : input_datetime.cycle_start_day

# End date for calendar (usually the last day of school).
# 	end_date : input_datetime.cycle_end_day

# Specials for each cycle day
#  	cycle_day_1: input_text.cycle_day_1
#  	cycle_day_2: input_text.cycle_day_2
#  	cycle_day_3: input_text.cycle_day_3
#	cycle_day_4: input_text.cycle_day_4
#	cycle_day_5: input_text.cycle_day_5

# Cycle day to start with when rerunning the calendar.  
#  	day_number: input_number.cycle_day_restart_day

# Bearer token for HA Rest API
#	bearer_token: !secret bearer_token

# Calendar entity name
#	calendar_name: "calendar.test"
  
# Physical path to calendar. In most cases, it's /homeassistant/.storage/
#	calendar_path: !secret calendar_path

# Button entity to rerun the cycle days on the calendar
#	button_entity_for_adding_dates: input_button.rerun_calendar_cycle_days

# Button entity to run the list of holidays
#	button_entity_to_list_holidays: input_button.cycle_day_list_holidays

# Button entity to add a new non-school day
#	button_entity_to_add_non_school_day: input_button.add_non_school_day

# Button entity to clear all non school days
#	button_entity_to_clear_non_school_days: input_button.clear_non_school_days
  
# Button entity to delete an individual non-school day
#	button_entity_to_delete_non_school_day: input_button.delete_non_school_day
  
# Button entity to delete all calendar events (actually deletes the physical .ics from the .storage file
#	button_entity_to_delete_calendar_events: input_button.delete_calendar_events

# For displaying system messages (error, success, etc.)  
#	system_message: input_text.system_message

# HA Rest API URL to create events -- usually http://[HA URL]/api/services/calendar/create_event
#	create_event_url

import appdaemon.plugins.hass.hassapi as hass
from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta
import requests
import json
import holidays
import os
import time
import icalendar
from pathlib import Path
import io

class CycleDays(hass.Hass):
	
	def initialize(self): 
		
		global url
		url = self.args["create_event_url"]
		
		global headers
		headers = {"Authorization": 'Bearer ' + self.args["bearer_token"], "content-type": "application/json" }
		
		global calendar_path
		calendar_path = self.args["calendar_path"]
		calendar_name = self.args["calendar_name"]
		
		# concatenate the path with the name of the calendar, and then append the .ics extension
		global calendar_path_to_file
		calendar_path_to_file = calendar_path + "local_" + calendar_name + ".ics"
		
		# Listening for button entity pushes
		
		self.button_entity = self.get_entity(self.args["button_entity_for_adding_dates"])
		self.handle = self.button_entity.listen_state(self.listDates)
				
		self.button_entity = self.get_entity(self.args["button_entity_to_list_holidays"])
		self.handle = self.button_entity.listen_state(self.showHolidays)
		
		self.button_entity = self.get_entity(self.args["button_entity_to_add_non_school_day"])
		self.handle = self.button_entity.listen_state(self.addNonSchoolday)
		
		self.button_entity = self.get_entity(self.args["button_entity_to_clear_non_school_days"])
		self.handle = self.button_entity.listen_state(self.clearNonSchooldays)
		
		self.button_entity = self.get_entity(self.args["button_entity_to_delete_non_school_day"])
		self.handle = self.button_entity.listen_state(self.deleteNonSchoolday)
		
		self.button_entity = self.get_entity(self.args["button_entity_to_delete_calendar_events"])
		self.handle = self.button_entity.listen_state(self.deleteDates)
		
		self.button_entity = self.get_entity(self.args["button_entity_to_delete_holidays"])
		self.handle = self.button_entity.listen_state(self.deleteHolidays)
        
		self.button_entity = self.get_entity(self.args["button_entity_to_add_dates_from_other_calendar"])
		self.handle = self.button_entity.listen_state(self.addOtherCalendarDates)
		
		self.button_entity = self.get_entity(self.args["button_entity_to_refresh_calendar_list"])
		self.handle = self.button_entity.listen_state(self.refreshCalendarList)



	def deleteDates(self, start_date, end_date, old, new, kwargs):
		
# Delete the calendar file from .storage because HA doesn't have a way to delete individual events. 
# This will be updated when that changes.

		try:
			os.remove(calendar_path_to_file)
			print(f"File '{calendar_path_to_file}' deleted successfully.")
			time.sleep(1)
			self.call_service("homeassistant/reload_config_entry", entity_id=self.args["calendar_name"])
			self.set_state(self.args["system_message"], state = "<ha-alert alert-type='info'>All calendar events have been removed.</ha-alert>" )
			
		except FileNotFoundError:
			print(f"File '{calendar_path_to_file}' not found.")

	
		
	
	def refreshCalendarList(self, start_date, end_date, old, new, kwargs):
		
		dir_list = os.listdir(calendar_path)
		
		#calendar_list_filenames = []
		calendar_list_friendly_names = []
		
		for calendar in dir_list:
			if calendar.endswith(".ics"):
				if calendar != "local_todo.tasks.ics":
					#calendar_list_filenames.append(calendar)
					#print(calendar)
					
					characters_to_remove = ["local_calendar.", ".ics"]
						
					for character in characters_to_remove:
						calendar = calendar.replace(character, '')
					calendar = calendar.replace("_"," ")
					calendar_list_friendly_names.append(calendar.title())
					calendar_list_friendly_names = sorted(calendar_list_friendly_names)
					print(calendar.title())


		
		self.call_service("input_select/set_options", entity_id = "input_select.calendar_list", options = calendar_list_friendly_names)
		
		#print("Test")
    
	def addOtherCalendarDates(self, start_date, end_date, old, new, kwargs):

		calendar_friendly_name = [self.get_state("input_select.calendar_list")]
		# find the calendar in the list (the index)
		characters_to_remove = ["[", "]","'"]
						
		for character in characters_to_remove:
			calendar_friendly_name = str(calendar_friendly_name).replace(character, '')
				
		calendar_friendly_name = calendar_friendly_name.replace(" ","_")
			
		calendar_technical_name = "local_calendar." + str(calendar_friendly_name).lower() + ".ics"
		
		
		calendar_path = self.args["calendar_path"]
		calendar_path = calendar_path + calendar_technical_name
		calendar_path_to_file = Path(calendar_path)
		
		
		# get the two date inputs for the start and end date
		start_date = self.get_state(self.args["start_date"])
		end_date =  self.get_state(self.args["end_date"])
	
		# Get the formatted start and end dates
		start_date = datetime.strptime(start_date, '%Y-%m-%d')
		end_date = datetime.strptime(end_date, '%Y-%m-%d')
		
	
		with calendar_path_to_file.open() as f:
			calendar = icalendar.Calendar.from_ical(f.read())

		for event in calendar.walk('VEVENT'):
			summary = event.get('SUMMARY')
			start = event.get('DTSTART')
			end = event.get('DTEND')
			
			if str(summary).find("No School") >0:
				
				event_start_date_as_string = datetime.strftime(start.dt, '%Y-%m-%d')
				event_start_date = datetime.strptime(event_start_date_as_string, '%Y-%m-%d')
				
				event_end_date_as_string = datetime.strftime(end.dt, '%Y-%m-%d')
				event_end_date = datetime.strptime(event_end_date_as_string, '%Y-%m-%d')
				
				if event_start_date >= start_date and event_start_date <= end_date:
				
					print(f"Event Start date (cleaned) {event_start_date}")
					print(f"Event start date as string: {event_start_date_as_string }")
					print(f"Event: {summary}")
					print(f"Start: {start}")
					print(f"End: {end}")
					
					dateDifference = (event_end_date - event_start_date).days
					print(dateDifference)
					print(type(dateDifference))

					
					print("-" * 20)
					#start_date = event_start_date
					#end_date = event_end_date
					delta = timedelta(days=1)

					#### add dates to initial start date
					
					for i in range (1,dateDifference):
						print(event_start_date) + i

	
	def addNonSchoolday(self, start_date, end_date, old, new, kwargs):
		
		entity = self.args["system_message"]
		self.set_state(entity, state = "" )
		
		# Get all of the non-school days already listed from the "No school days" attribute
		
		non_school_days = [self.get_state(self.args["non_school_days"], attribute="No school days")]
	
		# Deal with the "None" or empty strings
		if non_school_days[0] == "[]" or  non_school_days[0] =="" or len(non_school_days) == 0:
			non_school_days = ""


		addedDay = self.get_state(self.args["added_date"])
		
		# interpret the day from the "added_date" entity in HA
		addedDay = datetime.strptime(addedDay, '%Y-%m-%d')
		
		# change the format to a string with m/d/yyyy
		addedDay = datetime.strftime(addedDay, '%m/%d/%Y')
		
		non_school_days = list(non_school_days)
		
		already_entered = str(non_school_days).find(addedDay)

		#entity = "input_text.non_school_days"

		# check to see if the date was already entered
		if already_entered <=0:
			
			non_school_days.append(addedDay)
			print(addedDay + ' added.')
			
			self.set_state(entity, attributes =  {"No school days" :  non_school_days}  )
			
			entity = self.args["system_message"]
			self.set_state(entity, state = addedDay + ' added as a non school day.')

			
			# character removal to make a comma delimited list - removes the strange characters added by HA
			
			characters_to_remove = ["[", "]", "!", "'"]
						
			for character in characters_to_remove:
				non_school_days = str(non_school_days).replace(character, '')

			# now change it back to a comma-delimited list
			non_school_days = non_school_days.split(", ")
			#print(non_school_days)	
			
			# delete empty or none in list to allow it to be sorted by date below
			
			if non_school_days[0] == 'None' or non_school_days[0] =='':
				del non_school_days[0]

			# sort by date
			if len(non_school_days) >0 :
				
				non_school_days.sort(key=lambda date: datetime.strptime(date, "%m/%d/%Y"))
			
			# Sort the list in-place
			
			entity = self.args["non_school_days"]
			
			# set the attribute to be all of the current non-school days
			self.set_state(entity, attributes =  {"No school days" :  non_school_days}  )
			
			# Populate the dropdown to be able to delete already entered dates
			self.call_service("input_select/set_options", entity_id = "input_select.non_school_days", options = non_school_days)

		else:
			print("This date already exists.")
			# if the date was already entered, send an error message and stop processing
			self.set_state(self.args["system_message"], state = "<ha-alert alert-type='error'>This date already exists.</ha-alert>" )

	def deleteNonSchoolday(self, start_date, end_date, old, new, kwargs):
		
		# get the current list of non-school days

		non_school_days = [self.get_state(self.args["non_school_days"], attribute="No school days")]
		
		# get the date from the drop down that was passed
		day_to_delete = [self.get_state("input_select.non_school_days")]

		# clean up the string
		characters_to_remove = ["[", "]", "!", "'"]
						
		for character in characters_to_remove:#
			non_school_days = str(non_school_days).replace(character, '')

		# make it a list again
		non_school_days = non_school_days.split(", ")
						
		for character in characters_to_remove:#
			day_to_delete = str(day_to_delete).replace(character, '')

		# find the date in the list (the index)
		date_to_delete_index = non_school_days.index(day_to_delete)

		#Delete the passed date from the list
		del non_school_days[date_to_delete_index]

		entity = self.args["system_message"]
		self.set_state(entity, state = day_to_delete + ' removed as a non school day.')
		
		# update the dropdown with the new list
		self.call_service("input_select/set_options", entity_id = "input_select.non_school_days", options = non_school_days)
		
		entity = self.args["non_school_days"]
		# set the attributes to the new list of non-school days
		self.set_state(entity, attributes =  {"No school days" :  non_school_days}  )

		
	def showHolidays(self, start_date, end_date, old, new, kwargs):
		
		entity = self.args["system_message"]
		self.set_state(entity, state = "" )
		
		# since school years go across calendar years, the holidays will be pulled for the year of the "start date" and then the following year
		start_date = self.get_state(self.args["start_date"])
		start_year = datetime.strptime(start_date, '%Y-%m-%d')
		
		next_year = start_year + relativedelta(years=1)
		next_year = datetime.strftime(next_year, '%Y')
		start_year = datetime.strftime(start_year, '%Y')

		entity = self.args["cycle_day_holidays"]
		status = self.set_state(entity, state = start_year)
		
		# Set up the dictionary using the instructions from https://pypi.org/project/holidays/
		
		us_holidays = holidays.US(state='NH', years={start_year,next_year})
		
		holiday_dates = []
		holiday_names = []
		
		# run through all of the holidays and append to attributes in HA
		for date, name in us_holidays.items():

			holiday_dates.append(datetime.strftime(date, '%m/%d/%Y'))
			holiday_names.append(name)
			print(datetime.strftime(date, '%m/%d/%Y') + ' - ' + name + ' added.')
	
		holiday_names = list(set(holiday_names))
		
		# set the attributes for the names of holidays ("Holidays") and the associated dates ("Holiday Dates")
		self.set_state(entity, attributes =  {"Holidays" :  holiday_names}  )
		self.set_state(entity, attributes =  {"Holiday Dates" :  holiday_dates}  )
		
	def deleteHolidays(self, start_date, end_date, old, new, kwargs):
				
		entity = self.args["cycle_day_holidays"]
		# set the entity attributes to blank
		self.set_state(entity, attributes =  {"Holidays" :  ""}  )
		self.set_state(entity, attributes =  {"Holiday Dates" :  ""}  )
		
		self.set_state(self.args["system_message"], state = "<ha-alert alert-type='info'>All holidays have been deleted.</ha-alert>" )
		print("All holidays have been deleted.")
		
	def clearNonSchooldays(self, start_date, end_date, old, new, kwargs):

		# to get rid of all manually entered non-school days
		entity = self.args["system_message"]
		self.set_state(entity, state = "" )
		
		# clear the non-school days list and then update its attributes in HA
		
		non_school_days = [self.get_state(self.args["non_school_days"])]
		non_school_days.clear()
		self.set_state((self.args["non_school_days"]), attributes =  {"No school days" :  ""}  )
		print("Non School Days have been deleted.")

		# Update the input_select to set a single option of "None" as HA does not allow input_select entities without any options.
		self.call_service("input_select/set_options", entity_id = "input_select.non_school_days", options = "None")
		self.set_state(self.args["system_message"], state = "<ha-alert alert-type='success'>Non School Days have been deleted.</ha-alert>" )

	def listDates (self, start_date, end_date, old, new, kwargs):


		holiday_dates = self.get_state(self.args["cycle_day_holidays"], attribute="Holiday Dates")

		entity = self.args["system_message"]
		self.set_state(entity, state = "" )
		
		# Receive the cycle day to start from
		day_number = self.get_state(self.args["day_number"])
		day_number = int(float(day_number))
		
		non_school_days = [self.get_state(self.args["non_school_days"], attribute="No school days")]
		
		# add the holidays to the manually created non-school days
		non_school_days.append(holiday_dates)
		
		# get the two date inputs for the start and end date
		start_date = self.get_state(self.args["start_date"])
		end_date =  self.get_state(self.args["end_date"])

		# get the individual values for the cycle days, and make it into a list
		cycle_days = [ self.get_state(self.args["cycle_day_1"]), self.get_state(self.args["cycle_day_2"]), self.get_state(self.args["cycle_day_3"]), self.get_state(self.args["cycle_day_4"]), self.get_state(self.args["cycle_day_5"]) ]
		
		delta = timedelta(days=1)
		
		# Get the formatted start and end dates
		start_date = datetime.strptime(start_date, '%Y-%m-%d')
		end_date = datetime.strptime(end_date, '%Y-%m-%d')
		
		# HA creates odd strings where it adds [, ]  "" '
		# this removes all of those extra characters to just make it a comma deliminted list
		characters_to_remove = ["[", "]", "!", "'"]
		
		for character in characters_to_remove:#
			non_school_days = str(non_school_days).replace(character, '')
		
		# make it back into a list
		non_school_days = non_school_days.split(", ")
		
		non_school_days = set(non_school_days)

		non_school_days = list(non_school_days)

		# As long as the initial start date is less than or equal to the provided end date, run this loop
		while start_date <= end_date:
			
			# only check against the non_school_days if the date is a weekday.
			# check if the current date in the loop is also in the non-school days.
			# remember that holidays were added to the non-school days earlier in this function.
			
			if date.weekday(start_date) < 5 and start_date.strftime("%m/%d/%Y") not in non_school_days:

				# HA requires all day events to start one day and end the next day
				next_day = start_date + timedelta(days=1)
				next_day = next_day.strftime('%Y-%m-%d')
				
				# set up the request to include the current date in the loop, the next day, the cycle day number, and the special
				data = {'entity_id': self.args["calendar_name"], 'start_date': start_date.strftime('%Y-%m-%d'), 'end_date': next_day, 'summary': 'Day ' + str(day_number), 'description': cycle_days[day_number-1]}
				
				# Run this through the HA REST API
				response = requests.post(f'{url}', headers=headers, json=data)
				print(start_date.strftime("%m/%d/%Y") + ' - Day ' + str(day_number) + ' (' + cycle_days[day_number-1] + ') created')
				#entity = "input_text.system_message"
				self.set_state(self.args["system_message"], state = start_date.strftime("%m/%d/%Y") + ' - Day ' + str(day_number) + ' (' + cycle_days[day_number-1] + ') created')
						
				day_number = day_number + 1
			elif date.weekday(start_date) < 5:
				print(start_date.strftime('%m/%d/%Y') + ' has been skipped as a non-school day.')
			else:
				print(start_date.strftime('%m/%d/%Y') + ' is a weekend day.')
			
			start_date += delta
        
			if day_number > 5:
				day_number = 1

