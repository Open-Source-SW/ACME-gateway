#
#	ACMEViewResponse.py
#
#	(c) 2024 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
"""	This module defines a view to display request responses.
"""

from __future__ import annotations
from typing import Optional, cast

from rich.console import RenderableType
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static
from ..etc.ResponseStatusCodes import ResponseStatusCode

class ACMEViewResponse(VerticalScroll):
	"""	View to display request responses.
	"""

	_title = 'Response'

	def __init__(self, id:str):
		"""	Initialize the view.

			Args:
				id:	The view ID.
		"""
		super().__init__(id = id, classes = 'response-view-normal')
		self.response = Static('', id = f'{id}-content', classes = 'response-view-content')

		self.clear()


	def compose(self) -> ComposeResult:
		yield self.response

		from ..textui.ACMETuiApp import ACMETuiApp
		self._app = cast(ACMETuiApp, self.app)
		"""	The application. """



	def clear(self) -> None:
		"""	Clear the response.
		"""
		self.response.update('')
		self.border_title = self._title
		self.classes = 'response-view-normal'


	def success(self, renderable:RenderableType, rsc:Optional[ResponseStatusCode] = None) -> None:
		"""	Display a success response.

			Args:
				renderable:	The response text or renderable.
				rsc:		The response status code.
		"""
		self.response.update(renderable)
		self.classes = 'response-view-success'
		if rsc is not None:
			self.border_title = f'{self._title} [r] {rsc.value} {rsc.nname()} [/r]'
		else:
			self.border_title = self._title

	
	def error(self, renderable:RenderableType, rsc:Optional[ResponseStatusCode] = None, title:Optional[str] = 'ERROR') -> None:
		"""	Display an error response.

			Args:
				renderable:	The response text.
				rsc:		The response status code. Only used when the response is a string.
		"""
		
		if isinstance(renderable, str):
			self.response.update(f'[red]{renderable}[/red]')
			if rsc is not None:
				self.border_title = f'{self._title} [r] {rsc.value} {rsc.nname()} [/r]'
				# popup error notification
				self._app.showNotification(f'\n{rsc.nname()}\n\n{renderable}', title, 'error')
			else:
				self.border_title = self._title

		else:
			self.response.update(renderable)
		self.classes = 'response-view-error'