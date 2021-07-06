import json
import frappe



"""API Count method rewitten for Mobile app, 
please do not change as it is used to show counts in mobile app"""
@frappe.whitelist()
def get_count(doctype, filters=None, debug=0, cache=False):
	if filters and isinstance(filters, str):
		filters = json.loads(filters)

	return frappe.db.count(doctype, filters, debug, cache)