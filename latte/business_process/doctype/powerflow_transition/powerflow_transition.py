# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from latte.business_process.powerflow_exceptions import PowerflowTransitionAccessException,  MandatoryReasonPowerflowException
from latte.business_process.constants import POWERFLOW

class PowerflowTransition(Document):
	
	def validate(self, has_reason_provided):
		self.__validate_for_reason(has_reason_provided)

	def __validate_for_reason(self, has_reason_provided):
		if self.is_reason_required:
			if has_reason_provided:
				return
			frappe.throw("Reason is mandatory for this transition")
	
	def perform_transition(self, powerflow_status, reason):
		self.validate(reason)

		if self.transition_type == POWERFLOW:
			powerflow_status.update_configuration(self.to)
		else:
			powerflow_status.update_state(self.to) 
			
				
