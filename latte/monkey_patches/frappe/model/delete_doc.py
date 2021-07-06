
import frappe
import frappe.model.delete_doc
import frappe.defaults
from frappe.model.delete_doc import (
	delete_all_passwords_for,
	update_flags,
	check_permission_and_not_submitted,
	delete_from_table,
	check_if_doc_is_linked,
	check_if_doc_is_dynamically_linked,
	update_naming_series,
	remove_all,
	delete_for_document,
	add_to_deleted_document,
	string_types,
	integer_types,
	insert_feed
)
from latte.latte_core.doctype.permission.permission import Permission

def delete_doc(doctype=None, name=None, force=0, ignore_doctypes=None, for_reload=False,
	ignore_permissions=False, flags=None, ignore_on_trash=False, ignore_missing=True):
	"""
		Deletes a doc(dt, dn) and validates if it is not submitted and not linked in a live record
	"""
	if not ignore_doctypes: ignore_doctypes = []

	# get from form
	if not doctype:
		doctype = frappe.form_dict.get('dt')
		name = frappe.form_dict.get('dn')

	names = name
	if isinstance(name, string_types) or isinstance(name, integer_types):
		names = [name]

	if not (for_reload or ignore_permissions or force):
		Permission.validate_authorized_user(doctype, 'delete')

	for name in names or []:

		# already deleted..?
		if not frappe.db.exists(doctype, name):
			if not ignore_missing:
				raise frappe.DoesNotExistError
			else:
				return False

		# delete passwords
		delete_all_passwords_for(doctype, name)

		doc = None
		if doctype=="DocType":
			if for_reload:

				try:
					doc = frappe.get_doc(doctype, name)
				except frappe.DoesNotExistError:
					pass
				else:
					doc.run_method("before_reload")

			else:
				doc = frappe.get_doc(doctype, name)

				update_flags(doc, flags, ignore_permissions)
				check_permission_and_not_submitted(doc)

				frappe.db.sql("delete from `tabCustom Field` where dt = %s", name)
				frappe.db.sql("delete from `tabCustom Script` where dt = %s", name)
				frappe.db.sql("delete from `tabProperty Setter` where doc_type = %s", name)
				frappe.db.sql("delete from `tabReport` where ref_doctype=%s", name)
				frappe.db.sql("delete from `tabCustom DocPerm` where parent=%s", name)

			delete_from_table(doctype, name, ignore_doctypes, None)

		else:
			doc = frappe.get_doc(doctype, name)

			if not for_reload:
				update_flags(doc, flags, ignore_permissions)
				check_permission_and_not_submitted(doc)

				if not ignore_on_trash:
					doc.run_method("on_trash")
					doc.flags.in_delete = True
					doc.run_method('on_change')

				frappe.enqueue('frappe.model.delete_doc.delete_dynamic_links', doctype=doc.doctype, name=doc.name,
					is_async=False if frappe.flags.in_test else True)

				# check if links exist
				if not force:
					check_if_doc_is_linked(doc)
					check_if_doc_is_dynamically_linked(doc)

			update_naming_series(doc)
			delete_from_table(doctype, name, ignore_doctypes, doc)
			doc.run_method("after_delete")

			# delete attachments
			remove_all(doctype, name, from_delete=True)

		# delete global search entry
		delete_for_document(doc)

		if doc and not for_reload:
			add_to_deleted_document(doc)
			if not frappe.flags.in_patch:
				try:
					doc.notify_update()
					insert_feed(doc)
				except ImportError:
					pass

			# delete user_permissions
			frappe.defaults.clear_default(parenttype="User Permission", key=doctype, value=name)

frappe.model.delete_doc.delete_doc = delete_doc