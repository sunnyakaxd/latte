
from __future__ import unicode_literals
from os import sync
import frappe
from latte.utils.indexing import create_index
from frappe.modules.utils import sync_customizations

@frappe.whitelist()
def execute():
	print('Altering File table')
	frappe.reload_doctype('File', True)
	sync_customizations('latte')
	print('Indexing Adapter ID')
	create_index('tabFile', 'adapter_id(1)')
	total_updated = 0
	while updated := frappe.db.execute('''
		update
			tabFile
		set
			adapter_type =  'File',
			adapter_id = if(
				is_private=1,
				concat('private/files/', substring_index(file_url, '/', -1)),
				concat('public/files/', substring_index(file_url, '/', -1))
			),
			file_url = concat('/', substring_index(file_url, '/', -2))
		where
			adapter_type = ''
			and (
				adapter_id = ''
				or adapter_id is null
			)
			and is_folder = 0
		limit 5000
	''', {}):
		total_updated += updated
		print(f'Updated {total_updated} files')
		frappe.db.commit()

	frappe.db.sql('alter table `tabFile` drop index index_on_adapter_id')
