
import frappe
from frappe.core.page.permission_manager import permission_manager
from frappe.core.page.permission_manager.permission_manager import update_permission_property
from latte.latte_core.doctype.permission.permission import Permission

@frappe.whitelist()
def update(doctype, role, permlevel, ptype, value=None):
	frappe.only_for("System Manager")
	if not frappe.conf.use_permission_for_access:
		update_permission_property(doctype, role, permlevel, ptype, value)
	Permission.update_permission(doctype, role, permlevel, ptype, value)
	return 'refresh'

permission_manager.update = update