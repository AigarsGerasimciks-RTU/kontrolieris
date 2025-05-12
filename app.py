use_gpio = False # Use to enable or disable all GPIO functions if not on raspberry

import flask
import flask_login
import flask_socketio

if use_gpio:
	import lgpio as io

import threading
from time import sleep
from datetime import datetime

import json
from os import listdir, path
from inspect import getsourcefile


# function to Log changes made to setup
def logChange(logText):
	with open("editLog.txt", "a") as file:
		file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {logText}\n")


# Load previous config settings
configValues = None
with open("static/setup.json", "r") as file:
	configValues = json.loads(file.read())

if use_gpio:
	# ----- Code to control Raspberry PI's GPIO -----
	# Global pins
	a = 22
	b = 23
	c = 24
	inh0 = 14
	inh1 = 17
	inh2 = 27

	# Set up lgpio
	ioChip = io.gpiochip_open(0)

	# Enable SPI selection pins
	io.gpio_claim_output(ioChip, a)
	io.gpio_claim_output(ioChip, b)
	io.gpio_claim_output(ioChip, c)

	io.gpio_claim_output(ioChip, inh0)
	io.gpio_claim_output(ioChip, inh1)
	io.gpio_claim_output(ioChip, inh2)
	


# Hydrolysis TargetState class
class TargetState:
	def __init__(self, v0, v1, i0, i1, t):
		self.startingVoltage = v0
		self.endVoltage = v1

		self.startingAmperage = i0
		self.endAmperage = i1

		self.time = t
	
	# Return new voltage to set
	def currentVoltage(self, currentTime):
		voltageDelta = self.endVoltage - self.startingVoltage
		output = 1.00 * voltageDelta * currentTime / self.time
		output += self.startingVoltage
		return output
	
	# Return new amperage to set
	def currentAmperage(self, currentTime):
		amperageDelta = self.endAmperage - self.startingAmperage
		output = 1.00 * amperageDelta * currentTime / self.time
		output += self.startingAmperage
		return output
			
	

# Hydrolysis Channel class
class Channel:
	channelNumber = 0
	
	def __init__(self, polRevPin, potMUX, potAddr, dacMUX, dacAddr, adcMUX, adcAddr, adcCh):
		# Dynamically set channel number
		self.__class__.channelNumber += 1
		
		# Set setup-defined controls
		self.potMUX = potMUX
		self.potAddr = potAddr
		self.dacMUX = dacMUX
		self.dacAddr = dacAddr
		self.adcMUX = adcMUX
		self.adcAddr = adcAddr
		self.adcCh = adcCh
		
		self.polRevPin = polRevPin

		if use_gpio:
			io.gpio_claim_output(ioChip, polRevPin)
		
		# Set non-setup-defined controls
		self.startingTime = datetime.now()
		self.voltageIn = 0
		self.voltageOut = 0
		self.amperageOut = 0
		
		self.isActive = False
		
		self.states = []
        
	
	def _selectSPIDevice(self, mux, address):
		if use_gpio:
			# Select MUX
			io.gpio_write(ioChip, inh0, mux != 0)
			io.gpio_write(ioChip, inh1, mux != 1)
			io.gpio_write(ioChip, inh2, mux != 2)		
						
			# Select device
			if address & 1 == 0:
				io.gpio_write(ioChip, a, 0)
			else:
				io.gpio_write(ioChip, a, 1)

			if address & 2 == 0:
				io.gpio_write(ioChip, b, 0)
			else:
				io.gpio_write(ioChip, b, 1)

			if address & 4 == 0:
				io.gpio_write(ioChip, c, 0)
			else:
				io.gpio_write(ioChip, c, 1)
	
	
	def setPot(self, value):
		"""
		CS   1 o - 8 V+
		SCLK 2 - - 7 B
		MOSI 3 - - 6 W
		GND  4 - - 5 A

		For safety put a resistor between MOSI (SBC) and SDI/SDO (device).
		"""
		if use_gpio:
			self._selectSPIDevice(self.potMUX, self.potAddr)
			
			value = int(value)

			value = value if value >= 0 else value * -1
			value = 255 if value >= 255 else value
			
			pot = io.spi_open(0, 0, 250000, 0)
			io.spi_write(pot, [0, value])
			io.spi_close(pot)
		
		
	def readADC(self):
		"""
		CH0+ 1 o - 16 V+
		CH0- 2 - - 15 Vref
		CH1+ 3 - - 14 AGND
		CH1- 4 - - 13 SCLK
		CH2+ 5 - - 12 MISO
		CH2- 6 - - 11 MOSI
		CH3+ 7 - - 10 CS/SHDN
		CH3- 8 - - 9  DGND
		
		Vref can usually be connected to V+
		Both AGND and DGND can usually be connected the same GND
		"""
		if use_gpio:
			self._selectSPIDevice(self.adcMUX, self.adcAddr)
			
			sleep(0.01)
			
			adc = io.spi_open(0, 0, 25000, 0)
			(b, d) = io.spi_xfer(adc, [1, (self.adcCh<<5) + 0, 0])
			value = ((d[1] & 0x03)<<8)+d[2]
			if value == 0:
				(b, d) = io.spi_xfer(adc, [1, (self.adcCh<<5) + 16, 0])
				value = -1 * (((d[1] & 0x03)<<8)+d[2])
			io.spi_close(adc)
			return value / 1023 * configValues["referenceVoltage"]
		else: return 0
		
		
	def setPolRev(self, value):
		if use_gpio:
			value = 0 if value < 0 else value
			value = 1 if value > 1 else value
			
			io.gpio_write(ioChip, self.polRevPin, value)
		
		
	def setDAC(self, value):
		"""
		V+   1 o - 8 Vout
		CS   2 - - 7 GND
		SCLK 3 - - 6 Vref
		MOSI 4 - - 5 LDAC

		Vref can usually be connected to V+
		Here LDAC can be connected to GND
		"""
		if use_gpio:
			self._selectSPIDevice(self.dacMUX, self.dacAddr)
			
			

			value = value if value >= 0 else 0
			value = 4095 * configValues["DACMaxVoltage"] / configValues["referenceVoltage"] if value >= 4095 * configValues["DACMaxVoltage"] / configValues["referenceVoltage"] else value
			
			value = int(value)
			
			out1 = (0x03<<4) | ((value & 0xF00) >> 8)
			out2 = value & 0xFF
			
			pot = io.spi_open(0, 0, 250000, 0)
			io.spi_write(pot, [out1, out2])
			io.spi_close(pot)
	
		
	def tickGPIO(self): 
		self.voltageIn = self.readADC()
		
		if self.isActive:
			foundState = False
			timeSum = 0
			cycleTime = (datetime.now() - self.startingTime).total_seconds()
			for state in self.states:
				if timeSum + state.time > cycleTime:
					self.voltageOut = state.currentVoltage(cycleTime - timeSum)
					self.amperageOut = state.currentAmperage(cycleTime - timeSum)
					foundState = True
					break
				else:
					timeSum += state.time
			
			if not foundState:
				self.startingTime = datetime.now()
		
		else:
			self.amperageOut = 0
			self.voltageOut = 0

		# Check for negative voltage	
		self.setPolRev(self.voltageOut < 0)
		
		# Check amperage
		self.amperageOut = 0 if self.amperageOut < 0 else configValues["maxOutputAmperage"] if self.amperageOut > configValues["maxOutputAmperage"] else self.amperageOut
		
		# Check voltage
		self.voltageOut = -configValues["maxOutputVoltage"] if self.voltageOut < -configValues["maxOutputVoltage"] else configValues["maxOutputVoltage"] if self.voltageOut > configValues["maxOutputVoltage"] else self.voltageOut
		
		# Set outputs
		self.setDAC(int(4095 * configValues["DACMaxVoltage"] * self.amperageOut / configValues["maxOutputAmperage"] / configValues["referenceVoltage"])) # Change 2.3 to other number for max voltage change
		self.setPot(255.00 * self.voltageOut / configValues["maxOutputVoltage"])
	
	
	def __del__(self):
		io.gpio_free(ioChip, self.polRevPin)


# Create a list of Channel objects
channels = [Channel(5, 0, 3, 1, 5, 0, 0, 0), Channel(6, 0, 4, 1, 6, 0, 0, 1)]

def gpioLoop():
	try:
		while True:
			for c in channels:
				c.tickGPIO()
			sleep(1/configValues["GPIORate"])
	# On program close release all pins
	except KeyboardInterrupt:
		if use_gpio:
			for c in channels:
				del c
			
			io.gpio_free(ioChip, inh0)
			io.gpio_free(ioChip, inh1)
			io.gpio_free(ioChip, inh2)
			io.gpio_free(ioChip, a)
			io.gpio_free(ioChip, b)
			io.gpio_free(ioChip, c)
			
			io.gpioghip_close(ioChip)




# ----- Data logger -----
def logger():
	lineCount = 0
	filename = f"logs/{datetime.now().strftime('%Y-%m-%d %H-%M-%S')}.csv"
	file = None
	while True:
		if lineCount < configValues["maxLogEntriesPerFile"]:
			file = open(filename, "a")
		else:
			lineCount = 0
			filename = f"logs/{datetime.now().strftime('%Y-%m-%d %H-%M-%S')}.csv"
			file = open(filename, "w")
			file.write("time,channel,target voltage,real voltage,target amperage\n")
			

		for c in channels:
			if c.isActive:
				lineCount += 1
				file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]},{c.channelNumber},{round(c.voltageOut, 3)},{round(c.voltageIn, 3)},{round(c.amperageOut, 3)}\n")
		file.close
		sleep(1/configValues["SaveRate"])



# ----- App control -----
thread = None
thread_lock = threading.Lock()


app = flask.Flask(__name__)
app.secret_key = "f70341914c8ce53696015747e28dcdf795c58156eca78aa88e7a41353553ca3b" # python -c 'import secrets; print(secrets.token_hex())'

app.config["TEMPLATES_AUTO_RELOAD"] = True

login_manager = flask_login.LoginManager()
login_manager.init_app(app)

socketio = flask_socketio.SocketIO(app, cors_allowed_origins='*')

# Login "data base"
users = {'login': 'password'}

# Use defult provided user class
class User(flask_login.UserMixin):
    pass

# ----- Check if user exists -----
@login_manager.user_loader
def user_loader(username):
    if username not in users:
        return
    user = User()
    user.id = username
    return user

@login_manager.request_loader
def request_loader(request):
    username = request.form.get('username')
    if username not in users:
        return
    user = User()
    user.id = username
    return user


# ----- Login page -----
@app.route('/login', methods=['GET', 'POST'])
def login():
    if flask.request.method == 'GET':
        if flask_login.current_user.is_authenticated:
            return flask.redirect("/main")
        else:
            return flask.render_template("login.html", retry = False)

    username = flask.request.form['username']
    if username in users and flask.request.form['password'] == users[username]:
        user = User()
        user.id = username
        flask_login.login_user(user)
        return flask.redirect("/main")

    return flask.render_template("login.html", retry = True)


# ----- See live data -----
@app.route('/main')
@flask_login.login_required
def main_page():
	output = ""
	for i in range(0, len(channels)):
		output += f'<tr><th>{i+1}.</th><td><input type="text" id="v{i}" value="{channels[i].voltageIn}" readonly></td><td><input type="text" id="tv{i}" value="{channels[i].voltageOut}" readonly></td><td><input type="text" id="a{i}" value="{channels[i].amperageOut}" readonly></td></tr>'
	with open("templates/temp_main.html", "w") as file:
		file.write(output)
	return flask.render_template("main_page.html")


# ----- Add a new control state or edit an existing one -----
@app.route("/edit", methods=["GET", "POST"])
@flask_login.login_required
def addData():
	thisChannel = 0
	if flask.request.method == "POST":
		thisChannel = int(flask.request.form["selector"])-1
		logString = f"Changed settings on channel {thisChannel+1}: "
		if flask.request.form["submit"] == "Update values":
			try:
				flask.request.form["enable"]
				channels[thisChannel].isActive = True
				logString += "channel enabled, channel config: "
			except:
				channels[thisChannel].isActive = False
				logString += "channel disabled, channel config: "
			
			for i in range(0, len(channels[thisChannel].states)):
				channels[thisChannel].states[i].startingVoltage = float(flask.request.form[f"v0{i}"])
				channels[thisChannel].states[i].endVoltage = float(flask.request.form[f"v1{i}"])
				channels[thisChannel].states[i].startingAmperage = float(flask.request.form[f"i0{i}"])
				channels[thisChannel].states[i].endAmperage = float(flask.request.form[f"i1{i}"])
				channels[thisChannel].states[i].time = float(flask.request.form[f"t{i}"])
				
				logString += f'\nState {i+1}> v0 - {flask.request.form[f"v0{i}"]}; v1 - {flask.request.form[f"v1{i}"]}; i0 - {flask.request.form[f"v1{i}"]}; i1 - {flask.request.form[f"i1{i}"]}; t - {flask.request.form[f"t{i}"]}'

				
		elif flask.request.form["submit"] == "Add new state":
			logString += f"Disabled channel, added new state"
			channels[thisChannel].states.append(TargetState(0, 0, 0, 0, 0))
			channels[thisChannel].isActive = False
		else:
			buttonPressed = flask.request.form["submit"].split()
			if buttonPressed[0] == "Delete":
				logString += f"deleted state number {buttonPressed[1]}"
				channels[thisChannel].states.pop(int(buttonPressed[1]) - 1)
		logChange(logString)
	
	
	else:
		thisChannel = flask.request.args.get("ch", default = 1, type = int)-1
		
	with open("templates/temp_edit.html", "w") as file:
		if len(channels[thisChannel].states) > 0:
			file.write("<table><tr><th>Num.</th><th>V0</th><th>V1</th><th>I0</th><th>I1</th><th>T</th></tr>")
			for i in range(0, len(channels[thisChannel].states)):
				file.write(f"""<tr>
				  <td>{i+1}.</td>
				  <td><input type="number" name="v0{i}" id="v0{i}" min="-{configValues["maxOutputVoltage"]}" max="{configValues["maxOutputVoltage"]}" step="0.001" value="{channels[thisChannel].states[i].startingVoltage}" required></td>
				  <td><input type="number" name="v1{i}" id="v1{i}" min="-{configValues["maxOutputVoltage"]}" max="{configValues["maxOutputVoltage"]}" step="0.001" value="{channels[thisChannel].states[i].endVoltage}" required></td>
				  <td><input type="number" name="i0{i}" id="i0{i}" min="0" max="{configValues["maxOutputAmperage"]}" step="0.001" value="{channels[thisChannel].states[i].startingAmperage}" required></td>
				  <td><input type="number" name="i1{i}" id="i1{i}" min="0" max="{configValues["maxOutputAmperage"]}" step="0.001" value="{channels[thisChannel].states[i].endAmperage}" required></td>
				  <td><input type="number" name="t{i}" id="t{i}" min="0" step="0.1" value="{channels[thisChannel].states[i].time}" required></td>
				  <td><input type="submit" id="submit" name="submit" value="Delete {i+1}"></td>
				</tr>""")
			file.write("</table>")
		else:
			file.write("<h2>No states!</h2>")
	
	with open("templates/temp_selector_edit.html", "w") as file:
		for i in range(1, len(channels)+1):
			if i == thisChannel+1:
				file.write(f"<option value='{i}' selected>{i}</option>")
			else:
				file.write(f"<option value='{i}'>{i}</option>")
	
	return flask.render_template("edit.html", channels=channels, selectedChannel = thisChannel)


# ----- Access global setings -----
@app.route("/setup", methods=["GET", "POST"])
@flask_login.login_required
def settings():
	if flask.request.method == "POST":
		configValues["maxLogEntriesPerFile"] = int(flask.request.form["maxlogentriesperfile"])
		configValues["maxOutputVoltage"] = float(flask.request.form["maxoutputvoltage"])
		configValues["maxOutputAmperage"] = float(flask.request.form["maxoutputamperage"])
		configValues["referenceVoltage"] = float(flask.request.form["referencevoltage"])
		configValues["DACMaxVoltage"] = 2.2
		configValues["GPIORate"] = float(flask.request.form["gpiorate"])
		configValues["SaveRate"] = float(flask.request.form["saverate"])
		configValues["SendRate"] = float(flask.request.form["sendrate"])
		
		with open("static/setup.json", "w") as file:
			file.write(json.dumps(configValues))
	return flask.render_template("setup.html", configValues = configValues)


# ----- Access data log viewer -----
@app.route("/logs", methods=["GET", "POST"])
@flask_login.login_required
def get_data():
	if flask.request.method == "POST":
		try:
			startTime = datetime.strptime(flask.request.form["start"], '%Y-%m-%dT%H:%M')
		except:
			startTime = datetime.fromtimestamp(1)
		
		try:	
			endTime = datetime.strptime(flask.request.form["end"], '%Y-%m-%dT%H:%M')
		except:
			endTime = datetime.now()
		
		source = path.abspath(getsourcefile(lambda:0))[:-6]
		
		fileList = listdir(source + "logs/")
		fileList.sort()
		
		filteredFileList = []
		
		if len(fileList) > 0: 
			for i in range(0, len(fileList)):
				filedate = datetime.strptime(fileList[i], '%Y-%m-%d %H-%M-%S.csv')
				if startTime < filedate and endTime > filedate:
					filteredFileList.append(fileList[i])
				elif endTime > filedate:
					if startTime < datetime.strptime(fileList[i+1], '%Y-%m-%d %H-%M-%S.csv') and endTime > datetime.strptime(fileList[i+1], '%Y-%m-%d %H-%M-%S.csv'):
						filteredFileList.append(fileList[i])
				elif startTime < filedate:
					filteredFileList.append(fileList[i])
					break
		
		with open("OutputLogFile.csv", "w") as outFile:
			outFile.write("time,channel,target voltage,real voltage,target amperage\n")
			for f in filteredFileList:
				with open("logs/" + f, "r") as inFile:
					for line in inFile:
						if line.split(',')[0] == "time":
							continue
						
						thisTime = datetime.strptime(line.split(',')[0], '%Y-%m-%d %H:%M:%S.%f')
						
						if thisTime >= startTime and thisTime <= endTime:
							outFile.write(line)
		
		
		
		return flask.render_template("view_data.html", formattedStartTime = flask.request.form["start"], formattedEndTime = flask.request.form["end"])
		
	return flask.render_template("view_data.html", formattedStartTime = "1970-01-01T03:00", formattedEndTime = datetime.now().strftime('%Y-%m-%dT%H:%M'))


# ----- Download data log file -----
@app.route("/download-data")
@flask_login.login_required
def download_data():
	try:
		return flask.send_file(path.abspath(getsourcefile(lambda:0))[:-6] + "OutputLogFile.csv")
	except Exception as e:
		return str(e)


# ----- Access edit log viewer -----
@app.route("/editlogs")
@flask_login.login_required
def get_editlogs():
	output = ""
	try:
		with open("editLog.txt", "r") as file:
			logList = []
			for line in file:
				logList.append(line.strip())
				if len(logList) > 25:
					logList.pop(0)
			for line in logList:
				output +=f"{line}<br>\n"
	except:
		output = "No data!"
	with open("templates/temp_editlog.html", "w") as file:
		file.write(output)
	return flask.render_template("view_edit_logs.html")


# ----- Download access log -----
@app.route("/download-editlogs")
@flask_login.login_required
def download_editlogs():
	try:
		return flask.send_file(path.abspath(getsourcefile(lambda:0))[:-6] + "editLog.txt")
	except Exception as e:
		return str(e)


# ----- Logout option -----
@app.route('/logout')
@flask_login.login_required
def logout():
    flask_login.logout_user()
    return flask.redirect("/login")


# ----- Reroute to login if not logged in -----
@login_manager.unauthorized_handler
def unauthorized_handler():
    return flask.redirect("/login")



# ----- Start sending data to client when connected -----
def sendDataToPage():
	while True:
		# Have to use built-in to send data to .js file
		voltages = []
		targetVoltages = []
		amperages = []
		
		for ch in channels:
			voltages.append(ch.voltageIn)
			targetVoltages.append(ch.voltageOut)
			amperages.append(ch.amperageOut)
		
		socketio.emit("updateSensorData", {"voltage": voltages, "voltageTarget": targetVoltages, "amperage": amperages, "time": datetime.now().strftime("%H:%M:%S")})
		socketio.sleep(1/configValues["SendRate"])

@socketio.on("connect")
def connect():
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(sendDataToPage)


# ----- Start the app -----
# Create GPIO and data logger threads
gpioThread = threading.Thread(target = gpioLoop)
loggerThread = threading.Thread(target = logger)


logChange("Startup")

if not use_gpio:
	gpioThread.start()
	loggerThread.start()

# Start app
if __name__ == "__main__":
	if use_gpio:
		gpioThread.start()
		loggerThread.start()
	
	#app.run(debug=True)
	socketio.run(app)

	

