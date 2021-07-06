from __future__ import unicode_literals
import frappe
from frappe.desk.search import (
	build_for_autosuggest,
	search_widget
)
import latte
from latte.latte_core.naming.auto_increment import AUTO_INCREMENT_META

@frappe.whitelist()
@latte.read_only(key=lambda *_,**__: 3600)
def search_link(doctype, txt, query=None, filters=None, page_length=20, searchfield=None, reference_doctype=None, ignore_user_permissions=False):
	if frappe.get_meta(doctype).autoname == AUTO_INCREMENT_META:
		frappe.response['results'] = []
		return

	ordered_search_widget(
		doctype,
		txt,
		query,
		searchfield=searchfield,
		page_length=page_length,
		filters=filters,
		reference_doctype=reference_doctype,
		ignore_user_permissions=ignore_user_permissions
	)

	frappe.response['results'] = build_for_autosuggest(frappe.response["values"])
	del frappe.response["values"]

@frappe.whitelist()
def ordered_search_widget(doctype, txt, query=None, searchfield=None, start=0,
	page_length=10, filters=None, filter_fields=None, as_dict=False, reference_doctype=None, ignore_user_permissions=False):

	search_widget(
		doctype,
		txt,
		query,
		searchfield=searchfield,
		page_length=page_length,
		filters=filters,
		as_dict=as_dict,
		reference_doctype=reference_doctype,
		ignore_user_permissions=ignore_user_permissions
	)

	if as_dict:
		return
	# Ordering results
	frappe.response["values"] = sorted(frappe.response["values"], key=lambda x: len(x[0]))
