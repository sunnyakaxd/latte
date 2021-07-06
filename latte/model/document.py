import frappe
from latte.utils.caching import cache_in_mem
from frappe.model.document import Document
from frappe.modules import get_module_app

core_doctypes_list = {'DocType', 'DocField', 'DocPerm', 'User', 'Role', 'Has Role',
	'Page', 'Module Def', 'Print Format', 'Report', 'Customize Form',
	'Customize Form Field', 'Property Setter', 'Custom Field', 'Custom Script'}

@cache_in_mem(key=lambda dt,m=None:dt, lock_cache=True)
def get_controller(doctype, module=None):
	module, custom = frappe.db.get_value(
		"DocType",
		doctype,
		("module", "custom")
	) or [module or "Core", False]
	if custom:
		return Document

	app = get_module_app(module)

	scrubbed_dt = frappe.scrub(doctype)
	classname = doctype.replace(" ", "").replace("-", "")
	attr_name = f'{frappe.scrub(app)}.{frappe.scrub(module)}.doctype.{scrubbed_dt}.{scrubbed_dt}.{classname}'
	if doctype not in core_doctypes_list:
		extended_classes = frappe.get_hooks('doctype_class_extensions')
		extended_class = extended_classes and extended_classes.get(attr_name)
		if extended_class:
			attr_name = extended_class[0]

	return frappe.get_attr(attr_name)