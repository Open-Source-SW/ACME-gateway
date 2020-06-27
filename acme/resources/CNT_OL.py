#
#	CNT_OL.py
#
#	(c) 2020 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	ResourceType: oldest (virtual resource)
#

from flask import request
from Constants import Constants as C
import Utils, CSE
from .Resource import *
from Logging import Logging


class CNT_OL(Resource):

	def __init__(self, jsn=None, pi=None, create=False):
		super().__init__(C.tsCNT_OL, jsn, pi, C.tCNT_OL, create=create, inheritACP=True, readOnly=True, rn='ol', isVirtual=True)


	# Enable check for allowed sub-resources
	def canHaveChild(self, resource : Resource) -> bool:
		return super()._canHaveChild(resource, [])


	# def asJSON(self, embedded=True, update=False, noACP=False):
	# 	pi = self['pi']
	# 	Logging.logDebug('Oldest CIN from CNT: %s' % pi)
	# 	(pr, _) = CSE.dispatcher.retrieveResource(pi)	# get parent
	# 	rs = pr.contentInstances()						# ask parent for all CIN
	# 	if len(rs) == 0:								# In case of none
	# 		return None
	# 	return rs[0].asJSON(embedded=embedded, update=update, noACP=noACP)		# result is sorted, so take, and return first


	def handleRetrieveRequest(self, request : request = None, id : str = None, originator : str = None) -> (Resource, int, str):
		""" Handle a RETRIEVE request. Return resource """
		Logging.logDebug('Retrieving oldest CIN from CNT')
		if (r := self._getOldest()) is None:
			return None, C.rcNotFound, 'no instance for <oldest>'
		return r, C.rcOK, None


	def handleCreateRequest(self, request, id, originator, ct, ty) -> (Resource, int, str):
		""" Handle a CREATE request. Fail with error code. """
		return None, C.rcOperationNotAllowed, 'operation not allowed for <oldest> resource type'


	def handleUpdateRequest(self, request, id, originator, ct) -> (Resource, int, str):
		""" Handle a UPDATE request. Fail with error code. """
		return None, C.rcOperationNotAllowed, 'operation not allowed for <oldest> resource type'


	def handleDeleteRequest(self, request, id, originator) -> (Resource, int, str):
		""" Handle a DELETE request. Delete the oldest resource. """
		Logging.logDebug('Deleting oldest CIN from CNT')
		if (r := self._getOldest()) is None:
			return None, C.rcNotFound, 'no instance for <oldest>'
		return CSE.dispatcher.deleteResource(r, originator, withDeregistration=True)


	def _getOldest(self) -> Resource:
		pi = self['pi']
		pr, _, _ = CSE.dispatcher.retrieveResource(pi)	# get parent
		rs = []
		if pr is not None:
			rs = pr.contentInstances()						# ask parent for all CIN
		return rs[0] if len(rs) > 0 else None

