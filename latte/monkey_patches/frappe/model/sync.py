import frappe
from frappe.model import sync
from frappe.model.sync import get_doc_files, import_file_by_path, update_progress_bar, os

def sync_for(app_name, force=0, sync_everything = False, verbose=False, reset_permissions=False):
	files = []

	frappe.local.flags.in_install_app = 1

	if app_name == "frappe":
		# these need to go first at time of install
		for d in (("core", "docfield"),
			("core", "docperm"),
			("core", "has_role"),
			("core", "doctype"),
			("core", "user"),
			("core", "role"),
			("custom", "custom_field"),
			("custom", "property_setter"),
			("website", "web_form"),
			("website", "web_form_field"),
			("website", "portal_menu_item"),
			("data_migration", "data_migration_mapping_detail"),
			("data_migration", "data_migration_mapping"),
			("data_migration", "data_migration_plan_mapping"),
			("data_migration", "data_migration_plan")):
			files.append(os.path.join(frappe.get_app_path("frappe"), d[0],
				"doctype", d[1], d[1] + ".json"))

	for module_name in frappe.local.app_modules.get(app_name) or []:
		folder = os.path.dirname(frappe.get_module(app_name + "." + module_name).__file__)
		get_doc_files(files, folder, force, sync_everything, verbose=verbose)

	l = len(files)
	if l:
		for i, doc_path in enumerate(files):
			import_file_by_path(doc_path, force=force, ignore_version=True,
				reset_permissions=reset_permissions, for_sync=True)
			#print module_name + ' | ' + doctype + ' | ' + name

			frappe.db.commit()

			# show progress bar
			update_progress_bar("Updating DocTypes for {0}".format(app_name), i, l)

		# print each progress bar on new line
		print()

sync.sync_for = sync_for