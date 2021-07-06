from frappe import permissions, _dict
from frappe.permissions import rights

def allow_everything():
	'''
	returns a dict with access to everything
	eg. {"read": 1, "write": 1, ...}
	'''
	perm = _dict({ptype: 1 for ptype in rights})
	return perm

permissions.allow_everything = allow_everything