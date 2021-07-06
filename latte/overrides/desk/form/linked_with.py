import frappe
import latte
from frappe.desk.form.linked_with import (
	get_linked_doctypes,
	get_linked_docs
)

@frappe.whitelist()
@latte.read_only()
def read_only_get_linked_doctypes(doctype, without_ignore_user_permissions_enabled=False):
	return get_linked_doctypes(
		doctype=doctype,
		without_ignore_user_permissions_enabled=without_ignore_user_permissions_enabled
	)

@frappe.whitelist()
@latte.read_only()
def read_only_get_linked_docs(doctype, name, linkinfo=None, for_doctype=None):
	return get_linked_docs(
		doctype=doctype,
		name=name,
		linkinfo=linkinfo,
		for_doctype=for_doctype
	)