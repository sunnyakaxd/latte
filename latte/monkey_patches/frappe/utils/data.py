import frappe.utils
import frappe.utils.data
from latte.utils.caching import cache_in_mem

operator_map = {
	# startswith
	"^": lambda a, b: (a or "").startswith(b),

	# in or not in a list
	"in": lambda a, b: a in b,
	"not in": lambda a, b: a not in b,

	# comparison operators
	"=": lambda a, b: a == b,
	"!=": lambda a, b: a != b,
	">": lambda a, b: a > b,
	"<": lambda a, b: a < b,
	">=": lambda a, b: a >= b,
	"<=": lambda a, b: a <= b,
	"not None": lambda a, b: not not a,
	"None": lambda a, b: not a
}

frappe.utils.data.get_time_zone = cache_in_mem()(frappe.utils.data.get_time_zone)

frappe.utils.href = lambda dt, dn: f'{dt} <strong><a href="/desk#Form/{dt}/{dn}">{dn}</a></strong>'
frappe.utils.operator_map = frappe.utils.data.operator_map = operator_map