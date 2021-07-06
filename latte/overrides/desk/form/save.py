import frappe
from latte.json import loads
from frappe.desk.form.save import run_onload, send_updated_docs, set_local_name
from latte.business_process.powerflow.powerflow import get_powerflow_meta
from latte.business_process.powerflow_exceptions import AutoExecutionHaltPowerflowException

@frappe.whitelist()
def savedocs(doc, action):
	"""save / submit / update doclist"""
	try:
		doc_dic = doc
		if isinstance(doc, str):
			doc = loads(doc)
		doc = frappe.get_doc(doc)
		set_local_name(doc)

		# action
		doc.docstatus = {"Save":0, "Submit": 1, "Update": 1, "Cancel": 2}[action]

		if doc.docstatus==1:
			try:
				doc.submit()
			except AutoExecutionHaltPowerflowException as e:
				frappe.db.rollback()
				save_powerflow_docs(e)
				doc = frappe.get_doc(loads(doc_dic))
				set_local_name(doc)
		else:
			try:
				doc.save()
			except frappe.NameError as e:
				doctype, name, original_exception = e if isinstance(e, tuple) else (doc.doctype or "", doc.name or "", None)
				frappe.msgprint(frappe._("{0} {1} already exists").format(doctype, name))
				raise

		# update recent documents
		run_onload(doc)
		doc.__onload['__powerflow_meta'] = get_powerflow_meta(doc)
		frappe.get_user().update_recent(doc.doctype, doc.name)
		send_updated_docs(doc)
	except Exception:
		if not frappe.local.message_log:
			frappe.msgprint(frappe._('Did not save'))
		frappe.errprint(frappe.utils.get_traceback())
		raise

def save_powerflow_docs(exception_obj):
	exception_obj.powerflow.save(ignore_permissions = True)