#!/usr/bin/env python3

import sys
import json
import yaml
import yaml
import time
import curses
import docker
import inspect
import toolbox
import datetime
import subprocess
from curses import wrapper
from termcolor import colored
from ncengine import NCEngine, nceMenuListItem

# --- Variables -----------------------------------------------------------------------------------

version = "v0.2"   # added (better) parsing yaml
allInstances = []
viewModeArray = ['Container, all Data', 'Container Port Mappings', 'Container Volumes']

# --- Def / Classes -------------------------------------------------------------------------------


def parseYaml(fileName):
	collection = []
	with open(fileName, 'r') as yamlFile:
		dcConfig = yaml.load(yamlFile, yaml.SafeLoader)
	for service in dcConfig["services"]:
		_name = service
		_services = dcConfig["services"][service]["profiles"]
		_ports = dcConfig["services"][service]["ports"] if "ports" in dcConfig["services"][service].keys() else None
		collection.append([_name, _services, _ports])
	return collection


class dcInstance:

	def __init__(self, name, running):
		self.name = name
		self.running = running
		self.attributes = False
		self.mounts = False
		self.ports = False


	def dump(self):
		print(json.dumps(self.attributes, indent=2))



class Display:

	def __init__(self, data):
		# translate data to dict, for easier access
		self.allInstances = {}
		for instance in data:
				self.allInstances[instance.name] = instance
		self.scrollData = 0
		self.viewMode = toolbox.RangeIterator(2)
		# init view
		self.view = NCEngine(self)
		self.view.borderColor = 2
		self.view.screenBorder = True
		self.view.backgroundColor = 1
		self.view.addHorizontalLine(2)
		self.view.addVerticalLine(maxServiceW)
		self.view.addVerticalLine(maxServiceW + maxContainerW)
		# Set header labels
		id = self.view.addLabel(0, 0, "Profile", 4)
		id = self.view.addLabel(maxServiceW, 0, "Container", 4)
		id = self.view.addLabel(maxServiceW + maxContainerW, 0, viewModeArray[0], 4)
		self.view.objects[id].width = 30
		self.view.keyStore["infoWindowLabel"] = id
		id = self.view.addRawTextContainer(maxServiceW + maxContainerW + 2, 3, [], 5)
		self.view.keyStore["infoWindow"] = id
		prevLabel = "none"
		# add menu
		id = self.view.addMenu(0,0, ["stopStart", "stopStart", "Check Config", "Port Usage", "To Shell"], 3, True)
		self.view.keyStore["actionMenu"] = id
		self.view.drawStack.pop()
		obj = self.view.objects[id]
		obj.setFrameColor(2)
		obj.setItemColor(6)
		# set labels for profiles
		for nr, p in enumerate(profiles):
			if p != prevLabel:
				ID = self.view.addLabel(0, nr + 2, p, 3)
				prevLabel = p
		id = self.view.addMenu(maxServiceW, 2, [d.name for d in data], 1, False)
		self.view.keyStore["mainMenu"] = id
		# color running containers
		for index in range(0, len(self.view.objects[id].content)):
			if data[index].running:
				self.view.objects[id].setItemColor(2, index)
		# update info-view
		self.displayData()
		self.loop()


	def loop(self):
		while self.view.running:
			self.view.render()
			self.checkKey(self.view.getInput())
		self.view.terminate()
		sys.exit('\n Program terminated by user\n')



	def _changeMenuItemColor(self, newColor):
		# change colour of name, to show running state
		obj = self.view.objects[self.view.keyStore["mainMenu"]]
		selected = obj.content[obj.getHighlightedNo()]
		selected.constantColor = newColor



	def startContainer(self, name):
		self.view.drawStack.pop()
		self.view.updateStatus('Starting Container, please wait...')
		self.runExternalProcess("docker compose up -d " + name)
		self.view.updateStatus('Container started, checking status...')
		time.sleep(2)
		# check if it is actually running
		instance = dcInstance(name, True)
		runningInstance = dockerClient.containers.get(name)
		status = runningInstance.attrs["State"]["Running"]
		if status:
			instance.attributes = json.dumps(runningInstance.attrs, indent=2).split('\n')
			instance.mounts  = json.dumps(runningInstance.attrs["HostConfig"]["Binds"], indent=2).split('\n')
			instance.ports  = json.dumps(runningInstance.attrs["HostConfig"]["PortBindings"], indent=2).split('\n')
			self.allInstances[name] = instance
			self.displayData()
			self._changeMenuItemColor(2)
			self.view.updateStatus('Container running ok')
		else:
			self.view.updateStatus('Container exited after start, sorry')



	def stopContainer(self, name):
		self.view.drawStack.pop()
		self.view.updateStatus('Stopping Container, please wait...')
		self.runExternalProcess("docker kill " + name)
		self.runExternalProcess("docker rm " + name)
		self._changeMenuItemColor(1)
		self.allInstances[name].running = False
		self.allInstances[name].attributes = ["(No data)"]
		self.displayData()
		self.view.updateStatus('Container was killed and removed')




	def runExternalProcess(self, cmd):
		process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
		lineOut = ''; out = ''; lineNr = 0
		while not (out == '' and process.poll() != None):
			out = process.stdout.read(1)
			if out == '\n':
				# NOTHING WRITTEN, just to blcok while container starting
				self.view.screen.refresh()
				lineOut = ''
				lineNr += 1
			else:
				lineOut += out
		return 1



	def dumpInfo(self ,name):
		self.view.terminate()
		data = parseYaml("docker-compose.yaml")
		outer = {}
		# arrange data
		for d in data:
			inner = {}
			ports = []
			if d[2]:
				for p in d[2]:
					ports.append(p.split(":")[0])
			inner[d[0]] = ports

			# sort ports
			p1 = []; p2 = []
			for p in ports:
				if p.startswith("91"):
					p1.append(p)
				else:
					p2.append(p)
			p1.sort(); p2.sort()
			ports =  p1 + p2
			if d[1][0] in outer.keys():
				outer[d[1][0]][d[0]] = ports
			else:
				outer[d[1][0]] = inner
				outer[d[1][0]][d[0]] = ports
		# output
		print()
		for k,value in outer.items():
			print(k)
			for k, v in value.items():
				print("   ", k, " " * (15 - len(k)), end="")
				for p in v:
					print(p, " ", end="")
				print()
		print()
		sys.exit()



	def startGroup(self, name):
		sys.exit('\n NotImplemented Exception (startGroup)\n')



	def stopGroup(self, name):
		sys.exit('\n NotImplemented Exception (stopGroup)\n')



	def checkConfig(self, name):
		self.view.terminate()
		data = parseYaml("docker-compose.yaml")
		for d in data:
			print(d)
		sys.exit('\n NotImplemented Exception (checkConfig)\n')



	def findPort(self, name):
		self.view.terminate()
		data = parseYaml("docker-compose.yaml")
		ports = []
		mapping = {}
		for d in data:
			if d[2]:
				for p in d[2]:
					oPort = p.split(":")[0]
					ports.append(oPort)
					mapping[oPort] = d[0]
		ourPorts = []
		for p in ports:
			if p.startswith("91"):
				ourPorts.append(p)
		ourPorts.sort()
		lastPort = int(ourPorts[-1][2:])
		# output
		print()
		print("Ports used:")
		print("------------------")
		for nr in range(1, lastPort + 1):
			portText = "91" + str(nr) if nr > 9 else "910" + str(nr)
			if portText in ourPorts:
				print(portText, "  (" + mapping[portText] + ")")
			else:
				print(portText, "<------ Unused")
		print("------------------")
		print()
		sys.exit()


	def displayData(self):
		""" Formats data snd copies it to display """
		# get highlighted object
		id = self.view.keyStore["mainMenu"]
		highLightedName = self.view.objects[id].getHighlightedValue()
		highLightedObj = self.allInstances[highLightedName]
		mode = self.viewMode.get()
		if mode == 2:
			data = highLightedObj.ports
		elif mode == 1:
			data = highLightedObj.mounts
		else:
			data = highLightedObj.attributes
		if data:
			self.view.status = 'Use keys "W" and "D" to scroll container data, "SPACE" to change data view'
		else:
			data = ["(No data)"]
			self.view.status = 'No data found, container probably not running'
		# get infoview object
		id = self.view.keyStore["infoWindow"]
		self.view.objects[id].content = data[self.scrollData:]


	def showActionMenu(self):
		# get objects
		objAM = self.view.objects[self.view.keyStore["actionMenu"]]
		objMM = self.view.objects[self.view.keyStore["mainMenu"]]
		objAM.reset()
		# decide which items to have on menu
		cursorPos = objMM.pointer.get()
		instName = objMM.content[cursorPos].text
		objAM.actions = []
		if self.allInstances[instName].running:
			objAM.content[0].text = "Stop"
			objAM.content[1].text = "Stop All"
			objAM.actions.append(self.stopContainer)
			objAM.actions.append(self.stopGroup)
		else:
			objAM.content[0].text = "Start"
			objAM.content[1].text = "Start All"
			objAM.actions.append(self.startContainer)
			objAM.actions.append(self.startGroup)
		objAM.actions.append(self.checkConfig)
		objAM.actions.append(self.findPort)
		objAM.actions.append(self.dumpInfo)
		objAM.setWidth(14)
		# re-position the menu, then display it
		itemText = objMM.content[cursorPos].text
		objAM.x = maxServiceW + len(itemText) + 2
		objAM.y = cursorPos + 3
		self.view.drawStack.append(self.view.keyStore["actionMenu"])


	def checkKey(self, key):
		""" Checks and handles keys """
		activeObject = self.view.objects[self.view.drawStack[-1]]
		menuID, keyCode = activeObject.updateKeys(key)
		menuValue = activeObject.getHighlightedValue()
		if menuID == self.view.keyStore["actionMenu"]:	# in action  menu
			if keyCode == 260:     # Key LEFT
				self.view.drawStack.pop()
			elif keyCode == 10:        # Execute (ENTER)
				idMain = self.view.keyStore["mainMenu"]
				activeObject.actions[activeObject.getHighlightedNo()](self.view.objects[idMain].getHighlightedValue())
		elif menuID == self.view.keyStore["mainMenu"]:	# in main menu
			rawData = self.allInstances[menuValue].attributes
			height, width = self.view.screen.getmaxyx()
			if keyCode == 259 or keyCode == 258:     # Key DOWN or key UP
				self.scrollData = 0
				self.displayData()
			elif keyCode == 260:     # Key LEFT
				pass
			elif keyCode == 261:     # Key RIGHT
				self.showActionMenu()
			elif keyCode == 32:      # Key Space
				self.viewMode.inc()
				self.view.objects[self.view.keyStore["infoWindowLabel"]].content[0].text = viewModeArray[ self.viewMode.get() ]
				self.displayData()
				self.view.updateStatus('Viewmode Changed to "' + viewModeArray[ self.viewMode.get() ]  + '"')
			elif keyCode == 119:      # Key W
				if self.scrollData > 1:
					self.scrollData -= 5
					if self.scrollData < 0:
						self.scrollData = 0
					self.displayData()
			elif keyCode == 115:      # Key S
				if self.scrollData < len(rawData) - height + 5:
					self.scrollData += 5
					self.displayData()
			elif keyCode == 100:     # Key D, (DEBUG)

#				objMM = self.view.objects[self.view.keyStore["mainMenu"]]
#				cursorPos = objMM.pointer.get()
#				instName = objMM.content[cursorPos].text
#				self.view.exit(instName )


				self.view.exit( self.view.drawStack  )
			if keyCode == 10:        # Execute (ENTER)
				pass
			return 1


# --- Main ----------------------------------------------------------------------------------------

# check for file
if len(sys.argv) != 2:
	sys.exit('\n Please give the name of ysml-file to parse\n')
if not  sys.argv[1].endswith(".yaml"):
	sys.exit('\n Must be .yaml-file\n')
# get text-data
raw = parseYaml(sys.argv[1])
txtData = sorted(raw, key=lambda x: (x[1], x[0]))
staticNames = [x[0] for x in txtData]
profiles = [x[1][0] for x in txtData]
maxServiceW = len(max(profiles, key=len)) + 3
maxContainerW = len(max(staticNames, key=len)) + 3
# get live data
dockerClient = docker.from_env()
runningContainers = dockerClient.containers.list()
runningNames = [x.name for x in runningContainers]


for name in staticNames:
	if not name in runningNames:
		allInstances.append(dcInstance(name, False))
	else:
		instance = dcInstance(name, True)
		runningInstance = dockerClient.containers.get(name)
		instance.attributes = json.dumps(runningInstance.attrs, indent=2).split('\n')
		instance.mounts  = json.dumps(runningInstance.attrs["HostConfig"]["Binds"], indent=2).split('\n')
		instance.ports  = json.dumps(runningInstance.attrs["HostConfig"]["PortBindings"], indent=2).split('\n')
		allInstances.append(instance)



objHandle = Display(allInstances)





# --- Todo ----------------------------------------------------------------------------------------
# - staart/stop group
# - check syntax of each entry in file / pasteurize file







