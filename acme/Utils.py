#
#	Utils.py
#
#	(c) 2020 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	This module contains various utilty functions that are used from various
#	modules and entities of the CSE.
#

import datetime, random, string, sys, re
from resources import ACP, AE, ANDI, ANI, BAT, CIN, CNT, CNT_LA, CNT_OL, CSEBase, CSR, DVC
from resources import DVI, EVL, FCI, FCNT, FCNT_LA, FCNT_OL, FWR, GRP, GRP_FOPT, MEM, NOD, RBO, SUB, SWR, Unknown, Resource
from Constants import Constants as C
from Configuration import Configuration
from Logging import Logging
import CSE


def uniqueRI(prefix=''):
	p = prefix.split(':')
	p = p[1] if len(p) == 2 else p[0]
	return p + uniqueID()


def uniqueID():
	return str(random.randint(1,sys.maxsize))


def isUniqueRI(ri):
	return len(CSE.storage.identifier(ri)) == 0


def uniqueRN(prefix='un'):
	p = prefix.split(':')
	p = p[1] if len(p) == 2 else p[0]
	# return "%s_%s" % (p, ''.join(random.choices(string.ascii_uppercase + string.digits + string.ascii_lowercase, k=C.maxIDLength)))
	return "%s_%s" % (p, _randomID())


# create a unique aei, M2M-SP type
def uniqueAEI(prefix='S'):
	# return prefix + ''.join(random.choices(string.ascii_uppercase + string.digits + string.ascii_lowercase, k=C.maxIDLength))
	return prefix + _randomID()


def _randomID():
	""" Generate an ID. Prevent certain patterns in the ID. """
	while True:
		result = ''.join(random.choices(string.ascii_uppercase + string.digits + string.ascii_lowercase, k=C.maxIDLength))
		if 'fopt' not in result:	# prevent 'fopt' in ID
			return result


def fullRI(ri):
	return Configuration.get('cse.csi') + '/' + ri


def isSPRelative(uri : str):
	""" Check whether a URI is SP-Relative. """
	return uri is not None and len(uri) >= 2 and uri[0] == "/" and uri [1] != "/"


def isAbsolute(uri : str):
	""" Check whether a URI is Absolute. """
	return uri is not None and uri.startswith('//')

def isCSERelative(uri : str):
	""" Check whether a URI is CSE-Relative. """
	return uri is not None and uri[0] != '/'


def isStructured(uri : str):
	if isCSERelative(uri):
		if "/" in uri:
			return True
	elif isSPRelative(uri):
		if uri.count("/") > 2:
			return True
	elif isAbsolute(uri):
		if uri.count("/") > 4:
			return True
	return False



def isVirtualResource(resource):
	result = resource[resource._isVirtual]
	return result if result is not None else False
	# ireturn (ty := r.ty) and ty in C.tVirtualResources


# Check for valid ID
def isValidID(id):
	#return len(id) > 0 and '/' not in id 	# pi might be ""
	return '/' not in id


def getResourceDate(delta=0):
	return toISO8601Date(datetime.datetime.utcnow() + datetime.timedelta(seconds=delta))


def toISO8601Date(ts):
	if isinstance(ts, float):
		ts = datetime.datetime.utcfromtimestamp(ts)
	return ts.strftime('%Y%m%dT%H%M%S,%f')


def structuredPath(resource : Resource):
	""" Determine the structured path of a resource. """
	rn = resource.rn
	if resource.ty == C.tCSEBase: # if CSE
		return rn

	# retrieve identifier record of the parent
	if (pi := resource.pi) is None:
		# Logging.logErr('PI is None')
		return rn
	rpi = CSE.storage.identifier(pi) 
	if len(rpi) == 1:
		return rpi[0]['srn'] + '/' + rn
	Logging.logErr('Parent %s not fount in DB' % pi)
	return rn # fallback


def structuredPathFromRI(ri : str):
	""" Get the structured path of a resource by its ri. """
	if len((identifiers := CSE.storage.identifier(ri))) == 1:
		return identifiers[0]['srn']
	return None


def riFromStructuredPath(srn : str):
	""" Get the ri from a resource by its structured path. """
	if len((paths := CSE.storage.structuredPath(srn))) == 1:
		return paths[0]['ri']
	return None

def riFromCSI(csi : str):
	""" Get the ri from an CSEBase resource by its csi. """
	if (res := CSE.storage.retrieveResource(csi=csi)) is None:
		return None
	return res.ri


def retrieveIDFromPath(id : str, csern : str, cseri : str):
	""" Split a ful path e.g. from a http request into its component and return a local ri .
		The return tupple is (RI, CSI, SRN).
	"""
	csi 	= None
	spi 	= None
	srn 	= None
	ri 		= None

	# Prepare. Remove leading / and split
	if id[0] == '/':
		id = id[1:]
	ids = id.split('/')

	if (idsLen := len(ids)) == 0:	# There must be something!
		return (None, None, None)

	if ids[0] == '~' and idsLen >1:				# SP-Relative
		# print("SP-Relative")
		csi = ids[1]							# for csi
		if idsLen > 2 and ids[2] == csern:	# structured
			srn = '/'.join(ids[2:]) 
		elif idsLen == 3:						# unstructured
			ri = ids[2]
		else:
			return (None, None, None)

	elif ids[0] == '_' and idsLen >= 4:			# Absolute
		# print("Absolute")
		spi = ids[1]
		csi = ids[2]
		if ids[3] == csern:				# structured
			srn = '/'.join(ids[3:]) 
		elif idsLen == 4:						# unstructured
			ri = ids[3]
		else:
			return (None, None, None)

	else:										# CSE-Relative
		# print("CSE-Relative")
		if idsLen == 1 and (ids[0] != csern or ids[0] == cseri):	# unstructured
			ri = ids[0]
		else:									# structured
			srn = '/'.join(ids)

	# Now either csi, ri or structured is set
	if ri is not None:
		return (ri, csi, srn)
	if srn is not None:
		# if '/fopt' in ids:	# special handling for fanout points
		# 	return (srn, csi, srn)
		return (riFromStructuredPath(srn), csi, srn)
	if csi is not None:
		return (riFromCSI('/'+csi), csi, srn)
	# TODO do something with spi?
	return (None, None, None)




def resourceFromJSON(jsn, pi=None, acpi=None, tpe=None, create=False, isImported=False):
	""" Create a resource from a JSON structure.
		This will *not* call the activate method, therefore some attributes
		may be set separately.
	"""
	(jsn, root) = pureResource(jsn)	# remove optional "m2m:xxx" level
	ty = jsn['ty'] if 'ty' in jsn else tpe
	if ty != None and tpe != None and ty != tpe:
		return None
	mgd = jsn['mgd'] if 'mgd' in jsn else None		# for mgmtObj

	# Add extra acpi
	if acpi is not None:
		jsn['acpi'] = acpi if type(acpi) is list else [ acpi ]

	# store the import status in the original jsn
	if isImported:
		jsn[Resource.Resource._imported] = True	# Indicate that this is an imported resource


	# sorted by assumed frequency (small optimization)
	if ty == C.tCIN or root == C.tsCIN:
		return CIN.CIN(jsn, pi=pi, create=create)
	elif ty == C.tCNT or root == C.tsCNT:
		return CNT.CNT(jsn, pi=pi, create=create)
	elif ty == C.tGRP or root == C.tsGRP:
		return GRP.GRP(jsn, pi=pi, create=create)
	elif ty == C.tGRP_FOPT or root == C.tsGRP_FOPT:
		return GRP_FOPT.GRP_FOPT(jsn, pi=pi, create=create)
	elif ty == C.tACP or root == C.tsACP:
		return ACP.ACP(jsn, pi=pi, create=create)
	elif ty == C.tFCNT:
		return FCNT.FCNT(jsn, pi=pi, fcntType=root, create=create)	
	elif ty == C.tFCI:
		return FCI.FCI(jsn, pi=pi, fcntType=root, create=create)	
	elif ty == C.tAE or root == C.tsAE:
		return AE.AE(jsn, pi=pi, create=create)
	elif ty == C.tSUB or root == C.tsSUB:
		return SUB.SUB(jsn, pi=pi, create=create)
	elif ty == C.tCSR or root == C.tsCSR:
		return CSR.CSR(jsn, pi=pi, create=create)
	elif ty == C.tNOD or root == C.tsNOD:
		return NOD.NOD(jsn, pi=pi, create=create)
	elif (ty == C.tMGMTOBJ and mgd == C.mgdFWR) or root == C.tsFWR:
		return FWR.FWR(jsn, pi=pi, create=create)
	elif (ty == C.tMGMTOBJ and mgd == C.mgdSWR) or root == C.tsSWR:
		return SWR.SWR(jsn, pi=pi, create=create)
	elif (ty == C.tMGMTOBJ and mgd == C.mgdMEM) or root == C.tsMEM:
		return MEM.MEM(jsn, pi=pi, create=create)
	elif (ty == C.tMGMTOBJ and mgd == C.mgdANI) or root == C.tsANI:
		return ANI.ANI(jsn, pi=pi, create=create)
	elif (ty == C.tMGMTOBJ and mgd == C.mgdANDI) or root == C.tsANDI:
		return ANDI.ANDI(jsn, pi=pi, create=create)
	elif (ty == C.tMGMTOBJ and mgd == C.mgdBAT) or root == C.tsBAT:
		return BAT.BAT(jsn, pi=pi, create=create)
	elif (ty == C.tMGMTOBJ and mgd == C.mgdDVI) or root == C.tsDVI:
		return DVI.DVI(jsn, pi=pi, create=create)
	elif (ty == C.tMGMTOBJ and mgd == C.mgdDVC) or root == C.tsDVC:
		return DVC.DVC(jsn, pi=pi, create=create)
	elif (ty == C.tMGMTOBJ and mgd == C.mgdRBO) or root == C.tsRBO:
		return RBO.RBO(jsn, pi=pi, create=create)
	elif (ty == C.tMGMTOBJ and mgd == C.mgdEVL) or root == C.tsEVL:
		return EVL.EVL(jsn, pi=pi, create=create)
	elif ty == C.tCNT_LA or root == C.tsCNT_LA:
		return CNT_LA.CNT_LA(jsn, pi=pi, create=create)
	elif ty == C.tCNT_OL or root == C.tsCNT_OL:
		return CNT_OL.CNT_OL(jsn, pi=pi, create=create)
	elif ty == C.tFCNT_LA:
		return FCNT_LA.FCNT_LA(jsn, pi=pi, create=create)
	elif ty == C.tFCNT_OL:
		return FCNT_OL.FCNT_OL(jsn, pi=pi, create=create)

	elif ty == C.tCSEBase or root == C.tsCSEBase:
		return CSEBase.CSEBase(jsn, create=create)
	else:
		return Unknown.Unknown(jsn, ty, root, pi=pi, create=create)	# Capture-All resource
	return None


# return the "pure" json without the "m2m:xxx" resource specifier
excludeFromRoot = [ 'pi' ]
def pureResource(jsn):
	rootKeys = list(jsn.keys())
	if len(rootKeys) == 1 and rootKeys[0] not in excludeFromRoot:
		return (jsn[rootKeys[0]], rootKeys[0])
	return (jsn, None)


# find a structured element in JSON
def findXPath(jsn, element, default=None):     
	paths = element.split("/")
	data = jsn
	for i in range(0,len(paths)):
		if paths[i] not in data:
			return default
		data = data[paths[i]]
	return data


# set a structured element in JSON. Create if necessary, and observe the overwrite option
def setXPath(jsn, element, value, overwrite=True):
	paths = element.split("/")
	ln = len(paths)
	data = jsn
	for i in range(0,ln-1):
		if paths[i] not in data:
			data[paths[i]] = {}
		data = data[paths[i]]
	if paths[ln-1] in data is not None and not overwrite:
			return # don't overwrite
	data[paths[ln-1]] = value


urlregex = re.compile(
        r'^(?:http|ftp)s?://' 						# http://, https://, ftp://, ftps://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' # domain
        r'(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9]))|' # localhost or single name w/o domain
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' 		# ipv4
        r'(?::\d+)?' 								# optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)			# optional path


def isURL(url):
	""" Check whether a given string is a URL. """
	return url is not None and re.match(urlregex, url) is not None


def normalizeURL(url):
	""" Remove trailing / from the url. """
	if url is not None:
		while len(url) > 0 and url[-1] == '/':
			url = url[:-1]
	return url


def getIdFromOriginator(originator, idOnly=False):
	""" Get AE-ID-Stem or CSE-ID from the originator (in case SP-relative or Absolute was used) """
	if idOnly:
		return originator.split("/")[-1] if originator is not None  else originator
	else:
		return originator.split("/")[-1] if originator is not None and originator.startswith('/') else originator



def isAllowedOriginator(originator, allowedOriginators):
	""" Check whether an Originator is in the provided list of allowed 
		originators. This list may contain regex.
	"""
	if originator is None or allowedOriginators is None:
		return False
	for ao in allowedOriginators:
		if re.fullmatch(re.compile(ao), getIdFromOriginator(originator)):
			return True
	return False



#	Compare an old and a new resource. Keywords and values. Ignore internal __XYZ__ keys
#	Return a dictionary.
def resourceDiff(old, new):
	res = {}
	for k,v in new.items():
		if k.startswith('__'):	# ignore all internal attributes
			continue
		if not k in old:		# Key not in old
			res[k] = v
		elif v != old[k]:		# Value different
			res[k] = v 
	return res


def getCSE():
	return CSE.dispatcher.retrieveResource(Configuration.get('cse.ri'))

	
# Check whether the target contains a fanoutPoint in between or as the target
def fanoutPointResource(id):
	if id is None:
		return None
	# retrieve srn
	if not isStructured(id):
		id = structuredPathFromRI(id)
	if id is None:
		return None
	nid = None
	if id.endswith('/fopt'):
		nid = id
	elif '/fopt/' in id:
		(head, sep, tail) = id.partition('/fopt/')
		nid = head + '/fopt'
	if nid is not None:
		if (result := CSE.dispatcher.retrieveResource(nid))[0] is not None:
			return result[0]
	return None



#
#	HTTP request helper functions
#


def requestHeaderField(request, field):
	if not request.headers.has_key(field):
		return None
	return request.headers.get(field)

		
def getRequestHeaders(request):
	originator = requestHeaderField(request, C.hfOrigin)
	rqi = requestHeaderField(request, C.hfRI)

	# content-type
	ty = None
	if (ct := request.content_type) is not None:
		if not ct.startswith(tuple(C.supportedContentHeaderFormat)):
			ct = None
		else:
			p = ct.partition(';')
			ct = p[0] # content-type
			t = p[2].partition('=')[2]
			ty = int(t) if t.isdigit() else C.tUNKNOWN # resource type

	return (originator, ct, ty, rqi, C.rcOK)
