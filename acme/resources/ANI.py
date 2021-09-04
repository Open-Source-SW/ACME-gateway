#
#	ANI.py
#
#	(c) 2020 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	ResourceType: mgmtObj:areaNwkInfo
#

from ..etc.Types import ResourceTypes as T, JSON
from ..services.Validator import constructPolicy, addPolicy
from ..resources.MgmtObj import *

# Attribute policies for this resource are constructed during startup of the CSE
aniPolicies = constructPolicy([
	'ant', 'ldv'
])
attributePolicies =  addPolicy(mgmtObjAttributePolicies, aniPolicies)

defaultAreaNwkType = ''


class ANI(MgmtObj):

	def __init__(self, dct:JSON=None, pi:str=None, create:bool=False) -> None:
		self.resourceAttributePolicies = aniPolicies	# only the resource type's own policies
		super().__init__(dct, pi, mgd=T.ANI, create=create, attributePolicies=attributePolicies)

		self.setAttribute('ant', defaultAreaNwkType, overwrite=False)
