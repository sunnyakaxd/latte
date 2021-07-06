import frappe

@frappe.whitelist()
def load():
	if not "System Manager" in frappe.get_roles():
		frappe.throw("Not permitted", frappe.PermissionError)

	return {
		"timezones": ['Asia/Kolkata'],
		"defaults": {}
	}
