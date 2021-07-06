# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document
from latte.business_process.constants import HUMAN_TRANSITION_TYPE, SYSTEM_TRANSITION_TYPE

class PowerflowStatus(Document):

	def __init__(self, *args, powerflow_status=None, **kwargs):
		super().__init__(*args,**kwargs)
		self.transitions_collection = []
		self.communication_logs = []
		self.powerflow_event = None
	
	def add_transition_event(self, previous_state, action, human_transition, reason=None):
		transition_event = {
			'previous_state': previous_state,
			'next_state': self.current_state,
			'action': action,
			'user': frappe.session.user,
			'powerflow_configuration': self.powerflow_configuration,
			'transition_type': HUMAN_TRANSITION_TYPE if human_transition else SYSTEM_TRANSITION_TYPE,
			'reason': reason,
			'action_time': frappe.utils.now(),
		}

		self.transitions_collection.append(transition_event)
		self._add_communication_log(reason)

	def _add_communication_log(self, reason):
		msg = ''
		if reason:
			msg = f"""{self.current_state} with reason: <b>{reason or ''}</b>"""
		else:
			msg = f"""{self.current_state}"""
		communication_log = {
			'doctype': 'Communication',
			'reference_name': self.ref_docname,
			'reference_doctype': self.ref_doctype,
			'communication_type': 'Comment',
			'comment_type': 'Workflow',
			'content': msg,
		}
		self.communication_logs.append(communication_log)

	def save(self, *args, **kwargs):
		for communication_log in self.communication_logs:
			new_communication_log = frappe.get_doc(communication_log)
			new_communication_log.insert(ignore_permissions=True)

		self.communication_logs.clear()

		super().save(*args, **kwargs)
		for transition_event in self.transitions_collection:
			new_transition_event = self.append("transitions", transition_event)

		self.transitions_collection.clear()

		if self.powerflow_event:
			self.powerflow_event.save(ignore_permissions=True)
		super().save(*args, **kwargs)


	def update_configuration(self, name):
		self.powerflow_configuration = name

	def update_state(self,state):
		self.current_state = state
	
	def update_details(self, state_instance):
		self.update_state(state_instance.state)
		self.current_user = state_instance.get_assigned_user(self.ref_doctype, self.ref_docname)
		self.current_role = state_instance.role
		if state_instance.step_type == "Remote":
			self._add_powerflow_event()
	
	def get_last_transition_user(self):
		if len(self.transitions_collection):
			return self.transitions_collection[-1].get('user')
		elif self.transitions and len(self.transitions):
			return self.transitions[-1].get('user')

	def update_doc_status(self,new_doc_status):
		doc = frappe.get_doc(self.ref_doctype, self.ref_docname)
		if new_doc_status == 1 and doc.docstatus == 0:
			doc.flags.__submit_from_powerflow__ = True

		if new_doc_status == 1 and self.flags and self.flags.get('__call_from_capture_before_submit__'):
			return

		doc.update_docstatus(new_doc_status)

	def _add_powerflow_event(self):
		self.powerflow_event = frappe.get_doc({
			"doctype": "Powerflow Event",
			"ref_doctype": self.ref_doctype,
			"ref_docname": self.ref_docname,
			"state": self.current_state,
			"event_type": "Remote"
		})
		
		
	def on_update(self):
		ref_doc = frappe.get_doc(self.ref_doctype, self.ref_docname)
		ref_doc.run_method("on_powerflow_state_change", self.current_state)

def on_doctype_update():
	from latte.utils.indexing import create_index
	create_index('tabPowerflow Status', ['ref_doctype', 'ref_docname'], unique=True)
	create_index('tabPowerflow Status', ['ref_doctype', 'current_state'])
