import frappe

from frappe.desk.form import run_method
from latte.json import loads
from frappe import local

@frappe.whitelist()
def runserverobj(method, docs=None, dt=None, dn=None, arg=None, args=None):
	"""run controller method - old style"""
	if not args: args = arg or ""

	if dt: # not called from a doctype (from a page)
		if not dn: dn = dt # single
		doc = frappe.get_doc(dt, dn)

	else:
		doc = frappe.get_doc(loads(docs))
		doc._original_modified = doc.modified
		doc.check_if_latest()

	local.flags.current_running_method = f'{doc.__module__}.{doc.doctype}.{method}'
	if not doc.has_permission("read"):
		frappe.throw("Not permitted", frappe.PermissionError)

	if doc:
		frappe.response['message'] = getattr(doc, method)()

		frappe.response.docs.append(doc)

run_method.runserverobj = runserverobj
