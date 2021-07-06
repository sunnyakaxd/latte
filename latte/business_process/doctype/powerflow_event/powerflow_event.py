# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from latte.utils.logger import  get_logger
from latte.business_process.powerflow.powerflow import execute_action, get_current_actions
from latte.business_process.powerflow_exceptions import AutoExecutionHaltPowerflowException
from latte.utils.logger import  get_logger

class PowerflowEvent(Document):

	def after_insert(self):
		error_log = None
		if self.event_type == "Local":
			powerflow_status_name = frappe.db.get_value("Powerflow Status", {"ref_doctype": self.ref_doctype, "ref_docname": self.ref_docname})
			if powerflow_status_name:
				powerflow_status = frappe.get_doc("Powerflow Status", powerflow_status_name)
				powerflow_configuration = frappe.get_doc("Powerflow Configuration", powerflow_status.powerflow_configuration)
				action = None
				for transition in powerflow_configuration.transitions:
					if transition.state == powerflow_status.current_state and transition.transition_type == "State" and transition.to == self.state:
						action = transition.action
						break

				if action:
					try:
						powerflow = frappe.get_doc(self.ref_doctype, self.ref_docname).get_workflow()
						powerflow.perform_transition(action, self.reason)
						self.error = None
						self.save(ignore_permissions = True)
					except AutoExecutionHaltPowerflowException as e:
						e.powerflow.save(ignore_permissions = True)
						self.error = None
						self.save(ignore_permissions = True)
					except Exception as e:
						error_log = frappe.log_error({"error":str(e),
						"traceback":frappe.get_traceback()
						},f"Failed to execute Workflow action - {self.ref_doctype} - {self.ref_docname} - {action} - {self.reason}")

				else:
					error_log = frappe.log_error(title = "Powerflow Event", message = f" No transition configured between state {powerflow_status.current_state} and \
						state {self.state} for {self.ref_docname} of type {self.ref_doctype} under Powerflow Configuration {powerflow_status.powerflow_configuration}")

			else:
				error_log = frappe.log_error(title = "Powerflow Event", message = f" {self.ref_docname} of type {self.ref_doctype} is not currently under any Powerflow Configuration")

		if error_log:
			self.error = error_log.name
			self.save(ignore_permissions=True)

	def on_change(self):
		logger = get_logger()
		logger.debug(f"Finding doc with {self.ref_doctype} - {self.ref_docname}")
		doc = frappe.get_doc(self.ref_doctype, self.ref_docname)
		logger.debug(f"Found doc {doc}")
		if doc:
			logger.debug(f"Running post save methods for {doc.as_dict()}")
			#commented bcoz always raise on_update event by latte
			# doc.run_method('on_update')
			doc.run_method('on_state_change')
