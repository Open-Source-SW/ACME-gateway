#
#	Dispatcher.py
#
#	(c) 2020 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	Main request dispatcher. All external and most internal requests are routed
#	through here.
#

from Logging import Logging
from Configuration import Configuration
from Constants import Constants as C
import CSE, Utils


class Dispatcher(object):

	def __init__(self):
		self.rootPath 			= Configuration.get('http.root')
		self.enableTransit 		= Configuration.get('cse.enableTransitRequests')

		self.spid 				= Configuration.get('cse.spid')
		self.csi 				= Configuration.get('cse.csi')
		self.cseid 				= Configuration.get('cse.ri')
		self.csern				= Configuration.get('cse.rn')
		self.csiLen 			= len(self.csi)
		self.cseidLen 			= len(self.cseid)

		Logging.log('Dispatcher initialized')


	def shutdown(self):
		Logging.log('Dispatcher shut down')



	# The "xxxRequest" methods handle http requests while the "xxxResource"
	# methods handle actions on the resources. Security/permission checking
	# is done for requests, not on resource actions.

	#
	#	Retrieve resources
	#

	def retrieveRequest(self, request, _id):
		(originator, _, _, _, _) = Utils.getRequestHeaders(request)
		(id, csi, srn) = _id
		Logging.logDebug('RETRIEVE ID: %s, originator: %s' % (id if id is not None else srn, originator))

		# No ID, return immediately 
		if id is None and srn is None:
			return (None, C.rcNotFound)

		# handle transit requests
		if CSE.remote.isTransitID(id):
		 	return CSE.remote.handleTransitRetrieveRequest(request, id, originator) if self.enableTransit else (None, C.rcOperationNotAllowed)

		# handle fanoutPoint requests
		if (fanoutPointResource := Utils.fanoutPointResource(srn)) is not None and fanoutPointResource.ty == C.tGRP_FOPT:
			Logging.logDebug('Redirecting request to fanout point: %s' % fanoutPointResource.__srn__)
			return fanoutPointResource.handleRetrieveRequest(request, srn, originator)

		# just a normal retrieve request
		return self.handleRetrieveRequest(request, id, originator)


	def handleRetrieveRequest(self, request, id, originator):
		Logging.logDebug('Handle retrieve resource: %s' % id)

		try:
			attrs = self._getArguments(request)
			fu 			= attrs.get('fu')
			drt 		= attrs.get('drt')
			handling 	= attrs.get('__handling__')
			conditions 	= attrs.get('__conditons__')
			attributes 	= attrs.get('__attrs__')
			fo 			= attrs.get('fo')
			rcn 		= attrs.get('rcn')
		except Exception as e:
			return (None, C.rcInvalidArguments)


		if fu == 1 and rcn !=  C.rcnAttributes:	# discovery. rcn == Attributes is actually "normal retrieval"
			Logging.logDebug('Discover resources (fu: %s, drt: %s, handling: %s, conditions: %s, resultContent: %d, attributes: %s)' % (fu, drt, handling, conditions, rcn, str(attributes)))

			if rcn not in [C.rcnAttributesAndChildResourceReferences, C.rcnChildResourceReferences, C.rcnChildResources, C.rcnAttributesAndChildResources]:	# Only allow those two
				return (None, C.rcInvalidArguments)

			# do discovery
			(rs, _) = self.discoverResources(id, handling, conditions, attributes, fo)

			if rs is not None:
	
				# check and filter by ACP
				allowedResources = []
				for r in rs:
					if CSE.security.hasAccess(originator, r, C.permDISCOVERY):
						allowedResources.append(r)
				if rcn == C.rcnChildResourceReferences: # child resource references
					#return (self._resourcesToURIList(allowedResources, drt), C.rcOK)	
					return (self._resourceTreeReferences(allowedResources, None, drt), C.rcOK)


				# quiet strange for discovery, since children might not be direct descendants...
				elif rcn == C.rcnAttributesAndChildResourceReferences: 
					(resource, res) = self.retrieveResource(id)
					if resource is None:
						return (None, res)
					return (self._resourceTreeReferences(allowedResources, resource, drt), C.rcOK)	# the function call add attributes to the result resource

				# resource and child resources, full attributes
				elif rcn == C.rcnAttributesAndChildResources:
					(resource, res) = self.retrieveResource(id)
					if resource is None:
						return (None, res)
					self._childResourceTree(allowedResources, resource)	# the function call add attributes to the result resource. Don't use the return value directly
					return (resource, C.rcOK)

				# direct child resources, NOT the root resource
				elif rcn == C.rcnChildResources:
					resource = {  }			# empty 
					self._resourceTreeJSON(allowedResources, resource)
					return (resource, C.rcOK)
					# return (self._childResources(allowedResources), C.rcOK)

			return (None, C.rcNotFound)

		elif fu == 2 or rcn == C.rcnAttributes:	# normal retrieval
			Logging.logDebug('Get resource: %s' % id)
			(resource, res) = self.retrieveResource(id)
			if resource is None:
				return (None, res)
			if not CSE.security.hasAccess(originator, resource, C.permRETRIEVE):
				return (None, C.rcOriginatorHasNoPrivilege)
			if rcn == C.rcnAttributes:	# Just the resource & attributes
				return (resource, res)
			
			(rs, rc) = self.discoverResources(id, handling, rootResource=resource)
			if rs is  None:
				return (None, rc)

			# check and filter by ACP
			result = []
			for r in rs:
				if CSE.security.hasAccess(originator, r, C.permRETRIEVE):
					result.append(r)

			# Handle more sophisticated result content types
			if rcn == C.rcnAttributesAndChildResources:
				self._resourceTreeJSON(result, resource)	# the function call add attributes to the result resource
				return (resource, C.rcOK)

			elif rcn == C.rcnAttributesAndChildResourceReferences:
				self._resourceTreeReferences(result, resource, drt)	# the function call add attributes to the result resource
				return (resource, C.rcOK)
			elif rcn == C.rcnChildResourceReferences: # child resource references
				return (self._resourcesToURIList(result, drt), C.rcOK)

			return (None, C.rcInvalidArguments)
			# TODO check rcn. Allowed only 1, 4, 5 . 1= as now. If 4,5 check lim etc


		else:
			return (None, C.rcInvalidArguments)


	def retrieveResource(self, id : str = None):
		return self._retrieveResource(srn=id) if Utils.isStructured(id) else self._retrieveResource(ri=id)


	def _retrieveResource(self, ri : str = None, srn : str = None):
		Logging.logDebug('Retrieve resource: %s' % (ri if srn is None else srn))

		if ri is not None:
			r = CSE.storage.retrieveResource(ri=ri)		# retrieve via normal ID
		elif srn is not None:
			r = CSE.storage.retrieveResource(srn=srn) 	# retrieve via srn. Try to retrieve by srn (cases of ACPs created for AE and CSR by default)
		else:
			return (None, C.rcNotFound)

		if r is not None:
			# Check for virtual resource
			if r.ty != C.tGRP_FOPT and Utils.isVirtualResource(r):
				return r.handleRetrieveRequest()
			return (r, C.rcOK)
		Logging.logDebug('Resource not found: %s' % ri)
		return (None, C.rcNotFound)


	def discoverResources(self, id, handling, conditions=None, attributes=None, fo=None, rootResource=None):
		if rootResource is None:
			(rootResource, _) = self.retrieveResource(id)
			if rootResource is None:
				return (None, C.rcNotFound)
		return (CSE.storage.discoverResources(rootResource, handling, conditions, attributes, fo), C.rcOK)


	#
	#	Add resources
	#

	def createRequest(self, request, _id):
		(originator, ct, ty, _, _) = Utils.getRequestHeaders(request)
		(id, csi, srn) = _id
		Logging.logDebug('CREATE ID: %s, originator: %s' % (id if id is not None else srn, originator))

		# No ID, return immediately 
		if id is None and srn is None:
			return (None, C.rcNotFound)

		# handle transit requests
		if CSE.remote.isTransitID(id):
			return CSE.remote.handleTransitCreateRequest(request, id, originator, ty) if self.enableTransit else (None, C.rcOperationNotAllowed)

		# handle fanoutPoint requests
		if (fanoutPointResource := Utils.fanoutPointResource(srn)) is not None and fanoutPointResource.ty == C.tGRP_FOPT:
			Logging.logDebug('Redirecting request to fanout point: %s' % fanoutPointResource.__srn__)
			return fanoutPointResource.handleCreateRequest(request, srn, originator, ct, ty)

		# just a normal create request
		return self.handleCreateRequest(request, id, originator, ct, ty)



	def handleCreateRequest(self, request, id, originator, ct, ty):
		Logging.logDebug('Adding new resource')

		if ct == None or ty == None:
			return (None, C.rcBadRequest)

		# Get parent resource and check permissions
		(pr, res) = self.retrieveResource(id)
		if pr is None:
			Logging.log('Parent resource not found')
			return (None, C.rcNotFound)
		if CSE.security.hasAccess(originator, pr, C.permCREATE, ty=ty, isCreateRequest=True, parentResource=pr) == False:
			if ty == C.tAE:
				return (None, C.rcSecurityAssociationRequired)
			else:
				return (None, C.rcOriginatorHasNoPrivilege)

		# Check for virtual resource
		if Utils.isVirtualResource(pr):
			return pr.handleCreateRequest(request, id, originator, ct, ty)

		# Add new resource
		try:
			if (nr := Utils.resourceFromJSON(request.json, pi=pr.ri, tpe=ty)) is None:	# something wrong, perhaps wrong type
				return (None, C.rcBadRequest)
		except Exception as e:
			Logging.logWarn('Bad request (malformed content?)')
			return (None, C.rcBadRequest)

		# Check whether the parent allows the adding
		if not (res := pr.childWillBeAdded(nr, originator))[0]:
			return (None, res[1])

		# check whether the resource already exists
		if CSE.storage.hasResource(nr.ri, nr.__srn__):
			Logging.logWarn('Resource already registered')
			return (None, C.rcConflict)

		# Check resource creation
		if (res := CSE.registration.checkResourceCreation(nr, originator, pr))[1] != C.rcOK:
			return (None, res[1])
		originator = res[0]

		# Create the resource. If this fails we register everything
		if (res := self.createResource(nr, pr, originator))[0] is None:
			CSE.registration.checkResourceDeletion(nr, originator) # deregister resource. Ignore result, we take this from the creation
			return res
		return res



	def createResource(self, resource, parentResource=None, originator=None):
		Logging.logDebug('Adding resource ri: %s, type: %d' % (resource.ri, resource.ty))

		if parentResource is not None:
			Logging.logDebug('Parent ri: %s' % parentResource.ri)
			if not parentResource.canHaveChild(resource):
				if resource.ty == C.tSUB:
					Logging.logWarn('Parent resource not subscribable')
					return (None, C.rcTargetNotSubscribable)
				else:
					Logging.logWarn('Invalid child resource type')
					return (None, C.rcInvalidChildResourceType)

		# if not already set: determine and add the srn
		if resource.__srn__ is None:
			resource[resource._srn] = Utils.structuredPath(resource)

		# add the resource to storage
		if (res := resource.dbCreate(overwrite=False))[1] != C.rcCreated:
			return (None, res[1])

		# Activate the resource
		# This is done *after* writing it to the DB, because in activate the resource might create or access other
		# resources that will try to read the resource from the DB.
		if not (res := resource.activate(parentResource, originator))[0]: 	# activate the new resource
			resource.dbDelete()
			return (None, res[1])

		# Could be that we changed the resource in the activate, therefore write it again
		if (res := resource.dbUpdate())[0] is None:
			resource.dbDelete()
			return res

		if parentResource is not None:
			parentResource = parentResource.dbReload()				# Read the resource again in case it was updated in the DB
			parentResource.childAdded(resource, originator)			# notify the parent resource
		CSE.event.createResource(resource)	# send a create event

		return (resource, C.rcCreated) 	# everything is fine. resource created.



	#
	#	Update resources
	#

	def updateRequest(self, request, _id):
		(originator, ct, _, _, _) = Utils.getRequestHeaders(request)
		(id, csi, srn) = _id
		Logging.logDebug('UPDATE ID: %s, originator: %s' % (id if id is not None else srn, originator))

		# No ID, return immediately 
		if id is None and srn is None:
			return (None, C.rcNotFound)

		# handle transit requests
		if CSE.remote.isTransitID(id):
			return CSE.remote.handleTransitUpdateRequest(request, id, originator) if self.enableTransit else (None, C.rcOperationNotAllowed)

		# handle fanoutPoint requests
		if (fanoutPointResource := Utils.fanoutPointResource(srn)) is not None and fanoutPointResource.ty == C.tGRP_FOPT:
			Logging.logDebug('Redirecting request to fanout point: %s' % fanoutPointResource.__srn__)
			return fanoutPointResource.handleUpdateRequest(request, srn, originator, ct)

		# just a normal update request
		return self.handleUpdateRequest(request, id, originator, ct)


	def handleUpdateRequest(self, request, id, originator, ct):

		# get arguments
		try:
			attrs = self._getArguments(request)
			rcn   = attrs.get('rcn')
		except Exception as e:
			return (None, C.rcInvalidArguments)

		Logging.logDebug('Updating resource')
		if ct == None:
			return (None, C.rcBadRequest)

		# Get resource to update
		(r, _) = self.retrieveResource(id)	
		if r is None:
			Logging.log('Resource not found')
			return (None, C.rcNotFound)
		if r.readOnly:
			return (None, C.rcOperationNotAllowed)

		# check permissions
		try:
			jsn = request.json
		except Exception as e:
			Logging.logWarn('Bad request (malformed content?)')
			return (None, C.rcBadRequest)

		acpi = Utils.findXPath(jsn, list(jsn.keys())[0] + '/acpi')
		if acpi is not None:	# update of acpi attribute means check for self privileges!
			updateOrDelete = C.permDELETE if acpi is None else C.permUPDATE
			if CSE.security.hasAccess(originator, r, updateOrDelete, checkSelf=True) == False:
				return (None, C.rcOriginatorHasNoPrivilege)
		elif CSE.security.hasAccess(originator, r, C.permUPDATE) == False:
			return (None, C.rcOriginatorHasNoPrivilege)

		# Check for virtual resource
		if Utils.isVirtualResource(r):
			return r.handleUpdateRequest(request, id, originator, ct)

		jsonOrg = r.json.copy()
		if (result := self.updateResource(r, jsn, originator=originator))[0] is None:
			return (None, result[1])
		(r, rc) = result

		# only send the diff
		if rcn == C.rcnAttributes:
			return result
		if rcn == C.rcnModifiedAttributes:
			jsonNew = r.json.copy()
			result = { r.tpe : Utils.resourceDiff(jsonOrg, jsonNew) }
			return ( result if rc == C.rcUpdated else None, rc)
		return (None, C.rcNotImplemented)


	def updateResource(self, resource, json=None, doUpdateCheck=True, originator=None):
		Logging.logDebug('Updating resource ri: %s, type: %d' % (resource.ri, resource.ty))
		if doUpdateCheck:
			if not (res := resource.update(json, originator))[0]:
				return (None, res[1])
		else:
			Logging.logDebug('No check, skipping resource update')
		return resource.dbUpdate()



	#
	#	Remove resources
	#

	def deleteRequest(self, request, _id):
		(originator, _, _, _, _) = Utils.getRequestHeaders(request)
		(id, csi, srn) = _id
		Logging.logDebug('DELETE ID: %s, originator: %s' % (id if id is not None else srn, originator))

		# No ID, return immediately 
		if id is None and srn is None:
			return (None, C.rcNotFound)

		# handle transit requests
		if CSE.remote.isTransitID(id):
			return CSE.remote.handleTransitDeleteRequest(id, originator) if self.enableTransit else (None, C.rcOperationNotAllowed)

		# handle fanoutPoint requests
		if (fanoutPointResource := Utils.fanoutPointResource(srn)) is not None and fanoutPointResource.ty == C.tGRP_FOPT:
			Logging.logDebug('Redirecting request to fanout point: %s' % fanoutPointResource.__srn__)
			return fanoutPointResource.handleDeleteRequest(request, srn, originator)

		# just a normal delete request
		return self.handleDeleteRequest(request, id, originator)


	def handleDeleteRequest(self, request, id, originator):
		Logging.logDebug('Removing resource')

		# get resource to be removed and check permissions
		(r, _) = self.retrieveResource(id)
		if r is None:
			Logging.logDebug('Resource not found')
			return (None, C.rcNotFound)
		# if r.readOnly:
		# 	return (None, C.rcOperationNotAllowed)
		if CSE.security.hasAccess(originator, r, C.permDELETE) == False:
			return (None, C.rcOriginatorHasNoPrivilege)

		# Check for virtual resource
		if Utils.isVirtualResource(r):
			return r.handleDeleteRequest(request, id, originator)

		# remove resource
		return self.deleteResource(r, originator, withDeregistration=True)


	def deleteResource(self, resource, originator=None, withDeregistration=False):
		Logging.logDebug('Removing resource ri: %s, type: %d' % (resource.ri, resource.ty))
		if resource is None:
			Logging.log('Resource not found')

		# Check resource deletion
		if withDeregistration:
			if not (res := CSE.registration.checkResourceDeletion(resource, originator))[0]:
				return (None, C.rcBadRequest)

		resource.deactivate(originator)	# deactivate it first
		# notify the parent resource
		parentResource = resource.retrieveParentResource()
		(_, rc) = resource.dbDelete()
		CSE.event.deleteResource(resource)	# send a delete event
		if parentResource is not None:
			parentResource.childRemoved(resource, originator)
		return (resource, rc)


	#
	#	Utility methods
	#

	def subResources(self, pi, ty=None):
		return CSE.storage.subResources(pi, ty)


	def countResources(self):
		return CSE.storage.countResources()


	# All resources of a type
	def retrieveResourcesByType(self, ty):
		return CSE.storage.retrieveResource(ty=ty)


	#########################################################################

	#
	#	Internal methods
	#



	# Get the request arguments, or meaningful defaults.
	# Only a small subset is supported yet
	def _getArguments(self, request):
		result = { }

		args = request.args.copy()	# copy for greedy attributes checking 

		# basic attributes
		if (fu := args.get('fu')) is not None:
			fu = int(fu)
			del args['fu']
		else:
			fu = C.fuConditionalRetrieval
		result['fu'] = fu


		if (drt := args.get('drt')) is not None: # 1=strucured, 2=unstructured
			drt = int(drt)
			del args['drt']
		else:
			drt = C.drtStructured
		result['drt'] = drt

		if (rcn := args.get('rcn')) is not None: 
			rcn = int(rcn)
			del args['rcn']
		else:
			# TODO Not sure whether the conditional handling makes sense
			# rcn = C.rcnAttributes if fu == C.fuConditionalRetrieval else C.rcnChildResourceReferences
			if fu != C.fuDiscoveryCriteria:
				rcn = C.rcnAttributes
			else:
				# TODO It should be discovery-result-references or childResourceReferences, not specified
				rcn = C.rcnChildResourceReferences
		result['rcn'] = rcn

		# handling conditions
		handling = {}
		for c in ['lim', 'lvl', 'ofst']:	# integer parameters
			if c in args:
				handling[c] = int(args[c])
				del args[c]
		for c in ['arp']:
			if c in args:
				handling[c] = args[c]
				del args[c]
		result['__handling__'] = handling


		# conditions
		conditions = {}

		# TODO Check ty multiple times. Then -> "ty" : array?
		# also contentType 
		# Extra dictionary! as in attributes


		for c in ['crb', 'cra', 'ms', 'us', 'sts', 'stb', 'exb', 'exa', 'lbl', 'lbq', 'sza', 'szb', 'catr', 'patr']:
			if (x:= args.get(c)) is not None:
				conditions[c] = x
				del args[c]

		# get types (multi). Always create at least an empty list
		conditions['ty'] = []
		for e in args.getlist('ty'):
			conditions['ty'].extend(e.split())
		args.poplist('ty')

		# get contentTypes (multi). Always create at least an empty list
		conditions['cty'] = []
		for e in args.getlist('cty'):
			conditions['cty'].extend(e.split())
		args.poplist('cty')

		result['__conditons__'] = conditions

		# filter operation
		if (fo := args.get('fo')) is not None: # 1=AND, 2=OR
			fo = int(fo)
			del args['fo']
		else:
			fo = 1 # default
		result['fo'] = fo

		# all remaining arguments are treated as matching attributes
		result['__attrs__'] = args.copy()

		return result


	#	Create a m2m:uril structure from a list of resources
	def _resourcesToURIList(self, resources, drt):
		# cseid = '/' + Configuration.get('cse.csi') + '/'
		cseid = '/%s/' % self.csi
		lst = []
		for r in resources:
			lst.append(Utils.structuredPath(r) if drt == C.drtStructured else cseid + r.ri)
		return { 'm2m:uril' : lst }


	# def _attributesAndChildResources(self, parentResource, resources):
	# 	result = parentResource.asJSON()
	# 	ch = []
	# 	for r in resources:
	# 		ch.append(r.asJSON(embedded=False))
	# 	result[parentResource.tpe]['ch'] = ch
	# 	return result

	# Recursively walk the results and build a sub-resource tree for each resource type
	def _resourceTreeJSON(self, rs, rootResource):
		rri = rootResource['ri'] if 'ri' in rootResource else None
		while True:		# go multiple times per level through the resources until the list is empty
			result = []
			handledTy = None
			idx = 0
			while idx < len(rs):
				r = rs[idx]

				if rri is not None and r.pi != rri:	# only direct children
					idx += 1
					continue
				if r.ty in [ C.tCNT_OL, C.tCNT_LA, C.tFCNT_OL, C.tFCNT_LA ]:	# Skip latest, oldest virtual resources
					idx += 1
					continue
				if handledTy is None:
					handledTy = r.ty					# this round we check this type
				if r.ty == handledTy:					# handle only resources of the currently handled type
					result.append(r)					# append the found resource 
					rs.remove(r)						# remove resource from the original list (greedy), but don't increment the idx
					rs = self._resourceTreeJSON(rs, r)	# check recursively whether this resource has children
				else:
					idx += 1							# next resource

			# add all found resources under the same type tag to the rootResource
			if len(result) > 0:
				rootResource[result[0].tpe] = [r.asJSON(embedded=False) for r in result]
				# TODO not all child resources are lists [...] Handle just to-1 relations
			else:
				break # end of list, leave while loop
		return rs # Return the remaining list


	# Retrieve child resource referenves of a resource and add them to a new target resource as "children"
	def _resourceTreeReferences(self, resources, targetResource, drt):
		tp = 'ch'
		if targetResource is None:
			targetResource = { }
			tp = 'm2m:ch'	# top level in dict, so add qualifier.
		if len(resources) == 0:
			return targetResource
		t = []
		for r in resources:
			if r.ty in [ C.tCNT_OL, C.tCNT_LA, C.tFCNT_OL, C.tFCNT_LA ]:	# Skip latest, oldest virtual resources
				continue
			ref = { 'nm' : r['rn'], 'typ' : r['ty'], 'val' :  Utils.structuredPath(r) if drt == C.drtStructured else r.ri}
			if r.ty == C.tFCNT:
				ref['spty'] = r.cnd		# TODO Is this correct? Actually specializationID in TS-0004 6.3.5.29, but this seems to be wrong
			t.append(ref)
		targetResource[tp] = t
		return targetResource


	# Retrieve full child resources of a resource and add them to a new target resource
	def _childResourceTree(self, resource, targetResource):
		if len(resource) == 0:
			return resource
		result = {}
		self._resourceTreeJSON(resource, result)	# rootResource is filled with the result
		for k,v in result.items():			# copy child resources to result resource
			targetResource[k] = v
		return resource

