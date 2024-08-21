#
#	CSE.py
#
#	(c) 2020 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	Container that holds references to instances of various managing entities.
#

"""	This module implements various functions for CSE startip, running, resetting, shutdown etc.
	It also provides various global variable that hold fixed configuration values.
	In addition is holds pointers to the various runtime instance of CSE modules, packages etc.
"""

from __future__ import annotations
from typing import Dict, Any, cast, Optional

import atexit, argparse, sys
from threading import Lock
from configparser import ConfigParser

from ..helpers.BackgroundWorker import BackgroundWorkerPool
from ..etc.DateUtils import waitFor
from ..etc.Utils import runsInIPython
from ..etc.Types import CSEStatus, CSEType, ContentSerializationType, LogLevel
from ..etc.ResponseStatusCodes import ResponseException
from ..etc.ACMEUtils import isValidCSI	# cannot import at the top because of circel import
from ..services.ActionManager import ActionManager
from ..runtime.Configuration import Configuration, ConfigurationError
from ..runtime.Console import Console
from ..services.Dispatcher import Dispatcher
from ..services.RequestManager import RequestManager
from ..services.EventManager import EventManager
from ..services.GroupManager import GroupManager
from ..runtime.Importer import Importer
from ..services.LocationManager import LocationManager
from ..services.NotificationManager import NotificationManager
from ..services.RegistrationManager import RegistrationManager
from ..services.RemoteCSEManager import RemoteCSEManager
from ..runtime.ScriptManager import ScriptManager
from ..services.SecurityManager import SecurityManager
from ..services.SemanticManager import SemanticManager
from ..runtime.Statistics import Statistics
from ..runtime.Storage import Storage
from ..runtime.TextUI import TextUI
from ..services.TimeManager import TimeManager
from ..services.TimeSeriesManager import TimeSeriesManager
from ..services.Validator import Validator
from ..protocols.HttpServer import HttpServer
# from ..protocols.CoAPServer import CoAPServer
from ..protocols.MQTTClient import MQTTClient
from ..protocols.WebSocketServer import WebSocketServer
from ..services.AnnouncementManager import AnnouncementManager
from ..runtime.Logging import Logging as L




# singleton main components. These variables will hold all the various manager
# components that are used throughout the CSE implementation.

action:ActionManager = None
"""	Runtime instance of the `ActionManager`. """

announce:AnnouncementManager = None
"""	Runtime instance of the `AnnouncementManager`. """

# coapServer:CoAPServer = None
# """	Runtime instance of the `CoAPServer`. """

console:Console = None
""" Runtime instance of the `Console`. """

dispatcher:Dispatcher = None
"""	Runtime instance of the `Dispatcher`. """

event:EventManager = None
"""	Runtime instance of the `EventManager`. """

groupResource:GroupManager = None
"""	Runtime instance of the `GroupManager`. """

httpServer:HttpServer = None
"""	Runtime instance of the `HttpServer`. """

importer:Importer = None
"""	Runtime instance of the `Importer`. """

location:LocationManager = None
"""	Runtime instance of the `LocationManager`. """

mqttClient:MQTTClient = None
"""	Runtime instance of the `MQTTClient`. """

notification:NotificationManager = None
"""	Runtime instance of the `NotificationManager`. """

registration:RegistrationManager = None
"""	Runtime instance of the `RegistrationManager`. """

remote:RemoteCSEManager = None
"""	Runtime instance of the `RemoteCSEManager`. """

request:RequestManager = None
"""	Runtime instance of the `RequestManager`. """

script:ScriptManager = None
"""	Runtime instance of the `ScriptManager`. """

security:SecurityManager = None
"""	Runtime instance of the `SecurityManager`. """

semantic:SemanticManager = None
"""	Runtime instance of the `SemanticManager`. """

statistics:Statistics = None
"""	Runtime instance of the `Statistics`. """

storage:Storage = None
"""	Runtime instance of the `Storage`. """

textUI:TextUI = None
"""	Runtime instance of the `TextUI`. """

time:TimeManager = None
"""	Runtime instance of the `TimeManager`. """

timeSeries:TimeSeriesManager = None
"""	Runtime instance of the `TimeSeriesManager`. """

validator:Validator = None
"""	Runtime instance of the `Validator`. """

webSocketServer:WebSocketServer	= None
"""	Runtime instance of the `WebSocketServer`. """


# Global variables to hold various (configuation) values.

supportedReleaseVersions:list[str] = None
"""	List of the supported release versions. """

cseType:CSEType = None
""" The kind of CSE: IN, MN, or ASN. """

cseCsi:str = None
""" The CSE-ID. """

cseCsiSlash:str = None
""" The CSE-ID with an additional trailing /. """

cseCsiSlashLess:str = None
""" The CSE-ID without the leading /. """

cseSpid:str = None
""" The Service Provider ID. """

cseSPRelative:str = None
"""	The SP-Relative CSE-ID. """

cseAbsolute:str = None
""" The CSE's Absolute prefix (SP-ID/CSE-ID). """

cseAbsoluteSlash:str = None
""" The CSE's Absolute prefix with an additional trailing /. """

cseRi:str = None
""" The CSE's Resource ID. """

cseRn:str = None
""" The CSE's Resource Name. """

cseOriginator:str = None
"""	The CSE's admin originator, e.g. "CAdmin". """

slashCseOriginator:str = None
"""	The CSE's admin originator with a leading /. """

csePOA:list[str] = []
""" The CSE's point-of-access's. """

defaultSerialization:ContentSerializationType = None
""" The default / preferred content serialization type. """

releaseVersion:str = None
""" The default / preferred release version. """

isHeadless = False
""" Indicator whether the CSE is running in headless mode. """

cseStatus:CSEStatus = CSEStatus.STOPPED
""" The CSE's internal runtime status. """

cseActiveSchedule:list[str] = []
""" List of active schedules when the CSE is active and will process requests. """

_cseResetLock = Lock()
""" Internal CSE's lock when resetting. """

_cseStartupDelay:float = 2.0
""" Internal CSE's startup delay. """

##############################################################################


def startup(args:argparse.Namespace, **kwargs:Dict[str, Any]) -> bool:
	"""	Startup of the CSE. Initialization of various global variables, creating and initializing of manager instances etc.
	
		Args:
			args: Startup command line arguments.
			kwargs: Optional, additional keyword arguments which are added as attributes to the *args* object.
		Return:
			False if the CSE couldn't initialized and started. 
	"""
	global action, announce, coapServer, console, dispatcher, event, groupResource, httpServer, importer, location, mqttClient
	global notification, registration, remote, request, script, security, semantic, statistics, storage, textUI, time
	global timeSeries, validator, webSocketServer
	global supportedReleaseVersions, cseType, defaultSerialization, cseCsi, cseCsiSlash, cseCsiSlashLess, cseAbsoluteSlash
	global cseSpid, cseSPRelative, cseAbsolute, cseRi, cseRn, releaseVersion, csePOA
	global cseOriginator, slashCseOriginator
	global isHeadless, cseStatus

	# Set status
	cseStatus = CSEStatus.STARTING

	# Handle command line arguments and load the configuration
	if not args:
		args = argparse.Namespace()		# In case args is None create a new args object and populate it
		args.configfile	= None
		args.resetdb	= False
		args.loglevel	= None
		args.headless	= False
		for key, value in kwargs.items():
			args.__setattr__(key, value)

	event = EventManager()					# Initialize the event manager before anything else

	if not Configuration.init(args):
		cseStatus = CSEStatus.STOPPED
		return False

	# Initialize configurable constants
	# cseType					 = Configuration.cse_type
	supportedReleaseVersions = Configuration.cse_supportedReleaseVersions
	cseType					 = cast(CSEType, Configuration.cse_type)
	cseCsi					 = Configuration.cse_cseID
	cseCsiSlash				 = f'{cseCsi}/'
	cseCsiSlashLess			 = cseCsi[1:]
	cseSpid					 = Configuration.cse_serviceProviderID
	cseAbsoluteSlash		 = f'{cseAbsolute}/'
	cseRi					 = Configuration.cse_resourceID
	cseRn					 = Configuration.cse_resourceName
	cseOriginator			 = Configuration.cse_originator
	slashCseOriginator		= f'/{cseOriginator}'

	cseSPRelative			 = f'{cseCsi}/{cseRn}'
	cseAbsolute				 = f'//{cseSpid}{cseSPRelative}'

	defaultSerialization	 = cast(ContentSerializationType, Configuration.cse_defaultSerialization)
	releaseVersion 			 = Configuration.cse_releaseVersion
	isHeadless				 = Configuration.console_headless

	# Set the CSE's point-of-access
	csePOA = [ Configuration.http_address ]
	if Configuration.mqtt_enable:
		csePOA.append(f'mqtt://{Configuration.mqtt_address}:{Configuration.mqtt_port}')
	if Configuration.websocket_enable:
		csePOA.append(Configuration.websocket_address)

	#
	# init Logging
	#
	L.init()
	L.queueOff()				# No queuing of log messages during startup
	L.log('Starting CSE')
	L.log(f'CSE-Type: {cseType.name}')
	for l in Configuration.print().split('\n'):
		L.log(l)
	
	# set the logger for the backgroundWorkers. Add an offset to compensate for
	# this and other redirect functions to determine the correct file / linenumber
	# in the log output
	BackgroundWorkerPool.setLogger(lambda l,m: L.logWithLevel(l, m, stackOffset = 2))
	BackgroundWorkerPool.setJobBalance(	balanceTarget = Configuration.cse_operation_jobs_balanceTarget,
										balanceLatency = Configuration.cse_operation_jobs_balanceLatency,
										balanceReduceFactor = Configuration.cse_operation_jobs_balanceReduceFactor)

	try:
		textUI = TextUI()						# Start the textUI
		console = Console()						# Start the console

		storage = Storage()						# Initialize the resource storage
		statistics = Statistics()				# Initialize the statistics system
		registration = RegistrationManager()	# Initialize the registration manager
		validator = Validator()					# Initialize the resource validator
		dispatcher = Dispatcher()				# Initialize the resource dispatcher
		request = RequestManager()				# Initialize the request manager
		security = SecurityManager()			# Initialize the security manager
		httpServer = HttpServer()				# Initialize the HTTP server
		# coapServer = CoAPServer()				# Initialize the CoAP server
		mqttClient = MQTTClient()				# Initialize the MQTT client
		webSocketServer = WebSocketServer()		# Initialize the WebSocket server
		notification = NotificationManager()	# Initialize the notification manager
		groupResource = GroupManager()					# Initialize the group manager
		timeSeries = TimeSeriesManager()		# Initialize the timeSeries manager
		remote = RemoteCSEManager()				# Initialize the remote CSE manager
		announce = AnnouncementManager()		# Initialize the announcement manager
		semantic = SemanticManager()			# Initialize the semantic manager
		location = LocationManager()			# Initialize the location manager
		time = TimeManager()					# Initialize the time mamanger
		script = ScriptManager()				# Initialize the script manager
		action = ActionManager()				# Initialize the action manager

		# → Experimental late loading
		#
		# import importlib
		# mod = importlib.import_module('acme.services.ActionManager')
		# action = mod.ActionManager()	

		# mod = importlib.import_module('acme.runtime.ScriptManager')			# Initialize the action manager
		# # script = mod.ScriptManager()				# Initialize the script manager
		# thismodule = sys.modules[__name__]
		# setattr(thismodule, 'script', mod.ScriptManager())

		# Import a default set of resources, e.g. the CSE, first ACP or resource structure
		# Import extra attribute policies for specializations first
		# When this fails, we cannot continue with the CSE startup
		importer = Importer()
		if not importer.doImport():
			cseStatus = CSEStatus.STOPPED
			return False
		
		# Start the HTTP server
		if not httpServer.run(): 						# This does return (!)
			L.logErr('Terminating', showStackTrace = False)
			cseStatus = CSEStatus.STOPPED
			return False 					

		# # Start the CoAP server
		# if not coapServer.run():					# This does return
		# 	L.logErr('Terminating', showStackTrace = False)
		# 	cseStatus = CSEStatus.STOPPED
		# 	return False

		# Start the MQTT client
		if not mqttClient.run():				# This does return
			L.logErr('Terminating', showStackTrace = False)
			cseStatus = CSEStatus.STOPPED
			return False 

		# Start the WebSocket server
		if not webSocketServer.run():			# This does return
			L.logErr('Terminating', showStackTrace = False)
			cseStatus = CSEStatus.STOPPED
			return False
	
	except ResponseException as e:
		L.logErr(f'Error during startup: {e.dbg}')
		cseStatus = CSEStatus.STOPPED
		return False
	except Exception as e:
		L.logErr(f'Error during startup: {e}', exc = e)
		cseStatus = CSEStatus.STOPPED
		return False

	# Enable log queuing
	L.queueOn()	


	# Give the CSE a moment (2s) to experience fatal errors before printing the start message

	def _startUpFinished() -> None:
		"""	Internal function to print the CSE startup message after a delay
		"""
		global cseStatus
		cseStatus = CSEStatus.RUNNING
		# Send an event that the CSE startup finished
		event.cseStartup()	# type: ignore

		L.console('CSE started')
		L.log('CSE started')

	BackgroundWorkerPool.newActor(_startUpFinished, delay = _cseStartupDelay if isHeadless else _cseStartupDelay / 2.0, name = 'Delayed_startup_message' ).start()
	
	return True


def shutdown() -> None:
	"""	Gracefully shutdown the CSE programmatically. This will end the mail console loop
		to terminate.

		The actual shutdown happens in the _shutdown() method.
	"""
	global cseStatus
	
	if cseStatus in [ CSEStatus.STOPPING, CSEStatus.STOPPED ]:
		return
	
	# indicating the shutting down status. When running in another environment the
	# atexit-handler might not be called. Therefore, we need to set it here
	cseStatus = CSEStatus.STOPPING
	if console:
		console.stop()				# This will end the main run loop.
	
	if runsInIPython():
		L.console('CSE shut down', nlb = True)


@atexit.register
def _shutdown() -> None:
	"""	Shutdown the CSE, e.g. when receiving a keyboard interrupt or at the end of the programm run.
	"""
	global cseStatus

	if cseStatus != CSEStatus.RUNNING:
		return
		
	cseStatus = CSEStatus.STOPPING
	L.queueOff()
	L.isInfo and L.log('CSE shutting down')
	if event:	# send shutdown event
		event.cseShutdown() 	# type: ignore
	
	# shutdown the services
	textUI and textUI.shutdown()
	console and console.shutdown()
	time and time.shutdown()
	location and location.shutdown()
	semantic and semantic.shutdown()
	remote and remote.shutdown()
	webSocketServer and webSocketServer.shutdown()
	mqttClient and mqttClient.shutdown()
	httpServer and httpServer.shutdown()
	script and script.shutdown()
	announce and announce.shutdown()
	timeSeries and timeSeries.shutdown()
	groupResource  and groupResource.shutdown()
	notification  and notification.shutdown()
	request and request.shutdown()
	dispatcher and dispatcher.shutdown()
	security and security.shutdown()
	validator and validator.shutdown()
	registration and registration.shutdown()
	statistics and statistics.shutdown()
	event and event.shutdown()
	storage  and storage.shutdown()
	
	L.isInfo and L.log('CSE shut down')
	L.console('CSE shut down', nlb = True)

	L.finit()
	cseStatus = CSEStatus.STOPPED


def resetCSE() -> None:
	""" Reset the CSE: Clear databases and import the resources again.
	"""
	global cseStatus

	with _cseResetLock:
		cseStatus = CSEStatus.RESETTING
		L.isWarn and L.logWarn('Resetting CSE started')
		L.enableScreenLogging = Configuration.logging_enableScreenLogging	# Set screen logging to the originally configured values

		L.setLogLevel(cast(LogLevel, Configuration.logging_level))
		L.queueOff()	# Disable log queuing for restart
		
		httpServer.pause()
		mqttClient.pause()
		webSocketServer.shutdown()	# WS Server needs to be shutdown to close connections

		storage.purge()

		# The following event is executed synchronously to give every component
		# a chance to finish
		event.cseReset()	# type: ignore [attr-defined]   
		if not importer.doImport():
			textUI and textUI.shutdown()
			L.logErr('Error during import')
			sys.exit()	# what else can we do?
		remote.restart()

		webSocketServer.run()	# WS Server restart
		mqttClient.unpause()
		httpServer.unpause()

		# Enable log queuing again
		L.queueOn()

		# Send restart event
		event.cseRestarted()	# type: ignore [attr-defined]   

		cseStatus = CSEStatus.RUNNING
		L.isWarn and L.logWarn('Resetting CSE finished')


def run() -> None:
	"""	Run the CSE.
	"""
	if waitFor(_cseStartupDelay * 3, lambda: cseStatus == CSEStatus.RUNNING):
		console.run()
	else:
		raise TimeoutError(L.logErr(f'CSE did not start within {_cseStartupDelay * 3} seconds'))


def readConfiguration(parser:ConfigParser, config:Configuration) -> None:

	#	CSE

	config.cse_asyncSubscriptionNotifications = parser.getboolean('cse', 'asyncSubscriptionNotifications', fallback = True)
	config.cse_checkExpirationsInterval = parser.getint('cse', 'checkExpirationsInterval', fallback = 60)		# Seconds
	config.cse_cseID = parser.get('cse', 'cseID', fallback = '/id-in')
	config.cse_defaultSerialization = parser.get('cse', 'defaultSerialization', fallback = 'json')
	config.cse_enableRemoteCSE = parser.getboolean('cse', 'enableRemoteCSE', fallback = True)
	config.cse_enableResourceExpiration = parser.getboolean('cse', 'enableResourceExpiration', fallback = True)
	config.cse_enableSubscriptionVerificationRequests = parser.getboolean('cse', 'enableSubscriptionVerificationRequests', fallback = True)
	config.cse_flexBlockingPreference = parser.get('cse', 'flexBlockingPreference', fallback = 'blocking')
	config.cse_maxExpirationDelta = parser.getint('cse', 'maxExpirationDelta', fallback = 60*60*24*365*5)	# 5 years, in seconds
	config.cse_originator = parser.get('cse', 'originator', fallback = 'CAdmin')
	config.cse_poa = parser.getlist('cse', 'poa', fallback = ['http://127.0.0.1:8080'])	 # type: ignore [attr-defined]
	config.cse_releaseVersion = parser.get('cse', 'releaseVersion', fallback = '4')
	config.cse_requestExpirationDelta = parser.getfloat('cse', 'requestExpirationDelta', fallback = 10.0)	# 10 seconds
	config.cse_resourcesPath = parser.get('cse', 'resourcesPath', fallback = './init')
	config.cse_resourceID = parser.get('cse', 'resourceID', fallback = 'id-in')
	config.cse_resourceName = parser.get('cse', 'resourceName', fallback = 'cse-in')
	config.cse_sendToFromInResponses = parser.getboolean('cse', 'sendToFromInResponses', fallback = True)
	config.cse_sortDiscoveredResources = parser.getboolean('cse', 'sortDiscoveredResources', fallback = True)
	config.cse_supportedReleaseVersions = parser.getlist('cse', 'supportedReleaseVersions', fallback = ['2a', '3', '4', '5']) # type: ignore [attr-defined]
	config.cse_serviceProviderID = parser.get('cse', 'serviceProviderID', fallback = 'acme.example.com')
	config.cse_type = parser.get('cse', 'type', fallback = 'IN')		# IN, MN, ASN

	#	CSE Operation : Jobs

	config.cse_operation_jobs_balanceLatency = parser.getint('cse.operation.jobs', 'jobBalanceLatency', fallback = 1000)
	config.cse_operation_jobs_balanceReduceFactor = parser.getfloat('cse.operation.jobs', 'jobBalanceReduceFactor', fallback = 2.0)
	config.cse_operation_jobs_balanceTarget = parser.getfloat('cse.operation.jobs', 'jobBalanceTarget', fallback = 3.0)

	#	CSE Operation : Requests

	config.cse_operation_requests_enable = parser.getboolean('cse.operation.requests', 'enable', fallback = False)
	config.cse_operation_requests_size = parser.getint('cse.operation.requests', 'size', fallback = 1000)


def validateConfiguration(config:Configuration, initial:Optional[bool] = False) -> None:

	# override configuration with command line arguments
	if Configuration._args_initDirectory is not None:
		Configuration.cse_resourcesPath = Configuration._args_initDirectory
	if Configuration._args_remoteCSEEnabled is not None:
		Configuration.cse_enableRemoteCSE = Configuration._args_remoteCSEEnabled
	if Configuration._args_statisticsEnabled is not None:
		Configuration.cse_statistics_enable = Configuration._args_statisticsEnabled

	# CSE type
	if isinstance(config.cse_type, str):
		config.cse_type = config.cse_type.lower()
		match config.cse_type:
			case 'asn':
				config.cse_type = CSEType.ASN
			case 'mn':
				config.cse_type = CSEType.MN
			case 'in':
				config.cse_type = CSEType.IN
			case _:
				raise ConfigurationError(fr'Configuration Error: Unsupported \[cse]:type: {cseType}')

	# CSE Serialization
	if isinstance(config.cse_defaultSerialization, str):
		config.cse_defaultSerialization = ContentSerializationType.getType(config.cse_defaultSerialization)
		if config.cse_defaultSerialization == ContentSerializationType.UNKNOWN:
			raise ConfigurationError(fr'Configuration Error: Unsupported \[cse]:defaultSerialization: {config.cse_defaultSerialization}')
		
		# Operation
		if config.cse_operation_jobs_balanceTarget <= 0.0:
			raise ConfigurationError(fr'Configuration Error: [i]\[cse.operation.jobs]:balanceTarget[/i] must be > 0.0')
		if config.cse_operation_jobs_balanceLatency < 0:
			raise ConfigurationError(fr'Configuration Error: [i]\[cse.operation.jobs]:balanceLatency[/i] must be >= 0')
		if config.cse_operation_jobs_balanceReduceFactor < 1.0:
			raise ConfigurationError(fr'Configuration Error: [i]\[cse.operation.jobs]:balanceReduceFactor[/i] must be >= 1.0')

		# check the csi format and value
		if not isValidCSI(config.cse_cseID):
			raise ConfigurationError(fr'Configuration Error: Wrong format for [i]\[cse]:cseID[/i]: {config.cse_cseID}')
		if config.cse_cseID[1:] == config.cse_resourceName:
			raise ConfigurationError(fr'Configuration Error: [i]\[cse]:cseID[/i] must be different from [i]\[cse]:resourceName[/i]')

		# Check flexBlocking value
		config.cse_flexBlockingPreference = config.cse_flexBlockingPreference.lower()
		if config.cse_flexBlockingPreference not in ['blocking', 'nonblocking']:
			raise ConfigurationError(r'Configuration Error: [i]\[cse]:flexBlockingPreference[/i] must be "blocking" or "nonblocking"')

		# Check release versions
		if len(config.cse_supportedReleaseVersions) == 0:
			raise ConfigurationError(r'Configuration Error: [i]\[cse]:supportedReleaseVersions[/i] must not be empty')
		if len(config.cse_releaseVersion) == 0:
			raise ConfigurationError(r'Configuration Error: [i]\[cse]:releaseVersion[/i] must not be empty')
		if config.cse_releaseVersion not in config.cse_supportedReleaseVersions:
			raise ConfigurationError(fr'Configuration Error: [i]\[cse]:releaseVersion[/i]: {config.cse_releaseVersion} not in [i]\[cse].supportedReleaseVersions[/i]: {config.cse_supportedReleaseVersions}')

		# Check various intervals
		if config.cse_checkExpirationsInterval <= 0:
			raise ConfigurationError(r'Configuration Error: [i]\[cse]:checkExpirationsInterval[/i] must be > 0')
		if config.cse_maxExpirationDelta <= 0:
			raise ConfigurationError(r'Configuration Error: [i]\[cse]:maxExpirationDelta[/i] must be > 0')


