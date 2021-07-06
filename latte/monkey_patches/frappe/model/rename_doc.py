import frappe
import frappe.model.rename_doc
from frappe.model.rename_doc import (
	cint,
	validate_rename,
	rename_parent_and_child,
	get_link_fields,
	update_link_field_values,
	rename_dynamic_links,
	update_user_settings,
	rename_versions,
	update_attachments,
	rename_password,
	rename_doctype
)
from latte.latte_core.doctype.permission.permission import Permission

@frappe.whitelist()
def rename_doc(doctype, old, new, force=False, merge=False, ignore_permissions=False, ignore_if_exists=False):
	"""
		Renames a doc(dt, old) to doc(dt, new) and
		updates all linked fields of type "Link"
	"""
	if not frappe.db.exists(doctype, old):
		return

	if ignore_if_exists and frappe.db.exists(doctype, new):
		return

	if old==new:
		frappe.msgprint('Please select a new name to rename.')
		return

	if not ignore_permissions:
		Permission.validate_authorized_user(doctype, 'rename')

	force = cint(force)
	merge = cint(merge)

	meta = frappe.get_meta(doctype)

	# call before_rename
	old_doc = frappe.get_doc(doctype, old)
	new = ' '.join((new or '').split())
	out = old_doc.run_method("before_rename", old, new, merge) or {}
	new = (out.get("new") or new) if isinstance(out, dict) else (out or new)

	if doctype != "DocType":
		new = validate_rename(doctype, new, meta, merge, force, ignore_permissions)

	if not merge:
		rename_parent_and_child(doctype, old, new, meta)

	# update link fields' values
	link_fields = get_link_fields(doctype)
	update_link_field_values(link_fields, old, new, doctype)

	rename_dynamic_links(doctype, old, new)

	# save the user settings in the db
	frappe.utils.background_jobs.enqueue(
		update_user_settings,
		old=old,
		new=new,
		link_fields=link_fields,
		enqueue_after_commit=True,
	)
	# update_user_settings(old, new, link_fields)

	if doctype=='DocType':
		rename_doctype(doctype, old, new, force)

	update_attachments(doctype, old, new)

	rename_versions(doctype, old, new)

	# call after_rename
	new_doc = frappe.get_doc(doctype, new)

	# copy any flags if required
	new_doc._local = getattr(old_doc, "_local", None)

	new_doc.run_method("after_rename", old, new, merge)

	if not merge:
		rename_password(doctype, old, new)

	# update user_permissions
	frappe.db.sql("""update tabDefaultValue set defvalue=%s where parenttype='User Permission'
		and defkey=%s and defvalue=%s""", (new, doctype, old))

	if merge:
		new_doc.add_comment('Edit', f"merged {frappe.bold(old)} into {frappe.bold(new)}")
	else:
		new_doc.add_comment('Edit', f"renamed from {frappe.bold(old)} to {frappe.bold(new)}")

	if merge:
		frappe.delete_doc(doctype, old)

	frappe.clear_cache()
	frappe.enqueue('frappe.utils.global_search.rebuild_for_doctype', doctype=doctype)

	return new

frappe.model.rename_doc.rename_doc = rename_doc