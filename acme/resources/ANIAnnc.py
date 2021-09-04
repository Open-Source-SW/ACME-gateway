#
#	ANIAnnc.py
#
#	(c) 2020 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	ANI : Announceable variant
#

from ..etc.Types import ResourceTypes as T, JSON
from ..services.Validator import constructPolicy, addPolicy
from ..resources.MgmtObjAnnc import *

# Attribute policies for this resource are constructed during startup of the CSE
aniAPolicies = constructPolicy([
	'ant', 'ldv'
])
attributePolicies =  addPolicy(mgmtObjAAttributePolicies, aniAPolicies)
# TODO resourceMappingRules, announceSyncType, owner

class ANIAnnc(MgmtObjAnnc):

	def __init__(self, dct:JSON=None, pi:str=None, create:bool=False) -> None:
		super().__init__(dct, pi, mgd=T.ANI, create=create, attributePolicies=attributePolicies)

