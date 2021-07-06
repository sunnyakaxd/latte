import frappe
from pymysql import InternalError
from frappe.model.dynamic_links import get_dynamic_links
from frappe.model.rename_doc import get_link_fields

def create_index(table, columns, unique=False):
	column_dict = {}
	if isinstance(columns, str):
		columns = [columns]
	for i, column_name in enumerate(columns[:]):
		length = None
		try:
			column_name, length = column_name.split('(')
			column_dict[column_name] = length[:-1]
			columns[i] = column_name
		except ValueError:
			pass

	already_indexed = frappe.db.sql('''
		SELECT
			group_concat(distinct column_name order by seq_in_index) seq_idx
		from
			information_schema.statistics
		where
			table_name = %(table_name)s
			and non_unique = %(non_unique)s
			and seq_in_index <= %(total_keys)s
			and table_schema = %(table_schema)s
		group by
			index_name
		having seq_idx = %(seq_idx)s
	''', {
		'table_schema': frappe.db.db_name,
		'non_unique': int(not unique),
		'table_name': table,
		'seq_idx': ','.join(columns),
		'total_keys': len(columns),
	})

	if already_indexed:
		return

	column_names = f'''"{'","'.join(columns)}"'''
	try:
		try:
			column_def = ', '.join([
				f"`{column_name}`{('(' + column_dict[column_name] + ')') if column_name in column_dict else ''}"
				for column_name in columns
			])
			frappe.db.commit()
			index_name = f"{'unique_' if unique else ''}index_on_{'_'.join(columns)}"[:64]
			frappe.db.sql(f'''
				CREATE
					{'unique' if unique else ''}
					index
					{index_name}
				on
					`{table}`({column_def})
			''')
			print(f'''Indexed {column_names} columns for table {table}, UNIQUE={unique}''')
			return True
		except InternalError as e:
			print(e)
			if int(e.args[0]) == 1061: #Handle duplicate index error
				pass
			elif int(e.args[0]) == 1170:
				print(f'''Error while creating index on table {table} column {column_names}''')
				print('=>', e)
				print('You should not create keys on columns which are text/blob.')
			else:
				raise
	except Exception as e:
		print(f'Error while creating index on table {table} column {column_names}')
		print('=>', e)

def index_all():
	frappe.db.commit()
	# modified_and_owner()
	field_name()
	lft_rgt_index()
	# index_dynamic_links()
	# index_links()
	index_default_tables()
	index_after_migrate()
	remove_parent_from_non_tables()

def remove_parent_from_non_tables():
	crucials = {
		'Custom DocPerm',
		'Job Run'
	}
	non_tables = {row.name for row in frappe.get_all('DocType', {
		'istable': 0,
	})} - crucials

	non_tables_used_as_tables = frappe.db.sql('''
		select
			parent, fieldname, options
		from
			`tabDocField`
		where
			options in %(non_tables)s
			and fieldtype = 'Table'
		union

		select
			dt, fieldname, options
		from
			`tabCustom Field`
		where
			options in %(non_tables)s
			and fieldtype = 'Table'
	''', {
		'non_tables': list(non_tables),
	})

	if non_tables_used_as_tables:
		print('Non tables used as tables', non_tables_used_as_tables)
		non_tables = non_tables - {row[2] for row in non_tables_used_as_tables}

	present_tables_with_parent_index = frappe.db.sql('''
		select
			distinct
			tabs.table_name, stats.index_name
		from
			information_schema.tables tabs
		join
			information_schema.statistics stats
		on
			stats.table_name = tabs.table_name
			and stats.table_schema = tabs.table_schema
		where
			stats.table_schema = %(db_name)s
			and stats.seq_in_index = 1
			and stats.column_name = 'parent'
			and tabs.table_name in %(non_tables)s
			and not exists (
				select 1
				from
					information_schema.statistics istats
				where
					istats.table_schema = %(db_name)s
					and istats.table_name = stats.table_name
					and istats.index_name = stats.index_name
					and istats.seq_in_index != 1
			)
	''', {
		'non_tables': [f'tab{dt}' for dt in non_tables],
		'db_name': frappe.db.db_name,
	})

	for table, index in present_tables_with_parent_index:
		frappe.db.sql(f'''
			alter table `{frappe.db.escape(table)}`
			drop index {frappe.db.escape(index)}
		''')
		print('Dropped index', index, 'from table', table)

def index_after_migrate():
	for hook in frappe.get_hooks('index_after_migrate'):
		indices = frappe.get_attr(hook)
		for index_meta in indices:
			create_index(*index_meta)

def index_default_tables():
	create_index('__UserSettings', ['doctype'])
	create_index('tabCustom DocPerm', ['parent', 'role', 'permlevel', 'if_owner'], unique=True)
	create_index('tabContact', 'mobile_no')
	create_index('tabContact', 'user')
	create_index('tabDeleted Document', ['deleted_doctype', 'deleted_name'])
	create_index('tabDesktop Icon', 'standard')
	create_index('tabDocShare', ['everyone', 'share_doctype'])
	create_index('tabDocShare', ['user', 'share_doctype', 'share_name'])
	create_index('tabDocType', 'istable')
	create_index('tabDocType', 'allow_import')
	create_index('tabDocType', 'issingle')
	create_index('tabEmail Queue', ['reference_doctype', 'reference_name'])
	create_index('tabError Log', 'method')
	create_index('tabError Snapshot', 'timestamp')
	create_index('tabFile', 'file_url(200)')
	create_index('tabFile', 'file_name')
	create_index('tabFile', 'is_attachments_folder')
	create_index('tabFile', 'is_home_folder')
	create_index('tabFile', ['adapter_type', 'adapter_id(200)'])
	create_index('tabFile', ['content_hash', 'file_size', 'does_not_exist'])
	create_index('tabSeries', ['name'], unique = True)
	create_index('tabSingles', ['doctype', 'field'], unique = True)
	create_index('tabSMS Log', ['for_doctype', 'for_docname'])
	create_index('tabUser', ['user_type', 'enabled'])
	create_index('tabUser Permission', ['user', 'apply_to_all_doctypes', 'applicable_for'])
	create_index('tabUser Permission', ['user', 'applicable_for', 'allow'])
	create_index('tabVersion', ['ref_doctype', 'docname'])


def modified_and_owner():
	tables_to_update = frappe.db.sql_list(f'''
		SELECT
			cols.table_name
		from
			information_schema.columns cols
		join
			information_schema.tables tabs
		on
			tabs.table_name = cols.table_name
			and tabs.table_schema = cols.table_schema
		where
			cols.column_name = "modified"
			and tabs.table_type = "BASE TABLE"
			and tabs.table_schema = "{frappe.conf.db_name}";
	''')
	for table_name in tables_to_update:
		create_index(table_name, 'modified')
		create_index(table_name, 'owner')
		create_index(table_name, 'modified_by')

def field_name(destroy_first=False):
	doctypes_to_index = frappe.db.sql('''
		SELECT
			name,
			autoname
		from
			`tabDocType`
		where
			(issingle = 0 or issingle is null or issingle = "")
			and (istable = 0 or istable is null or istable = "")
			and autoname like "field:%%"
			and name not in (
				"Warehouse",
				"Sales Taxes and Charges Template",
				"Purchase Taxes and Charges Template",
				"Account",
				"Cost Center",
				"Department"
			)
	''')
	for dt, field in doctypes_to_index:
		field = field.split(':')[-1]
		if field:
			try:
				if destroy_first:
					frappe.db.sql('''
						ALTER table
							`tab{dt}`
						drop index index_on_{field}
					'''.format(dt=dt, field=field))
				create_index('tab{dt}'.format(dt=dt), field)
			except Exception as e:
				print('Error while creating field index',dt, field, e)

def lft_rgt_index():
	for table in frappe.db.sql_list('''
		SELECT
			table_name
		from
			information_schema.tables
		where
			table_name in ("tabCustomer Group", "tabTerritory", "tabItem Group", "tabWarehouse")
	'''):
		create_index(table, 'lft')
		create_index(table, 'rgt')

def index_dynamic_links():
	links = get_dynamic_links()
	links.sort(key=lambda x:x.get('parent'))
	for link in links:
		if frappe.get_meta(link.get('parent')).issingle:
			continue
		try:
			frappe.db.sql(f'''
				ALTER table
					`tab{link.get('parent')}`
				drop index
					index_on_{link.get('options')}
			''')
		except:
			pass
		else:
			print(f'Dropped index index_on_{link.get("options")}')
		create_index('tab' + link.get('parent'), [link.get('options'), link.get('fieldname')])

def index_links():
	links = ([
		link
			for dt in frappe.get_all('DocType')
			for link in get_link_fields(dt.name)
	])
	links.sort(key=lambda x:x.get('parent'))
	for link in links:
		if link.get('issingle'):
			continue
		create_index('tab' + link.get('parent'), link.get('fieldname'))
