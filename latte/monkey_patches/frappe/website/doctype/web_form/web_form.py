import frappe
from frappe.utils.file_manager import get_max_file_size

from frappe.website.doctype.web_form.web_form import WebForm

def has_web_form_permission_override(doctype, name, ptype='read'):
	if frappe.session.user=="Guest":
		return False

	# owner matches
	elif frappe.db.get_value(doctype, name, "owner")==frappe.session.user:
		return True

	elif frappe.has_website_permission(name, ptype=ptype, doctype=doctype):
		return True

	elif check_webform_perm(doctype, name):
		return True

	else:
		return False

def make_route_string(parameters):
	route_string = ""
	delimeter = '?'
	if isinstance(parameters, dict):
		for key in parameters:
			if key != "web_form_name":
				route_string += route_string + delimeter + key + "=" + cstr(parameters[key])
				delimeter = '&'
	return (route_string, delimeter)


def get_context(self, context):
    '''Patched Build context to render the `web_form.html` template'''
    self.set_web_form_module()

    context._login_required = False
    if self.login_required and frappe.session.user == "Guest":
        context._login_required = True

    doc, delimeter = make_route_string(frappe.form_dict)
    context.doc = doc
    context.delimeter = delimeter

    # patched check permissions
    if frappe.session.user == "Guest" and frappe.form_dict.name and self.login_required:
        frappe.throw(_("You need to be logged in to access this {0}.").format(self.doc_type), frappe.PermissionError)

    if self.login_required and frappe.form_dict.name and not has_web_form_permission_override(self.doc_type, frappe.form_dict.name):
        frappe.throw(_("You don't have the permissions to access this document"), frappe.PermissionError)

    self.reset_field_parent()

    if self.is_standard:
        self.use_meta_fields()

    if not context._login_required:
        if self.allow_edit:
            if self.allow_multiple:
                if not frappe.form_dict.name and not frappe.form_dict.new:
                    self.build_as_list(context)
            else:
                if frappe.session.user != 'Guest' and not frappe.form_dict.name:
                    frappe.form_dict.name = frappe.db.get_value(self.doc_type, {"owner": frappe.session.user}, "name")

                if not frappe.form_dict.name:
                    # only a single doc allowed and no existing doc, hence new
                    frappe.form_dict.new = 1

    # always render new form if login is not required or doesn't allow editing existing ones
    if not self.login_required or not self.allow_edit:
        frappe.form_dict.new = 1

    self.load_document(context)
    context.parents = self.get_parents(context)

    if self.breadcrumbs:
        context.parents = frappe.safe_eval(self.breadcrumbs, { "_": _ })

    context.has_header = ((frappe.form_dict.name or frappe.form_dict.new)
        and (frappe.session.user!="Guest" or not self.login_required))

    if context.success_message:
        context.success_message = frappe.db.escape(context.success_message.replace("\n",
            "<br>"))

    self.add_custom_context_and_script(context)
    if not context.max_attachment_size:
        context.max_attachment_size = get_max_file_size() / 1024 / 1024

    context.show_in_grid = self.show_in_grid
    hasattr(self, 'load_translations') and self.load_translations(context)


WebForm.get_context = get_context

