# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from latte import read_only
from latte.business_process.doctype.powerflow_configuration.powerflow_configuration import PowerflowConfiguration
from latte.business_process.powerflow_exceptions import DocumentInWorkflowTransition, AutoExecutionHaltPowerflowException, PowerflowNotFoundException, WorkflowStateAccessException, SelfApprovalPowerflowException
from latte.business_process.doctype.powerflow_state.powerflow_state import PowerflowState
from latte.business_process.constants import POWERFLOW
import json
from latte.utils.caching import cache_in_mem


class Powerflow():

	ref_doc = None
	def __init__(self, powerflow_status=None):
		self.powerflow_status = powerflow_status
		self.current_configuration_doc = None

	def start(self, ref_document):
		try:
			if ref_document:
				ref_document.check_permission("submit")
			self.ref_doc = ref_document
			self.load_configuration()
			self.current_configuration_doc.update_state(self.powerflow_status)
			self.powerflow_status.flags.__call_from_capture_before_submit__ = True
			self.powerflow_status.add_transition_event("", "", True, "")
			self._execute_action(True)
		except WorkflowStateAccessException:
			frappe.throw("User dont have have permission to perform this action")

	def perform_transition(self, action, reason=None):
		self.load_configuration()
		self.__validate_user_role_permissions()
		self._perform_transition(action, True, reason)

	def _perform_transition(self, action, human_transition, reason=None):
		current_state = self.powerflow_status.current_state
		self.current_configuration_doc.perform_transition(self.powerflow_status, action, reason, human_transition)
		self.update_configuration()
		self.powerflow_status.add_transition_event(current_state, action, human_transition, reason)
		self._execute_action(human_transition)

	def _execute_action(self,human_transition):
		action_result = self.current_configuration_doc.execute_state_script(self.powerflow_status.current_state, self.powerflow_status.ref_docname)
		if action_result:
			self._perform_transition(action_result, False)
		else:
			state_doc_status = self.current_configuration_doc.get_state_docstatus(self.powerflow_status.current_state)
			if state_doc_status == 0:
				if self.ref_doc:
					self.ref_doc.flags.ignore_submit = True
					self.ref_doc.docstatus = 0
					# doc = frappe.get_doc(self.current_configuration_doc.ref_doctype, self.powerflow_status.ref_docname)
					# doc.flags.ignore_submit = True
				# raise AutoExecutionHaltPowerflowException(self.powerflow_status)


			self.powerflow_status.save(ignore_permissions=True)
			self.powerflow_status.update_doc_status(state_doc_status)

	def load_configuration(self):
		if not self.current_configuration_doc:
			self._load_configuration(self.powerflow_status.powerflow_configuration)

	def update_configuration(self):
		if self.current_configuration_doc.name != self.powerflow_status.powerflow_configuration:
			self.current_configuration_doc = None
			self.load_configuration()
			self.current_configuration_doc.update_state(self.powerflow_status)

	def _load_configuration(self,name):
		self.current_configuration_doc = PowerflowConfiguration.get_configuration(self.powerflow_status.ref_doctype, name)
		self.powerflow_status.powerflow_configuration = self.current_configuration_doc.name

	def get_actions(self):
		try:
			self.load_configuration()
			self.__validate_user_role_permissions()
			return self.current_configuration_doc.get_transitions(self.powerflow_status.current_state, self.powerflow_status.get_last_transition_user())
		except Exception:
			return None

	def __validate_user_role_permissions(self):
		roles = frappe.get_roles()
		if self.powerflow_status.current_role in roles:
			if self.powerflow_status.current_user and self.powerflow_status.current_user != frappe.session.user:
				raise WorkflowStateAccessException()
			return True
		raise WorkflowStateAccessException()

	@staticmethod
	def get_workflow(doc):
		filter_to_get_doc = {
			'ref_doctype': doc.doctype,
			'ref_docname': doc.name,
		}
		powerflow_name = frappe.db.get_value("Powerflow Status", filter_to_get_doc, 'name')
		if powerflow_name:
			return frappe.get_doc("Powerflow Status", powerflow_name)

	@staticmethod
	@cache_in_mem(key=lambda doctype:doctype, timeout=60)
	def is_enabled_for(doctype):
		return not not frappe.db.get_value("Powerflow Configuration",{
			'ref_doctype': doctype,
			'is_active': 1,
		})

def attach_workflow(doc, event=None):
	if doc.flags and doc.flags.get("__submit_from_powerflow__"):
		return
	workflow = doc.get_workflow()
	if not workflow:
		doc.initialize_workflow()
	else:
		raise DocumentInWorkflowTransition()


@frappe.whitelist()
@read_only()
def get_current_actions(doctype, docname):
	try:
		if frappe.db.exists(doctype,docname):
			powerflow = frappe.get_doc(doctype,docname).get_workflow()
			if powerflow:
				return powerflow.get_actions()
	except PowerflowNotFoundException as e:
		frappe.throw("Failed to fetch required workflow configurations", exc=e)
	except Exception:
		frappe.throw("Failed to fetch required configurations")

@frappe.whitelist()
def execute_action(doctype, docname, action, reason=None):
	powerflow = frappe.get_doc(doctype, docname).get_workflow()
	if powerflow:
		try:
			powerflow.perform_transition(action, reason)
		except AutoExecutionHaltPowerflowException as e:
			frappe.db.rollback()
			e.powerflow.save(ignore_permissions=True)
		except Exception as e:
			frappe.log_error({"error":str(e),
			"traceback":frappe.get_traceback()
			},f"Failed to execute Workflow action - {doctype} - {docname} - {action} - {reason}")
			raise

def get_hooks():
	dts = frappe.get_all('Powerflow Configuration', fields=['distinct ref_doctype'])
	return {
		'doc_events': {
			row.ref_doctype: {
				'attach_workflow': 'latte.business_process.powerflow.powerflow.attach_workflow',
			}
			for row in dts
		}
	}

def get_powerflow_meta(doc):
	powerflow_status = frappe.db.get_value('Powerflow Status', {
		'ref_doctype': doc.doctype,
		'ref_docname': doc.name,
	}, fieldname=['current_state', 'powerflow_configuration'], as_dict=True)
	if not powerflow_status:
		return
	state_meta = frappe.db.get_value('Powerflow State', filters={
		'parent': powerflow_status.powerflow_configuration,
		'state': powerflow_status.current_state,
	}, fieldname=[
		'state',
		'style',
	], as_dict=True)

	return state_meta.update(powerflow_status)

@frappe.whitelist()
def bulk_execute_action(doctype, doc_list=None, action='', reason=None):
	for docname in json.loads(doc_list):
		try:
			execute_action(doctype, docname, action, reason)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()


