#
#	DEPR.py
#
#	(c) 2022 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	ResourceType: Dependency
#

from __future__ import annotations
from typing import Optional, Tuple, Any, cast

from ..etc.Types import AttributePolicyDict, EvalMode, ResourceTypes, Result, JSON, Permission, EvalCriteriaOperator
from ..etc.Types import BasicType
from ..etc.Utils import findXPath
from ..services import CSE
from ..services.Logging import Logging as L
from ..resources.Resource import Resource
from ..resources.AnnounceableResource import AnnounceableResource


class DEPR(AnnounceableResource):

	# Specify the allowed child-resource types
	_allowedChildResourceTypes:list[ResourceTypes] = [ ResourceTypes.SUB ] 
	""" The allowed child-resource types. """

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
		'lbl': None,
		'acpi':None,
		'et': None,
		'daci': None,
		'at': None,
		'aa': None,
		'ast': None,
		'cstn': None,
		'cr': None,

		# Resource attributes
		'sfc': None,
		'evc': None,
		'rri': None,
	}


	def __init__(self, dct:Optional[JSON] = None, pi:Optional[str] = None, create:Optional[bool] = False) -> None:
		super().__init__(ResourceTypes.DEPR, dct, pi, create = create)


	def activate(self, parentResource: Resource, originator: str) -> Result:

		if not (res := super().activate(parentResource, originator)).status:
			return res


		# 2) The Receiver shall check the existence and accessibility of the resource defined in the 
		# referencedResourceID attribute. If the resource does not exist or is not accessible by the Originator, 
		# then the Receiver shall return a response primitive with a Response Status Code indicating "BAD_REQUEST" error.

		# 3) The Receiver shall check that the attribute referenced by the subject element of the evalCriteria
		#  attribute is an attribute of the resource type referenced by the referencedResourceID attribute. 
		# If it is not, the receiver shall return a response primitive with a Response Status Code indicating 
		# "BAD_REQUEST" error.

		# 4) The Receiver shall check that the value provided for the threshold element of the evalCriteria
		#  attribute is within the value space (as defined in [3]) of the data type of the subject element of 
		# the evalCriteria attribute. The Receiver shall also check that the value provided for the operator 
		# element of the evalCriteria attribute is a valid value based on Table 6.3.4.2.861. If either 
		# check fails, the receiver shall return a response primitive with a Response Status Code indicating 
		# "BAD_REQUEST" error.

		# 5) Process the <dependency> resource as described in clause 10.2.21 of oneM2M TS-0001 [6] after Recv-6.7.


		return super().activate(parentResource, originator)
	

	def update(self, dct: JSON = None, originator: Optional[str] = None, doValidateAttributes: Optional[bool] = True) -> Result:

		# 13)If the evalCriteria attribute is present in the request, the Receiver shall check that the 
		# attribute referenced by the subject element of the evalCriteria attribute is an attribute of the
		# resource type referenced by the referencedResourceID attribute. If it is not, the receiver shall
		#  return a response primitive with a Response Status Code indicating "BAD_REQUEST" error.

		# 14)If the evalCriteria attribute is present in the request, the Receiver shall check the value 
		# provided for the threshold element of the evalCriteria attribute is within the value space 
		# (as defined in [3]) of the data type of the subject element of the evalCriteria attribute. 
		# The Receiver shall also check that the value provided for the operator element of the evalCriteria 
		# attribute is a valid value based on Table 6.3.4.2.861. If either check fails, the receiver shall 
		# return a response primitive with a Response Status Code indicating "BAD_REQUEST" error.

		# 15)Process the <dependency> resource as described in clause 10.2.21 of oneM2M TS-0001 [6] after Recv-6.7.


		return super().update(dct, originator, doValidateAttributes)