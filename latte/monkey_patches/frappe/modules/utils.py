
import frappe, os
from frappe.modules import utils
from latte.latte_core.doctype.permission.permission import Permission

def sync_customizations_for_doctype(data, folder):
	'''Sync doctype customzations for a particular data set'''
	from frappe.core.doctype.doctype.doctype import validate_fields_for_doctype

	doctype = data['doctype']
	update_schema = False

	def sync(key, custom_doctype, doctype_fieldname, doctype_name=None):
		doctypes = list(set(map(lambda row: row.get(doctype_fieldname), data[key])))

		def sync_single_doctype(doc_type):
			frappe.db.sql('delete from `tab{0}` where `{1}` =%s'.format(
				custom_doctype, doctype_name if doctype_name else doctype_fieldname), doc_type)
			for d in data[key]:
				if d.get(doctype_fieldname) == doc_type:
					d['doctype'] = custom_doctype
					if doctype_name:
						d['doc_type'] = doc_type
					doc = frappe.get_doc(d)
					doc.db_insert()

		for doc_type in doctypes:
			if doc_type == doctype or not os.path.exists(os.path.join(folder, frappe.scrub(doc_type)+".json")):
				sync_single_doctype(doc_type)

	if data['custom_fields']:
		sync('custom_fields', 'Custom Field', 'dt')
		update_schema = True

	if data['property_setters']:
		sync('property_setters', 'Property Setter', 'doc_type')

	if data.get('custom_perms') and (not frappe.conf.use_permission_for_access):
		sync('custom_perms', 'Custom DocPerm', 'parent')

	print('Updating customizations for {0}'.format(doctype))
	validate_fields_for_doctype(doctype)

	if update_schema and not frappe.db.get_value('DocType', doctype, 'issingle'):
		from frappe.model.db_schema import updatedb
		updatedb(doctype)

utils.sync_customizations_for_doctype = sync_customizations_for_doctype