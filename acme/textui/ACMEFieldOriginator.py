 #
#	ACMEFieldOriginator.py
#
#	(c) 2023 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#

from __future__ import annotations
from dataclasses import dataclass
from typing import cast

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Middle
from textual.widgets import Input, Label
from textual.suggester import SuggestFromList
from textual.validation import Function
from textual import on
from textual.message import Message


class ACMEInputField(Container):
	
	DEFAULT_CSS = """
	ACMEInputField {
		width: 1fr;
		height: 3;
		layout: horizontal;
		overflow: hidden hidden;
		# background: red;
		content-align: left middle;
		margin: 1 1 1 1;
	}

	#field-label {
		height: 1fr;
		content-align: left middle;
		align: left middle;
	}

	#field-input-view {
		width: 1fr;
	}

	#field-message {
		height: 1fr;
		width: 1fr;
		margin-left: 1;
		color: red;
	}
	"""

	@dataclass
	class Submitted(Message):
		input: ACMEInputField
		"""The *Input* widget that is being submitted."""
		value: str
		"""The value of the *Input* being submitted."""



	def __init__(self, label:str = 'a label',
		  			   value:str = '',
					   suggestions:list[str] = [],
					   placeholder:str = '',
					   validators:Function = None,
					   id:str = None) -> None:
		# TODO list of originators as a suggestion
		super().__init__(id = id)
		self._suggestions = suggestions
		self._labelText = label
		self._value = value
		self._placeholder = placeholder
		self._validators = validators


	def compose(self) -> ComposeResult:
		yield Label(f'[b]{self._labelText}[/b] ', id = f'field-label')
		with Vertical(id = 'field-input-view'):
			yield Input(value = self._value, 
						placeholder = self._placeholder,
						suggester = SuggestFromList(self._suggestions),
						validators = self._validators,
						id = 'field-input')
			yield Label('', id = 'field-message')


	@on(Input.Changed)
	def show_invalid_reasons(self, event:Input.Changed) -> None:
		# Updating the UI to show the reasons why validation failed
		if event.validation_result and not event.validation_result.is_valid:  
			self.msgField.update(event.validation_result.failure_descriptions[0])
		else:
			self.msgField.update('')
			self.originator = event.value


	@on(Input.Submitted, '#field-input')
	async def submit(self, event:Input.Submitted) -> None:
		self.post_message(self.Submitted(self, self.inputField.value))


	def setLabel(self, label:str) -> None:
		""" Set the label of the field.
		
			Args:
				label: The label to set.
		"""
		cast(Label, self.query_one('#field-label')).update(f'[b]{label}[/b] ')
	

	@property
	def value(self) -> str:
		return cast(Input, self.query_one('#field-input')).value


	@value.setter
	def value(self, value:str) -> None:
		self._value = value
		try:
			self.inputField.value = value
		except:
			pass
	
	
	@property
	def msgField(self) -> Label:
		return cast(Label, self.query_one('#field-message'))
	
	
	@property
	def inputField(self) -> Input:
		return cast(Input, self.query_one('#field-input'))
	
	
	def setSuggestions(self, suggestions:list[str]) -> None:
		""" Set the suggestions for the input field.
		
			Args:
				suggestions: The suggestions to set.
		"""
		self.suggestions = suggestions
		self.inputField.suggester = SuggestFromList(self.suggestions)


# TODO This may has to be turned into a more generic field class

idFieldOriginator = 'field-originator'

def validateOriginator(value: str) -> bool:
	return value is not None and len(value) > 1 and value.startswith(('C', 'S', '/')) and not set(value) & set(' \t\n')

class ACMEFieldOriginator(ACMEInputField):
	def __init__(self, originator:str, suggestions:list[str] = []) -> None:
		super().__init__(label = 'Originator',
		   				 suggestions = suggestions,
						 placeholder = 'Originator',
						 validators = Function(validateOriginator, 
				 							   'Wrong originator format: Must start with "C", "S" or "/", contain now white spaces, and have length > 1.')
						)
		self.originator = originator
		self.suggestions = suggestions

	def update(self, originator:str, suggestions:list[str] = []) -> None:
		self.originator = originator
		self.suggestions = suggestions
		self.value = originator
		self.setSuggestions(suggestions)
