#!/usr/bin/python
from numpy import *
import sqlite3
import json
import pickle
import math
from dateutil.parser import parse
from datetime import datetime
from datetime import timedelta

global completed, trips, dist, shapes, stops, allstops

#GENERAL FUNCTIONS
def parse_time(s):
    try:
        ret = parse(s)
    except ValueError:
        ret = datetime.utcfromtimestamp(s)
    return ret

def fileDump(output, name = "output.json"):
	fo = open(name, "w+")
	print "Name of the file: ", fo.name
	#print "Closed or not : ", fo.closed
	#print "Opening mode : ", fo.mode
	#print "Softspace flag : ", fo.softspace
	jsonoutput = json.dumps(output, sort_keys=True, indent=0, separators=(',', ': '))
	fo.write(jsonoutput)
	fo.close
	
#PART 1 FUNCTIONS
def projection(l, p):
	n = (l[1]-l[0])
	n = n * (1/(dot(n,n))**0.5)
	vpro = (l[0] - p) - (dot(l[0] - p, n)) * n 
	lpro = p + vpro
	return median(array([l[0], l[1], lpro]), axis=0)
	
def distance(l, p):
	pro = projection(l, p)
	n = pro - p
	return (dot(n,n)**0.5)

def postmile(PMs, allstops, shapes):
	for key in PMs.keys():
		if (PMs[key] == -1):
			#retrives the latitude and longitude of the bus stop
			stop = allstops[key[0]]
			p = array([stop["longitude"], stop["latitude"]])
		
			#retrives the collection of points in the shape
			shape = filter(lambda x: x["properties"]["shape_id"] == key[1], shapes["features"])[0]["geometry"]["coordinates"]
		
			multiline = []
			for index in range(0,len(shape) - 1):
				A = array([shape[index][0], shape[index][1]])
				B = array([shape[index + 1][0], shape[index + 1][1]])
				multiline.append({ 0 : A, 1 : B, "start" : shape[index][2], "end" : shape[index + 1][2]})
			line = sorted(multiline, key = lambda k: distance(k, p))[0]	
		
			#projects the point into the line
			pro = projection(line, p)
		
			#proportion from A to pro / A to B
			if (abs(line[1][0]-line[0][0]) < abs(line[1][1]-line[0][1])):
				#just making sure the interpolation is done with the dimession with more significant distance
				proportion = (pro[1]-line[0][1]) / (line[1][1]-line[0][1])
			else:
				proportion = (pro[0]-line[0][0]) / (line[1][0]-line[0][0])
			dist = (line["end"]-line["start"]) * proportion + line["start"]
			PMs[key] = dist
	return PMs

def calcDist():
	global dist, allstops, shapes
	dist = postmile(dist, allstops, shapes)
	
#PART 2 FUNCTIONS
def getStops():
	output=[]
	
	routes = []
	for entry in cursor.execute("""SELECT DISTINCT PUBLIC_ROUTE_NAME FROM realtime_arrivals"""):
		routes.append(entry[0])
		
	for route in routes:
		stops = []
		for entry in cursor.execute("SELECT DISTINCT STOP_ID, LONGITUDE, LATITUDE FROM realtime_arrivals WHERE PUBLIC_ROUTE_NAME = (?)", (route,)):
			stops.append({ "_id" : entry[0], "longitude" : entry[1], "latitude" : entry[2]})
		output.append({"_id" : route, "stops" : stops})
		
	for entry in cursor.execute("""SELECT DISTINCT STOP_ID, LONGITUDE, LATITUDE FROM realtime_arrivals """):
		output.append({"_id" : entry[0], "longitude" : entry[1], "latitude" : entry[2]})
	fileDump(output, "stops.json")

def getRoute(trips):
	Routes = []
	print str(datetime.now()) + ": Getting all the routes"
	for entry in cursor.execute("""SELECT DISTINCT PUBLIC_ROUTE_NAME FROM realtime_arrivals"""):
		Routes.append({"_id" : entry[0], "shapes" : []})
		
	print str(datetime.now()) + ": Looking up for the shapes on each route"
	for entry in cursor.execute("""SELECT DISTINCT PUBLIC_ROUTE_NAME, TRIP_ID FROM realtime_arrivals"""):
		for route in filter(lambda x: x["_id"] == entry[0], Routes):
			shape = 0
			for trip in filter(lambda x: x["trip"] == entry[1], trips):
				route["shapes"].append(trip["shape"])
				shape = shape + 1
			if shape == 0 :
				print "Trip " + str(entry[1]) + " does not have an associated shape"
			elif shape > 1:
				print "Trip " + str(entry[1]) + " has more than one associated shape"
	fileDump(Routes, "routes.json")

def improve( events, trip):
	#this script adds the first stop if it does not exist already 
	global trips
	firstevent = events[0]
	lastevent = events[len(events)-1]
	tripData = trips[firstevent["trip"]]["events"]

	firststop = tripData[0]
	if firstevent["dist"] != dist[(firststop["stop"], firstevent["shape"])]:
		thisday = parse_time(str(firstevent["time"]))
		
		#print "the trip does not begin at 0, adding a new event"
		schedule = filter(lambda x: x["stop"] == firstevent["stop"], tripData)[0]
		
		traveltime = schedule["time"] - firststop["time"]
		
		traveltime = timedelta(seconds = (traveltime))
		delay = firstevent["delay"]
			
		newevent = {"time": (str(thisday - traveltime)), "delay" : delay, "trip" : firstevent["trip"], "shape" : firstevent["shape"]}
		newevent["dist"] = dist[(firststop["stop"], firstevent["shape"])]
		newevent["not real"] = True
		newevent["stop"] = firststop["stop"]
		events.insert(0, newevent)

	laststop = tripData[len(tripData)-1]
	if lastevent["dist"] != dist[(laststop["stop"], firstevent["shape"])]:
		#print "adding the last stop"
		thisday = parse_time(str(lastevent["time"]))
		schedule = filter(lambda x: x["stop"] == lastevent["stop"], tripData)[0]
		traveltime = laststop["time"] - schedule["time"]
		traveltime = timedelta(seconds = (traveltime))
		delay = lastevent["delay"]
		newevent = {"time": (str(thisday + traveltime)), "delay" : delay, "trip" : lastevent["trip"], "shape" : firstevent["shape"]}
		newevent["dist"] = dist[(laststop["stop"], firstevent["shape"])]
		newevent["not real"] = True
		newevent["stop"] = laststop["stop"]
		events.append(newevent)
		
	return events

def getSchedule(events, trips):
	#events only includes the realtime arrivals, we are going to get the trips and load the scheduled events
	current_trip = events[0]["trip"]
	newevents = []
	tripevents = []
	for event in events:
		if event["trip"] == current_trip:
			tripevents.append(event)
		else:
			tripevents = improve(tripevents, current_trip)
			if len(tripevents) == 0:
				print event
				print events
			newevents.extend(tripevents)
			tripevents = []
			tripevents.append(event)
			current_trip = event["trip"]
	if len(tripevents) == 0:
		print event
		print events
	tripevents = improve(tripevents, current_trip)
	newevents.extend(tripevents)
	return newevents

def getBuses(route_id, trips):
	# using global "trips" and "dist"
	buses = {}
	events = {}
	query = True
	print str(datetime.now()) + ": looking for the buses in this route"
	for entry in cursor.execute("SELECT DISTINCT NEXTBUS_VEHICLE_ASSIGNMENT FROM realtime_arrivals WHERE PUBLIC_ROUTE_NAME = (?)", (route_id,)):
		buses[entry[0]]=[]
	
	print str(datetime.now()) + ": looking for the events in this route"
	for entry in cursor.execute("""SELECT 
		DISTINCT 
		ra.NEXTBUS_ARRIVAL_TIME, 
		ra.PUBLIC_ROUTE_NAME, 
		ra.STOP_ID, 
		ra.TRIP_ID, 
		ra.NEXTBUS_VEHICLE_ASSIGNMENT
		FROM realtime_arrivals AS ra  
		WHERE ra.PUBLIC_ROUTE_NAME = (?) 
		ORDER BY ra.STOP_ID ASC""", (route_id,)):
		if query:
			query = False
			print str(datetime.now()) + ": query completed, processing results"
		event = {"time" : str(parse_time(entry[0])), "stop" : entry[2], "trip" : entry[3] }
		try:
			event["shape"] = trips[entry[3]]["shape"]
			try:
				event["dist"] = dist[(event["stop"], event["shape"])]
			except:
				print "this event is not in the schedule " + str((event["stop"], event["shape"]))
				dist[(event["stop"], event["shape"])] = -1
				calcDist()
				event["dist"] = dist[(event["stop"], event["shape"])]
			try:
				events[(entry[1], entry[4])].append(event)
			except:
				events[(entry[1], entry[4])] = []
				events[(entry[1], entry[4])].append(event)
		except:
			pass
				
	print str(datetime.now()) + ": loading the scheduled data and sorting the events"
	schedule = []
	for key in buses.keys():
		try:
			buses[key] = events[(route_id, key)]
			buses[key] = sorted(buses[key], key=lambda k: parse_time(k["time"]))
		except:
			pass
	print str(datetime.now()) + ": all events successfully parsed"
	return buses

#-----------------------------------
#Execution Begins


conn = sqlite3.connect("MUNI.db") # or use :memory: to put it in RAM
cursor = conn.cursor()
#loading the database

#PART 1 BEGINS
print str(datetime.now()) + ": loading the list of completed routes"
track = "completed.json"
try:
	json_data = open(track)
	completed = json.load(json_data)
	json_data.close()
except:
	json_data = open(track, "w+")
	json_data.close()
	completed = []
#loading the list of completed routes


print str(datetime.now()) + ": loading all trips "
try:
	json_data=open('trips.json')
	trips = json.load(json_data)
	json_data.close()
except:
	print "no trips found"
#loading the file with all assigned trips

#the first challenge is to calculate, for each stop, the distance along each shape.
#to achieve that we generates a dictionary of all the distances that need to be calculated
dist = {}
for _id in trips.keys():
	for event in trips[_id]["events"]:
		dist[(event["stop"], trips[_id]["shape"])] = -1

#since this is a time consuming process we dont want to repeat it every time, 
#so we check if the distances have been calculated before.
try:
	dist_before = pickle.load(open("dist.p", "rb"))
	for key in dist.keys():
		try:
			dist[key] = dist_before[key]
		except:
			pass
except:
	pass
#now we procede to calculate the distance that are missing
#so we load the geometry of each shape and stop

try:
	json_data=open('shapes.json')
	shapes = json.load(json_data)
	json_data.close()

	json_data=open('allstops.json')
	allstops = json.load(json_data)
	json_data.close()
except:
	print "no data"

json_data=open('stops.json')
stops = json.load(json_data)
json_data.close()
#note to myself, im not sure if we need to load the stops.json anymore


print str(datetime.now()) + ": calculating the postmile for every single stop "
calcDist()
pickle.dump(dist, open("dist.p", "wb"))
print str(datetime.now()) + ": finished calculating the postmile for every single stop "
#now we calculate the distances and save the data for the next time
#PART 1 ENDS

#PART 2 BEGINS
#now we need to iterate over each route, so we look in the database how many routes exist
route_ids =[]
print str(datetime.now()) + ": looking up route Ids"
for entry in cursor.execute("""SELECT DISTINCT PUBLIC_ROUTE_NAME FROM realtime_arrivals ORDER BY PUBLIC_ROUTE_NAME ASC"""):
	route_ids.append(entry[0])

#for each route not completed we perform we need to lookup for the real arrivals
for route_id in filter(lambda x: not ( x in completed ), route_ids):
	print str(datetime.now()) + ": looking up for route: " + route_id
	#buses = {}
	buses = getBuses(route_id, trips)
	
	fileDump(buses, route_id + ".json")
	completed.append(route_id)
	fileDump(completed, track)
	



#stopData()
#stopANDshapeTOpostmile = {(u'3450', u'92669') : -1,(u'5817', u'92618') : -1,(u'5818', u'92617') : -1,(u'3559', u'92617') : -1,(u'4296', u'92619') : -1,(u'3545', u'92617') : -1,(u'3435', u'92663') : -1 }
#stopANDshapeTOpostmile = events()
#events()
conn.close()

print str(datetime.now()) + ": all data saved"
#PART 2 ENDS


#print "sorting the arrivals by time" + str(datetime.now())
#postmile(stopANDshapeTOpostmile, stops, shapes)
#print "end" + str(datetime.now())





