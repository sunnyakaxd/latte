# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import local

ACCESS_TYPES = [
	'read', 'write', 'create',
	'delete', 'rename', 'submit',
	'cancel', 'amend', 'report',
	'print', 'import', 'export',
	'email', 'share'
]

def on_doctype_update():
	from latte.utils.indexing import create_index
	create_index('tabPermission', ['doc_type', 'role', 'permlevel'], unique=True)

class Permission(Document):
	def autoname(self):
		self.name = self.doc_type + '-' + self.role + '-' + str(self.permlevel)

	def after_insert(self):
		self.update_custom_docperm()

	def on_update(self):
		self.update_custom_docperm()
		self.invalidate_cache()

	def invalidate_cache(self):
		from latte.utils.caching import invalidate
		invalidate('permissions')
		invalidate(f'meta|{self.doc_type}')

	def after_delete(self):
		self.reset_custom_docperm()
		self.invalidate_cache()

	def reset_custom_docperm(self):

		if not local.conf.use_permission_for_access:
			return

		existing_custom_docperms = [cdp.name for cdp in frappe.get_all('Custom DocPerm', {
			'parent': self.doc_type,
			'role': self.role,
		})]
		for custom_docperm in existing_custom_docperms:
			custom_docperm = frappe.get_doc('Custom DocPerm', custom_docperm)
			for _type in ACCESS_TYPES:
				if hasattr(custom_docperm, _type):
					setattr(custom_docperm, _type, 0)

			custom_docperm.save(ignore_permissions=True)

	def update_custom_docperm(self):

		if not local.conf.use_permission_for_access:
			return

		existing_custom_docperm = local.db.get_value('Custom DocPerm', {
			'parent': self.doc_type,
			'role': self.role,
			'permlevel': self.permlevel,
		})
		custom_docperm = frappe.get_doc('Custom DocPerm', existing_custom_docperm) if existing_custom_docperm else frappe.get_doc({
			'doctype': 'Custom DocPerm',
			'role': self.role,
			'parent': self.doc_type,
			'permlevel': self.permlevel,
		})
		for _type in ACCESS_TYPES:
			if hasattr(custom_docperm, _type):
				setattr(custom_docperm, _type, getattr(self, _type))

		custom_docperm.save(ignore_permissions=True)

	@staticmethod
	def update_permission(doctype, role, permlevel, ptype, value=None):

		''' Update access for given permission type in Permission document for specified role on a certain DocType. '''

		if not local.conf.use_permission_for_access:
			return

		existing_permission = local.db.get_value('Permission', {
			'doc_type': doctype,
			'role': role,
			'permlevel': permlevel,
		})
		permission = frappe.get_doc('Permission', existing_permission) if existing_permission else frappe.get_doc({
			'doctype': 'Permission',
			'role': role,
			'doc_type': doctype,
			'permlevel': permlevel,
		})
		if hasattr(permission, ptype):
			setattr(permission, ptype, value)
		permission.save(ignore_permissions=True)

	@staticmethod
	def validate_authorized_user(doctype, permission_on):

		''' Validate if a certain role has defined permission on the specified doctype. '''

		if not local.conf.use_permission_for_access:
			return

		if local.session.user.lower() == 'administrator':
			return

		permission_on = permission_on.lower()
		if permission_on not in ACCESS_TYPES:
			frappe.throw(f'{permission_on} is incorrect. Access type should be one of {frappe.utils.comma_and(ACCESS_TYPES)}')

		user_roles = set(frappe.get_roles())
		doctype_roles = set([row.role for row in frappe.get_all('Permission', {
			'doc_type': doctype,
			f'{permission_on}': 1,
		}, 'role')])
		allow = True if user_roles.intersection(doctype_roles) else False

		if not allow:
			frappe.throw(f'You are not authorized to {permission_on} {doctype}.')
