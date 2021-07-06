import frappe
# from frappe.core.doctype.data_import.importer import upload
from .importer import upload

@frappe.whitelist()
def import_data(data_import, only_validate=False):
	frappe.db.set_value("Data Import", data_import, "import_status", "In Progress", update_modified=False)
	frappe.publish_realtime("data_import_progress", {"progress": "0",
		"data_import": data_import, "reload": True}, user=frappe.session.user)

	from frappe.core.page.background_jobs.background_jobs import get_info
	enqueued_jobs = [d.get("job_name") for d in get_info()]

	if data_import not in enqueued_jobs:
		frappe.utils.background_jobs.enqueue(
			upload,
			queue='default',
			timeout=6000,
			event='data_import',
			job_name=data_import,
			data_import_doc=data_import,
			from_data_import="Yes",
			user=frappe.session.user,
			only_validate=only_validate
		)
	frappe.msgprint('''
		Import enqueued. Kindly
		<strong><a href="javascript:cur_frm.reload_doc()">reload</a></strong>
		page to see progress
	''')

# frappe.core.doctype.data_import.importer.upload = upload
frappe.core.doctype.data_import.data_import.import_data = import_data


