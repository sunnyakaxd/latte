from frappe.core.doctype.user.user import User
import frappe.core.doctype.user.user

# Sometimes, it's better to do nothing instead of
# trying to do something cool which rarely has
# practical benefits
def nothing(*args, **kwargs):
	pass

frappe.core.doctype.user.user.ask_pass_update = nothing
User.before_insert = nothing