import frappe

AUTO_INCREMENT_META = 'auto_increment'
OLD_NAME = '__old_name_auto_incr_'

class MigrateException(Exception):
	pass

def set_autoname(dt_name, type):
	print('Moving', dt_name, 'to', type)
	from latte.utils.caching import invalidate
	frappe.db.set_value('DocType', dt_name, 'autoname', type)
	frappe.get_meta(dt_name).autoname = type
	invalidate(f'meta|{dt_name}')

def move_non_auto_to_hash():
	if not frappe.local.conf.developer_mode:
		return

	from latte.utils.caching import invalidate
	from pymysql.err import ProgrammingError
	for dt in frappe.get_all('DocType', filters={
		'issingle': 0,
	}, fields=['name', 'autoname']):
		try:
			if dt.autoname == AUTO_INCREMENT_META and (not is_table_autoincr(dt.name)):
				set_autoname(dt.name, 'hash')
			elif is_table_autoincr(dt.name) and dt.autoname != AUTO_INCREMENT_META:
				set_autoname(dt.name, AUTO_INCREMENT_META)
		except ProgrammingError as e:
			if e.args[0] != 1146:
				raise
	frappe.db.commit()

def migrate_doc(doc, _=None):
	from latte.utils.caching import invalidate
	if doc.autoname == AUTO_INCREMENT_META:
		migrate(doc.name)
		invalidate(f'meta|{doc.name}')
		frappe.get_meta(doc.name).autoname = AUTO_INCREMENT_META

def migrate(dt):
	try:
		migrate_table(dt)
	except MigrateException:
		set_autoname(dt, 'hash')
		return

	if frappe.db.get_value('DocType', dt, 'autoname') != AUTO_INCREMENT_META:
		print('Setting', dt, AUTO_INCREMENT_META)
		frappe.db.set_value('DocType', dt, 'autoname', AUTO_INCREMENT_META)
	else:
		print('Meta Already', dt, AUTO_INCREMENT_META)

	frappe.db.commit()

def is_table_autoincr(dt):
	name = [row for row in frappe.db.sql(f'desc `tab{dt}`', as_dict=1) if row.Field == 'name'][0]
	return AUTO_INCREMENT_META in name.Extra

def migrate_table(dt, rename=False):
	from latte.utils.indexing import create_index
	from latte.database_utils.connection_pool import PatchedDatabase
	if root_pwd := frappe.local.conf.root_password:
		frappe.local.db.close()
		root_db = PatchedDatabase(user='root', password=root_pwd)
		frappe.local.db = root_db
	else:
		print('Migration to auto increment failed')
		print(f'Kindly add "root_password" in site config to convert {dt} to auto_increment')
		raise MigrateException()

	frappe.local.db.close()
	frappe.local.db = root_db

	name = [row for row in frappe.db.sql(f'desc `tab{dt}`', as_dict=1) if row.Field == 'name'][0]
	if is_table_autoincr(dt):
		print(dt, 'already set as auto_increment in db')
		return

	print(f'Altering table {dt}')
	bkp_tab = f'__auto_incr_backup_tab{dt}'
	print('Creating', bkp_tab)
	frappe.db.sql(f'create or replace table `{bkp_tab}` like `tab{dt}`')
	print('Altering', bkp_tab)
	frappe.db.sql(f'''
		alter table `{bkp_tab}`
			drop primary key,
			modify name serial primary key,
			add column IF NOT EXISTS {OLD_NAME} varchar(140)
	''')
	create_index(bkp_tab, OLD_NAME, unique=True)
	print('Copying data from', dt, 'to', bkp_tab)
	columns = [row.Field for row in frappe.db.sql(f'desc `tab{dt}`', as_dict=True) if 'generated' not in (row.Extra or '').lower()]
	for col in ('name', OLD_NAME):
		if col in columns:
			columns.remove(col)

	frappe.db.sql(f'''
		LOCK TABLE
			`tab{dt}`
		WRITE
	''')
	triggers = set_triggers(dt, bkp_tab, columns)
	max_modified = frappe.db.sql(f'select modified from `tab{dt}` order by modified desc limit 1')
	frappe.db.sql('unlock tables')
	if max_modified:
		transfer_data(dt, bkp_tab, columns, max_modified[0][0])
	for trigger in triggers:
		frappe.db.sql(f'drop trigger `{trigger}`')

	old_tab = f'__auto_incr_old_tab{dt}'
	print('Renaming', dt, 'to', old_tab)
	# frappe.db.sql(f'drop table if exists `{old_tab}`')
	# frappe.throw('Done')
	frappe.db.sql(f'rename table `tab{dt}` to `{old_tab}`')
	print('Renaming', bkp_tab, 'to', f'tab{dt}')
	frappe.db.sql(f'rename table `{bkp_tab}` to `tab{dt}`')
	print(f'Finished {dt}')

def transfer_data(dt, bkp_tab, columns, max_modified):
	from frappe.utils import get_datetime_str, add_to_date
	min_modified = frappe.db.sql(f'select modified from `tab{dt}` order by modified limit 1')[0][0]

	data_copy_query = f'''
		insert into `{bkp_tab}`
			({', '.join(["__old_name_auto_incr_"] + [f"`{column}`" for column in columns])})
		select
			{', '.join(["name as __old_name_auto_incr_"] + [f"`{column}`" for column in columns])}
		from
			`tab{dt}`
		where
			modified between %(from)s and %(upto)s
	'''

	from_mod = min_modified
	inserts = 0
	while (upto_mod := get_datetime_str(add_to_date(from_mod, days=1))) < get_datetime_str(max_modified):
		print('Copying from', from_mod, 'to', upto_mod)
		new_inserts = frappe.db.execute(data_copy_query, {
			'from': from_mod,
			'upto': upto_mod,
		})
		inserts += new_inserts
		print(new_inserts, '/', inserts, 'rows inserted')

		frappe.db.commit()
		from_mod = upto_mod

	inserts += frappe.db.execute(data_copy_query, {
		'from': from_mod,
		'upto': max_modified,
	},)
	print('Total', inserts, 'rows inserted')
	frappe.db.commit()
	print('Copied upto', max_modified)

def cache():
	frappe.db.sql('''
		create table if not exists `___auto_incr_doctypes`
		select name from `tabDocType`
		where autoname = 'auto_increment'
	''')
	frappe.db.commit()

def reset():
	frappe.db.sql('''
		update
			`tabDocType` dt
		join
			`___auto_incr_doctypes` auto_inc
		on
			auto_inc.name = dt.name
		set
			dt.autoname = 'auto_increment'
	''')
	frappe.db.commit()
	frappe.db.sql('drop table ___auto_incr_doctypes')

	from redis.connection import ConnectionError
	try:
		frappe.cache().flushall()
	except ConnectionError:
		pass

def set_triggers(dt, tab, cols):
	newline = '\n'

	frappe.local.db.sql(f'''
		create or replace trigger `{tab}_ins`
		AFTER INSERT ON `tab{dt}`
		FOR EACH ROW
		BEGIN
			insert into `{tab}`(
				`{f'`,{newline}`'.join(cols + [OLD_NAME])}`
			) values (
				{f',{newline}'.join([f'NEW.`{col}`' for col in cols] + ['name'])}
			);
		END
	''', debug=1)

	frappe.local.db.sql(f'''
		create or replace trigger `{tab}_del`
		AFTER DELETE ON `tab{dt}`
		FOR EACH ROW
		BEGIN
			delete from `{tab}`
			where `{tab}`.`{OLD_NAME}` = OLD.name;
		END
	''', debug=1)

	frappe.local.db.sql(f'''
		create or replace trigger `{tab}_upd`
		AFTER UPDATE ON `tab{dt}`
		FOR EACH ROW
		BEGIN
			update
				`{tab}`
			set
				{
					f',{newline}'.join(f'`{tab}`.`{col}` = NEW.`{col}`' for col in cols)
				}
			where
				`{tab}`.`{OLD_NAME}` = NEW.name;
		END
	''', debug=1)

	return [
		f'{tab}_ins',
		f'{tab}_del',
		f'{tab}_upd',
	]