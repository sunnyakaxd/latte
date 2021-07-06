import frappe
from frappe.www.printview import get_html_and_style, string_types

@frappe.whitelist()
def patched_get_html_and_style(doc, name=None, print_format=None, meta=None,
	no_letterhead=None, trigger_print=False, style=None, lang=None):
	frappe.local.flags.log_identity = print_format
	return get_html_and_style(
		doc=doc,
		name=name,
		print_format=print_format,
		meta=meta,
		no_letterhead=no_letterhead,
		trigger_print=trigger_print,
		style=style,
		lang=lang,
	)