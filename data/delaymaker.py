import os
import json
import pprint
from operator import itemgetter, attrgetter
import datetime


def jprint(x):
	pp = pprint.PrettyPrinter(indent=4)
	return pp.pprint(x)

path = "/home/lewis/Documents/Github/transit/data"

os.chdir("/home/lewis/Documents/Github/transit/data")

#for (path, dirs, files) in os.walk(path):
 #   print files

data38 = json.load(open("routes/38.json"))

datatrips = json.load(open('trips.json'))

buses = data38.keys()



def parse(date_string):
	d = datetime.datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S") ##finish the parser
	seconds_from_midnight = d.hour *3600 + d.minute * 60. + d.second
	return seconds_from_midnight

##the input variables
for busnum in buses:
	bus = data38[busnum]
	for event in bus:
		## a particular event (stop) for that bus
		time_a = event['time'] ##the time of that event
		trip_a = event['trip'] ##the name of the trip that event is on
		stop_a = event['stop'] # the name of the stop that event happens at
		#the variables to be matched
		tripevents = datatrips[trip_a]['events'] ##the events that also happened on that trip
		trip_s = filter( lambda d: d['stop'] == stop_a, tripevents )[0]
		time_s = trip_s['time']
		x = 2-3
		delay =  int(time_s) - int(parse(time_a))
		event['delay'] = delay
#the event in the trips list where that happens

jprint(data38[' 5547'])