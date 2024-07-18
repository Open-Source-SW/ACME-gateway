#
#	ACMEContainerUpdate.py
#
#	(c) 2024 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
"""	This module defines the *Update* view for the ACME text UI.
"""

from __future__ import annotations
from typing import cast

from textual.app import ComposeResult
from textual.containers import Container
from .ACMEViewResponse import ACMEViewResponse
from .ACMEViewRequest import ACMEViewRequest

from ..etc.Types import Operation
from ..helpers.ResourceSemaphore import CriticalSection, inCriticalSection
from ..resources.Resource import Resource
from ..runtime import CSE

class ACMEContainerUpdate(Container):

	BINDINGS = [('c', 'show_request', 'cURL command')]

	def __init__(self, id:str) -> None:
		"""	Initialize the view.

			Args:
				id:	The view ID.
		"""
		from ..textui.ACMETuiApp import ACMETuiApp

		super().__init__(id = id)

		self.requestOriginator = CSE.cseOriginator
		"""	The request originator. """

		self.resource:Resource = None
		"""	The resource to update. """

		self._app = cast(ACMETuiApp, self.app)
		"""	The application. """

		self.responseView:ACMEViewResponse = ACMEViewResponse(id = 'request-update-response')
		"""	The response view. """

		self.requestView:ACMEViewRequest = ACMEViewRequest(id = 'request-update-request', 
													 	   title = 'UPDATE Request',
													 	   header = 'Add, modify, and remove resource attributes.',
														   originator = self.requestOriginator,
														   buttonLabel = 'UPDATE Resource',
														   operation = Operation.UPDATE,
														   callback = self.doUpdate,
														   responseView = self.responseView
														   )
		"""	The request view. """

		from ..textui.ACMETuiApp import ACMETuiApp
		self._app = cast(ACMETuiApp, self.app)
		"""	The application. """


	def compose(self) -> ComposeResult:
		"""	Build the *Update* view.
		"""
		yield self.requestView
		yield self.responseView


	def updateResource(self, resource:Resource) -> None:
		"""	Update the resource to update.

			Args:
				resource:	The resource to update.
		"""
		self.resource = resource

		# Check whether we are currently doing a resource update (below). If so, return and don't update the editor.
		if inCriticalSection('tuiRequest'):
			return
		
		# Update the request originator. Important for getting a default request originator
		self.requestOriginator = self.resource.getOriginator()
		if self.requestOriginator:	
			self.requestView.updateOriginator(self.requestOriginator, [CSE.cseOriginator, self.requestOriginator])
		else: # No originator, use CSE originator
			self.requestView.updateOriginator(self.requestOriginator, [CSE.cseOriginator])

		# Update the request view
		self.requestView.updateResourceView(self.resource, 
									  		resourceType = None, 
											requestOriginator = self.resource.getOriginator()	)
		self.responseView.clear()


	def doUpdate(self) -> None:
		"""	Handle the *Send UPDATE Request* button event.
		"""

		# Send the request and handle the response
		if(result := self.requestView.runRequest(self.resource)):

			# The following is a critical section, because the resource tree has to be updated
			# but we don't want to update the editor. The 'updateResource()' method would do that.
			# There is a check for the critical section in the 'updateResource()' method above.
			# Display a success message and update the container tree
			with CriticalSection('tuiRequest', timeout = 0.0):
				self._app.containerTree.refreshCurrentNode()
				self._app.containerTree.updateResourceView(result.resource)


	def action_show_request(self) -> None:
		"""	Show the last / current request as cURL command.
		"""
		self.requestView.showCurlDialog(self.resource)

