import frappe
from latte.json import loads
from frappe.desk.form.load import (
	run_onload,
	_get_communications,
	get_versions,
	get_assignments,
	get_doc_permissions,
	get_feedback_rating,
	get_view_logs
)
from latte.file_storage.file import get_files
# from latte.file_storage.doctype.attachment.attachment import get_attachments
from latte.business_process.powerflow.powerflow import get_powerflow_meta

@frappe.whitelist()
def getdoc(doctype, name, user=None):
	"""
	Loads a doclist for a given document. This method is called directly from the client.
	Requries "doctype", "name" as form variables.
	Will also call the "onload" method on the document.
	"""
	if not (doctype and name):
		raise Exception('doctype and name required!')

	if not name:
		name = doctype

	if not frappe.db.exists(doctype, name):
		return []

	try:
		doc = frappe.get_doc(doctype, name)
		doc.name = f'{doc.name}'

		run_onload(doc)

		if not doc.has_permission("read"):
			frappe.flags.error_message = f'Insufficient Permission for {frappe.bold(f"{doctype} {name}")}'
			raise frappe.PermissionError(("read", doctype, name))

		doc.apply_fieldlevel_read_permissions()

		# add file list
		doc.add_viewed()
		get_docinfo(doc)

	except Exception:
		frappe.errprint(frappe.utils.get_traceback())
		raise

	if doc and not name.startswith('_'):
		frappe.get_user().update_recent(doctype, name)

	doc.add_seen()
	doc.__onload['__powerflow_meta'] = get_powerflow_meta(doc)
	frappe.response.docs.append(doc)

@frappe.whitelist()
def get_docinfo(doc=None, doctype=None, name=None):
	if not doc:
		doc = frappe.get_doc(doctype, name)
		if not doc.has_permission("read"):
			raise frappe.PermissionError

	frappe.response["docinfo"] = {
		"attachments": get_files(doc.doctype, doc.name),
		"communications": _get_communications(doc.doctype, doc.name),
		'total_comments': len(loads(doc.get('_comments') or '[]')),
		'versions': get_versions(doc),
		"assignments": get_assignments(doc.doctype, doc.name),
		"permissions": get_doc_permissions(doc),
		"shared": frappe.share.get_users(doc.doctype, doc.name),
		"rating": get_feedback_rating(doc.doctype, doc.name),
		"views": get_view_logs(doc.doctype, doc.name)
	}