# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class PowerflowTransitionEvent(Document):
	
	def set_values(self, transition_data):
		self.previous_state = transition_data.get('previous_state')
		self.next_state = transition_data.get('next_state')
		self.user = transition_data.get('user')
		self.action = transition_data.get('action')
		self.powerflow_configuration = transition_data.get('powerflow_configuration')
		self.reason = transition_data.get('reason')
		self.transition_type =transition_data.get('transition_type')
