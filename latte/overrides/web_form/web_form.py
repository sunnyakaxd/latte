import frappe


@frappe.whitelist(allow_guest=True)
def get_form_data(doctype, docname=None, web_form_name=None):
	out = frappe._dict()

	login_required = frappe.db.get_value('Web Form', web_form_name, 'login_required')
	if docname:
		doc = frappe.get_doc(doctype, docname)
		# if has_web_form_permission(doctype, docname, ptype='read'):
		if not login_required:
			out.doc = doc
		else:
			frappe.throw(_("Not permitted"), frappe.PermissionError)

	out.web_form = frappe.get_doc('Web Form', web_form_name)

	# For Table fields, server-side processing for meta
	for field in out.web_form.web_form_fields:
		if field.fieldtype == "Table":
			field.fields = get_in_list_view_fields(field.options)
			out.update({field.fieldname: field.fields})

		if field.fieldtype == "Link":
			field.fieldtype = "Autocomplete"
			field.options = get_link_options(
				web_form_name,
				field.options,
				field.allow_read_on_all_link_options
			)

	return out