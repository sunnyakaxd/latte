import frappe
import frappe.defaults
from latte.utils.caching import cache_in_mem

old_get_defaults = frappe.defaults.get_defaults

get_defaults = cache_in_mem(key=lambda user:user, timeout=10)(old_get_defaults)

def cached_get_defaults(user=None):
    user = user or (frappe.session.user if frappe.session else "Guest")
    return get_defaults(user)

frappe.defaults.get_defaults = cached_get_defaults
