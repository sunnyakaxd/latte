# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from latte.business_process.powerflow_exceptions import WorkflowStateAccessException, SelfApprovalPowerflowException
from latte.json import loads, dumps
from RestrictedPython import compile_restricted, safe_globals
import math
from latte.json import loads, dumps

class PowerflowState(Document):

	def __get_doc(self, doctype, docname):
		return frappe.get_doc(doctype, docname)

	def validate(self, last_transition_user):
		if "Administrator" not in frappe.get_roles():
			self.__validate_for_last_transition(last_transition_user)

	def __validate_for_last_transition(self, last_transition_user):
		if not self.allow_previous_approver:
			if frappe.session.user == last_transition_user:
				raise SelfApprovalPowerflowException()

	def execute(self, doctype, docname):
		return self.__execute_script(doctype,docname,self.script)

	def __execute_script(self, doctype, docname, script_to_execute):
		if script_to_execute:
			doc = self.__get_doc(doctype,docname)
			local_dict = {}
			patched_safe_globals = dict(safe_globals)
			script_result = None
			patched_safe_globals.update(self.get_context())
			script_to_execute = script_to_execute.replace('\n', '\n\t')
			code =f'''
def execute_me(doc):
	{script_to_execute.strip()}
'''
			byte_code = compile_restricted(code, '<inline>', 'exec')
			builtins_dict = patched_safe_globals.get("__builtins__")
			builtins_dict['print_var'] = lambda *_: print(*_)
			patched_safe_globals.update({'__builtins__': builtins_dict})
			exec(byte_code, patched_safe_globals, local_dict)
			script_result = local_dict.get('execute_me')(doc)
			if script_result:
				return script_result.strip()

	def get_assigned_user(self, doctype, docname):
		return self.__execute_script(doctype,docname,self.user)

	def get_context(self,):
		return frappe._dict({
			'_write_': lambda x: x,
			'_getitem_': lambda o, a: o[a],
			'_getattr_': getattr,
			'_getiter_': iter,
			'any': any,
			'all': all,
			'math': math,
			'frappe': frappe._dict({
				'loads': loads,
				'dumps': dumps,
				'get_doc': frappe.get_doc,
				'get_cached_doc': frappe.get_cached_doc,
				'get_cached_value': frappe.get_cached_value,
				'db': frappe._dict({
					'get_value': lambda *args, **kwargs: frappe.local.db.get_value(*args, **kwargs),
				}),
				'get_all': frappe.get_all,
				"get_url": frappe.utils.get_url,
				'format': frappe.format_value,
				"format_value": frappe.format_value,
				"get_meta": frappe.get_meta,
				'get_system_settings': frappe.get_system_settings,
				"utils": frappe.utils.data,
				"render_template": frappe.render_template,
				'session': {
					'user': frappe.session.user,
				},
				"socketio_port": frappe.conf.socketio_port,
				"call": frappe.call,
				"throw": frappe.throw,
			}),
		})



