#packages
import os
import json
import pprint
from operator import itemgetter, attrgetter
import datetime

###files nat
path = "/home/lewis/Dropbox/transit/data/routes"
newpath = "/home/lewis/Dropbox/transit/data/routes_new"
datatrips = json.load(open('trips.json'))


def jprint(x):
	pp = pprint.PrettyPrinter(indent=4)
	return pp.pprint(x)

def parse(date_string): ###parses into seconds-from-midnight
	d = datetime.datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S") ##finish the parser
	seconds_from_midnight = d.hour *3600 + d.minute * 60. + d.second
	return seconds_from_midnight

def delayMaker(data): ##calculates all the delays and updates them in the data
	for bus in data: ##for each bus number in the list of buses
		events = data[bus] ##events is the events for the bus
		for event in events: ## a particular event (stop) for that bus
			time_a = event['time'] ##the time of that event
			trip_a = event['trip'] ##the name of the trip that event is on
			stop_a = event['stop'] # the name of the stop where the stop happens

			#the variables to be matched
			tripevents = datatrips[trip_a]['events'] ##the events that also happened on that same trip
			trip_s = filter( lambda d: d['stop'] == stop_a, tripevents )[0] ## the trip_s
			time_s = trip_s['time']
			delay =  int(time_s) - int(parse(time_a))
			if delay > 7200:
				delay += -3600 * 24
			event['delay'] = delay ##add a delay property to the event with the calculated delay

def print_JSON(new_data, original): ###prints the new data
	name = 'new_' + original
	with open( newpath + '/' + name, 'w') as outfile:
	  json.dump(new_data, outfile)

#the event in the trips list where that happens

def main(path): ###brings it all together
	for (path, dirs, files) in os.walk(path):
	    for routefile in files:
	    	data = json.load(open(path + '/' + routefile))
	    	delayMaker(data)
	    	print_JSON(data, routefile)

main(path)