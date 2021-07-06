# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from latte.business_process.powerflow_exceptions import PowerflowNotFoundException, InvalidPowerflowActionException, WorkflowStateAccessException, SelfApprovalPowerflowException
from latte.business_process.doctype.powerflow_state.powerflow_state import PowerflowState
from latte.business_process.constants import POWERFLOW


class PowerflowConfiguration(Document):

	@staticmethod
	def get_configuration(doctype, configuration_name=None):
		if configuration_name:
			return frappe.get_doc("Powerflow Configuration", configuration_name)
		else:
			default_configuration = frappe.db.get_value("Powerflow Configuration",{
				'ref_doctype':doctype,
				'is_default':1,
				'is_active':1,
				}, "name")
			if default_configuration:
				return frappe.get_doc("Powerflow Configuration", default_configuration)
			else:
				powerflow_configuration_name = frappe.db.get_value("Powerflow Configuration",{
					'ref_doctype':doctype,
					'is_default':1,
					'is_active':1,
					}, 'name')
				if powerflow_configuration_name:
					return frappe.get_doc("Powerflow Configuration", powerflow_configuration_name)
				else:
					raise PowerflowNotFoundException()	

	def get_transition(self, current_state,execute_action):
		for transition in self.transitions:
			if transition.state == current_state and transition.action == execute_action:
				return transition
		else:
			raise InvalidPowerflowActionException()


	def get_state_instance(self,state):
		for state_instance in self.states:
			if state_instance.state == state:
				return state_instance
		frappe.throw(f"Invalid workflow configurations, '{state}' not found in {self.name} powerflow configuration. Please check with administrator")

	def get_transitions(self, current_state, last_user):
		state = self.get_state_instance(current_state)
		if state.step_type == "Remote":
			return None
		state.validate(last_user)
		return self._get_transitions(state)
	
	def _get_transitions(self, state):
		try:
			return [
				transition
				for transition in self.transitions
				if
				transition.state == state.state
			]
		except (SelfApprovalPowerflowException, WorkflowStateAccessException):
			return None

	def _validate_state_permissions(self, state, last_user, human_transition):
		state_instance = self.get_state_instance(state)
		state_instance.validate(last_user)

	def perform_transition(self, powerflow_status, action, reason, human_transition):
		current_state = powerflow_status.current_state
		if human_transition:
			self._validate_state_permissions(current_state, powerflow_status.get_last_transition_user(), human_transition)
		
		transition = self.get_transition(current_state, action)
		transition.validate(reason)

		if transition.transition_type == POWERFLOW:
			powerflow_status.update_configuration(transition.to)
		else:
			self.update_state(powerflow_status, transition.to)


	def update_state(self, powerflow_status, state=None):
		if not state:
			state = self.initial_state

		state_instance = self.get_state_instance(state)
		powerflow_status.update_details(state_instance)

	def execute_state_script(self, state, docname):
		state = self.get_state_instance(state)
		return state.execute(self.ref_doctype, docname)

	def get_state_docstatus(self, state):
		state = self.get_state_instance(state)
		return int(state.doc_status)

	def validate(self):
		self.validate_single_default()
		self.validate_transitions()

	def validate_single_default(self):
		if not self.is_default:
			return

		others = frappe.get_all('Powerflow Configuration', {
			'ref_doctype': self.ref_doctype,
			'is_default': 1,
			'is_active': 1,
			'name': ['!=', self.name],
		})
		if others:
			frappe.throw(f'''
				{frappe.utils.href("Powerflow", others[0].name)}
				is already set as default for {self.ref_doctype}
			''')

	def validate_transitions(self):
		present_set = set()
		valid_states = set(row.state for row in self.states)
		for row in self.transitions:
			if row.state not in valid_states:
				frappe.throw(f'Transition state {row.state} is not defined in States table')
			transition = row.state, row.action,
			if transition in present_set:
				frappe.throw(f'State {row.state} and Action {row.action} are not unique in transitions')
			present_set.add(transition)
