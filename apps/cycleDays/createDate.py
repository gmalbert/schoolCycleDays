# This app seeks to provide a way to keep track of school specials based on cycle days rather than days of the week.
# Each time there's a snow day or in-service day, etc., the cycle days stop, and then they start back up when school is back in sessions. This is very difficult to keep up with.
# This relies heavily on Home Assistant created entities, and using the HA interface to trigger different tasks. Below are the helpers that need to be created.
# Because HA does not have a way to programatically delete events, the delete events button deletes the physical calendar file (.ics), and then it's recreated when adding a new calendar entry.

# Holds all of the non-school days (in-service, snow days, etc.) in a long list in its attribute.
# 	non_school_days: input_text.non_school_days

# Date input to pick a day to add to the list of non-school days.
#  	added_date: input_datetime.add_non_school_day

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


class CycleDays(hass.Hass):
	
	def initialize(self): 
		
		global url
		url = self.args["create_event_url"]
		#url = "http://192.168.1.140:8123/api/services/calendar/create_event"
		
		global headers
		headers = {"Authorization": 'Bearer ' + self.args["bearer_token"], "content-type": "application/json" }
		
		calendar_path = self.args["calendar_path"]
		calendar_uid = self.args["calendar_uid"]
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
		
		start_date = self.get_state(self.args["start_date"])
		start_year = datetime.strptime(start_date, '%Y-%m-%d')
		
		next_year = start_year + relativedelta(years=1)
		next_year = datetime.strftime(next_year, '%Y')
		start_year = datetime.strftime(start_year, '%Y')

		entity = self.args["cycle_day_holidays"]
		status = self.set_state(entity, state = start_year)
		
		us_holidays = holidays.US(state='NH', years={start_year,next_year})
		
		holiday_dates = []
		holiday_names = []
		
		for date, name in us_holidays.items():

			holiday_dates.append(datetime.strftime(date, '%m/%d/%Y'))
			holiday_names.append(name)
			print(datetime.strftime(date, '%m/%d/%Y') + ' - ' + name + ' added.')
	
		holiday_names = list(set(holiday_names))
		
		
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
		
		entity = "input_text.system_message"
		self.set_state(entity, state = "" )
		non_school_days = [self.get_state(self.args["non_school_days"])]
		non_school_days.clear()
		self.set_state((self.args["non_school_days"]), attributes =  {"No school days" :  ""}  )
		print("Non School Days have been deleted.")
		#entity = "input_text.system_message"
		self.call_service("input_select/set_options", entity_id = "input_select.non_school_days", options = "None")
		self.set_state(self.args["system_message"], state = "<ha-alert alert-type='success'>Non School Days have been deleted.</ha-alert>" )

	def listDates (self, start_date, end_date, old, new, kwargs):

		#entity = "input_text.cycle_day_holidays"
		holiday_dates = self.get_state("input_text.cycle_day_holidays", attribute="Holiday Dates")
		print(holiday_dates)
		print(type(holiday_dates))
		#return
		entity = "input_text.system_message"
		self.set_state(entity, state = "" )
		
		day_number = self.get_state(self.args["day_number"])
		day_number = int(float(day_number))
		
		non_school_days = [self.get_state(self.args["non_school_days"], attribute="No school days")]
		
		print(non_school_days)
		
		non_school_days.append(holiday_dates)
		
		start_date = self.get_state(self.args["start_date"])
		end_date =  self.get_state(self.args["end_date"])

		cycle_days = [ self.get_state(self.args["cycle_day_1"]), self.get_state(self.args["cycle_day_2"]), self.get_state(self.args["cycle_day_3"]), self.get_state(self.args["cycle_day_4"]), self.get_state(self.args["cycle_day_5"]) ]
		
		delta = timedelta(days=1)
		
		start_date = datetime.strptime(start_date, '%Y-%m-%d')
		end_date = datetime.strptime(end_date, '%Y-%m-%d')
		
		characters_to_remove = ["[", "]", "!", "'"]
		
		for character in characters_to_remove:#
			non_school_days = str(non_school_days).replace(character, '')
		
		non_school_days = non_school_days.split(", ")
		
		non_school_days = set(non_school_days)

		non_school_days = list(non_school_days)

		#print(headers)
		#return
		while start_date <= end_date:
			
			
			if date.weekday(start_date) < 5 and start_date.strftime("%m/%d/%Y") not in non_school_days:

				next_day = start_date + timedelta(days=1)
				next_day = next_day.strftime('%Y-%m-%d')
				
				data = {'entity_id': self.args["calendar_name"], 'start_date': start_date.strftime('%Y-%m-%d'), 'end_date': next_day, 'summary': 'Day ' + str(day_number), 'description': cycle_days[day_number-1]}
				
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

