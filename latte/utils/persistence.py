import frappe
from frappe import local

def persist():
	persistence = frappe.get_hooks('persistence')
	print(persistence)
	if not persistence:
		return

	local.db.sql('''
		create table if not exists __tab_persistence (
			ref_doctype varchar(140),
			fieldname varchar(140),
			ref_name varchar(140),
			value text,
			constraint primary_key primary key (ref_doctype, fieldname, ref_name)
		)
	''')

	for dt, fields in persistence.items():
		if not local.db.table_exists(dt):
			continue
		table_columns = local.db.get_db_table_columns(f'tab{dt}')
		fields = [field for field in fields if field in table_columns]
		for field in fields:
			local.db.sql(f'''
				insert into __tab_persistence
				(ref_doctype, fieldname, ref_name, value)
				select
					"{dt}" as ref_doctype,
					"{field}" as field,
					dt.name,
					`{field}` as stored_value
				from
					`tab{dt}` dt
				on duplicate key update
					ref_name = dt.name
			''')
		local.db.commit()

def restore():
	doctypes = local.db.sql('select ref_doctype, fieldname from __tab_persistence group by ref_doctype, fieldname')
	for doctype, fieldname in doctypes:
		local.db.sql(f'''
			update
				__tab_persistence p
			join
				`tab{doctype}` dt
			on
				dt.name = p.ref_name
				and p.ref_doctype = "{doctype}"
				and p.fieldname = "{fieldname}"
			set
				dt.`{fieldname}` = p.value
		''')

	local.db.sql('drop table __tab_persistence')
