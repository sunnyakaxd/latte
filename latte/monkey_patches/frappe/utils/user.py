
import frappe
from frappe.utils.user import UserPermissions, get_valid_perms
from latte.utils.caching import cache_me_if_you_can, cache_in_mem
from frappe import local

def build_doctype_map(self):
	"""build map of special doctype properties"""
	self.doctype_map = get_doctype_map()

@cache_in_mem(lock_cache=True)
@cache_me_if_you_can(key=lambda: ('', 36000))
def get_doctype_map():
	doctype_map = {}
	active_domains = frappe.get_active_domains()
	for r in frappe.db.sql("""select name, in_create, issingle, istable,
		read_only, restrict_to_domain, module from tabDocType""", as_dict=1):
		if (not r.restrict_to_domain) or (r.restrict_to_domain in active_domains):
			doctype_map[r['name']] = r

	return doctype_map

UserPermissions.build_doctype_map = build_doctype_map

def build_perm_map(self):
	"""build map of permissions at level 0"""
	self.perm_map = get_perm_map()

@cache_me_if_you_can(key=lambda: (f'{local.session.user}|{local.session.sid}', 3600), invalidate='permissions')
def get_perm_map():
	perm_map = {}
	for r in get_valid_perms():
		dt = r['parent']

		if not dt in perm_map:
			perm_map[dt] = {}

		for k in frappe.permissions.rights:
			if not perm_map[dt].get(k):
				perm_map[dt][k] = r.get(k)

	return perm_map

UserPermissions.build_perm_map = build_perm_map