import frappe
import os, json
from frappe.modules.export_file import export_to_files as _export_to_files
from frappe.modules.import_file import import_file_by_path

def export_to_files(doc):
	if (
		doc.is_standard
		and doc.module
		and frappe.local.conf.developer_mode
		and (not frappe.flags.in_migrate)
	):
		_export_to_files(
			record_list=[[doc.doctype, doc.name]],
			record_module=doc.module,
			create_init=True,
		)

def sync_standard_documents():
	'''
	Writes on DB from JSON files created for standard documents

	Searches for the standard doctype across all modules. If found, gets the JSON file from that path
	and imports it.
	'''
	standard_docs = frappe.get_hooks('standard_doctypes')
	my_apps = frappe.get_installed_apps()
	my_app_modules = []
	for app in my_apps:
		if app not in ["frappe", "erpnext"]:
			modules = frappe.local.app_modules.get(app) or []
			my_app_modules.extend(modules)

	for doc in standard_docs:
		for module in my_app_modules:
			module_path = frappe.get_module_path(frappe.unscrub(module))
			folder_path = f"{module_path}/{frappe.scrub(doc)}"
			if os.path.exists(folder_path):
				try:
					sync_doc(folder_path)
				except:
					print(frappe.get_traceback())

def sync_doc(folder_path):
	'''
	Helper function that does the meat of syncing standard documents.
	Called from sync_standard_documents
	'''
	print('Syncing', folder_path)
	dirs = os.listdir(folder_path)
	for directory in dirs:
		json_path = f'{folder_path}/{directory}/{directory}.json'
		try:
			if os.path.isfile(json_path):
				with open(json_path) as f:
					doc_data = json.load(f)
					dt = doc_data['doctype']
					dn = doc_data['name']
				# print(f'Syncing standard document for doctype {dt}: {dn}')
				import_file_by_path(json_path)
			frappe.db.commit()
		except:
			print('Import failed for', json_path)
			print(frappe.get_traceback())
			frappe.db.rollback()