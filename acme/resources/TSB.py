#
#	TSB.py
#
#	(c) 2022 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	ResourceType: TimeSyncBeacon
#

from __future__ import annotations
from ..etc.Types import AttributePolicyDict, BeaconCriteria, ResourceTypes as T, Result, JSON
from ..resources.Resource import *
from ..resources import Factory as Factory
from ..services import CSE as CSE
from ..services.Logging import Logging as L


# DISCUSS child of CB, CSR, AE
# DISCUSS announceable?

# DISCUSS Only one TSB with loss_of_sync, but only one is relevant. Only one is allowed? Check in update/create



class TSB(Resource):

	# Specify the allowed child-resource types
	_allowedChildResourceTypes = [ T.SUB ]

	# Attributes and Attribute policies for this Resource Class
	# Assigned during startup in the Importer
	_attributes:AttributePolicyDict = {		
		# Common and universal attributes
		'rn': None,
		'ty': None,
		'ri': None,
		'pi': None,
		'ct': None,
		'lt': None,
		'et': None,
		'acpi': None,
		'lbl': None,
		'cstn': None,
		'daci': None,

		# 'at': None,
		# 'aa': None,
		# 'ast': None,

		# Resource attributes
		'bcnr': None,
		'bcnc': None,
		'bcni': None,
		'bcnt': None,
		'bcnu': None,
	}

	# internal attributes to store durations in s
	_bcni	= '__bcni__'
	_bcnt	= '__bcnt__'



# DISCUSS Questions to Miguel? Bob?
# beaconInterval, beaconThreshold are xs:duration? Is this correct? Not (also) second?
# timeSyncBeaconAnnc is missing from TS-0001 Table 9.6.1.1-1: Resource Types
# DISCUSS beaconRequester prerequisites are not specifically mentioned in CREATE and UPDATE procedure. -> good would be that if not present then the CSE provides a value. Add to TS-0004 procedures

# TODO docs for configuration

# TODO Implement Annc


	def __init__(self, dct:JSON = None, pi:str = None, create:bool = False) -> None:
		super().__init__(T.TSB, dct, pi, create = create)
		# Add to internal attributes to ignore in validation etc
		self.internalAttributes.append(self._bcni)	
		self.internalAttributes.append(self._bcnt)

		self.setAttribute('bcnc', BeaconCriteria.PERIODIC, overwrite = False)


# TODO activate: add to interval updater
# TODO update:

	def validate(self, originator:str = None, create:bool = False, dct:JSON = None, parentResource:Resource = None) -> Result:
		L.isDebug and L.logDebug(f'Validating timeSeriesBeacon: {self.ri}')
		if (res := super().validate(originator, create, dct, parentResource)).status == False:
			return res
		
		# Check length of beaconNotificationURI
		if len(self.bcnu) == 0:
			L.logWarn(dbg := f'beaconNotificationURI attribute shall shall contain at least one URI')
			return Result(status = False, rsc = RC.badRequest, dbg = dbg)

		# Check beaconInterval
		if self.hasAttribute('bcni') and self.bcnc != BeaconCriteria.PERIODIC:
			L.logWarn(dbg := f'beaconInterval attribute shall only be present when beaconCriteria is PERIODIC')
			return Result(status = False, rsc = RC.badRequest, dbg = dbg)
		if self.bcnc == BeaconCriteria.PERIODIC and not self.hasAttribute('bcni'):
			self.setAttribute('bcni', Configuration.get('cse.tsb.bcni'))
		if self.hasAttribute('bcni'):
			self.setAttribute(self._bcni, DateUtils.fromDuration(self.bcni))
		
		# Check beaconThreshold
		if self.hasAttribute('bcnt') and self.bcnc != BeaconCriteria.LOSS_OF_SYNCHRONIZATION:
			L.logWarn(dbg := f'beaconThreshold attribute shall only be present when beaconCriteria is LOSS_OF_SYNCHRONIZATION')
			return Result(status = False, rsc = RC.badRequest, dbg = dbg)
		if self.bcnc == BeaconCriteria.LOSS_OF_SYNCHRONIZATION and not self.hasAttribute('bcnt'):
			self.setAttribute('bcnt', Configuration.get('cse.tsb.bcnt'))
		if self.hasAttribute('bcnt'):
			self.setAttribute(self._bcnt, DateUtils.fromDuration(self.bcnt))
		
		# Check beaconRequester
		if self.hasAttribute('bcnr'):
			if self.bcnc == BeaconCriteria.PERIODIC:
				L.logWarn(dbg := f'beaconRequester attribute shall only be present when beaconCriteria is LOSS_OF_SYNCHRONIZATION')
				return Result(status = False, rsc = RC.badRequest, dbg = dbg)
		else:
			if self.bcnc == BeaconCriteria.LOSS_OF_SYNCHRONIZATION:
				L.logWarn(dbg := f'beaconRequester attribute shall be present when beaconCriteria is PERIODIC')
				return Result(status = False, rsc = RC.badRequest, dbg = dbg)

		return Result(status = True)
		


