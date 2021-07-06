import frappe
from latte.database_utils.connection_pool import PatchedDatabase
from pymysql.err import IntegrityError

def lockless_gapless_autoname(doc, _=None):
	# print('Gapless')
	naming_series = doc.naming_series.replace('.', '').replace('#', '')
	digits = doc.naming_series.split('.')[-1].count('#') or 5
	getter_db = get_db()
	try:
		next_name = get_next_value(getter_db, doc.doctype, naming_series, digits)
		doc.name = next_name
		doc.flags.retry_on_duplicate_insert = True
	finally:
		getter_db.close()

def get_db():
	try:
		return frappe.local.gapless_autoname_conn
	except AttributeError:
		getter_db = frappe.local.gapless_autoname_conn = PatchedDatabase()
		return getter_db

def get_next_value(db, doctype, naming_series, digits, failsafe=10):
	if failsafe < 0:
		frappe.throw('Failsafe broke')

	current = db.sql('select current from `tabSeries` where name = %(name)s for update', {
		'name': naming_series,
	})
	if current:
		current = current[0][0]
	else:
		try:
			max_val = db.sql(f'''
				SELECT
					max(name)
				from
					`tab{doctype}`
				where
					name like %(naming_series)s
					and name regexp "^{db.escape(naming_series)}[0-9]+$"
			''', {
				'naming_series': f'{naming_series}%',
			})[0][0]
			current = int(max_val[len(naming_series):]) if max_val else 0
			print('FOund new current = ', current)
			db.sql('insert into `tabSeries` (name, current) value (%(name)s, %(current)s)', {
				'name': naming_series,
				'current': current,
			})
		except IntegrityError:
			return get_next_value(db, naming_series, digits, failsafe - 1)
	# print('Current Value', naming_series, current)

	next_name = get_min_used_name(db, doctype, naming_series, digits, current)
	# print('Found Next name=', next_name)
	db.commit()
	return next_name

INCR_BY = 10
INSERT_STRING = f'''
	insert into `tabGapless Name Record`
		(ref_doctype, naming_series, generated_name, status, modified)
	values
		{','.join(["(%s, %s, %s, %s, %s)"] * INCR_BY)}
'''
def get_min_used_name(db, doctype, naming_series, digits, current):
	min_name = db.sql('''
		SELECT
			min(generated_name)
		from
			`tabGapless Name Record`
		where
			naming_series = %(naming_series)s
			and status = "Pending"
	''', {
		'naming_series': naming_series
	})[0][0]
	# print('Min name', min_name)
	if min_name:
		db.sql('''
			update
				`tabGapless Name Record`
			set
				status = "Used"
			where
				naming_series = %(naming_series)s
				and status = 'Pending'
				and generated_name = %(used_name)s
		''', {
			'used_name': min_name,
			'naming_series': naming_series,
		})
		return min_name

	# print(f'Incrementing current {current} to {INCR_BY}', current + INCR_BY)

	now = frappe.utils.now_datetime()
	db.sql('update tabSeries set current = %(new_val)s where name = %(naming_series)s', {
		'new_val': current + INCR_BY,
		'naming_series': naming_series,
	})
	next_names = [
		j
		for i in range(1, INCR_BY + 1)
		for j in [
			doctype,
			naming_series,
			f'{naming_series}%0{digits}d' % (current + i),
			'Pending',
			now,
		]
	]
	next_names[3] = 'Used'

	db.sql(INSERT_STRING, next_names)

	return next_names[2]

def reconcile():
	doctypes = frappe.db.sql_list('''
		select distinct ref_doctype from `tabGapless Name Record`
	''')
	for doctype in doctypes:
		try:
			clean_up(doctype)
		except:
			pass

def clean_up(doctype):
	frappe.db.sql(f'''
		delete gnr from
			`tabGapless Name Record` gnr
		where
			gnr.ref_doctype = %(doctype)s
			and gnr.status = 'Used'
			and exists (
				select 1
				from `tab{doctype}` dt
				where dt.name = gnr.generated_name
			)
	''', {
		'doctype': doctype
	})
	frappe.db.commit()

	frappe.db.sql(f'''
		update
			`tabGapless Name Record` gnr
		set
			gnr.status = 'Pending'
		where
			gnr.ref_doctype = %(doctype)s
			and gnr.status = 'Used'
			and gnr.modified < %(now)s - interval 5 minute
			and not exists (
				select 1
				from `tab{doctype}` dt
				where dt.name = gnr.generated_name
			)
	''', {
		'doctype': doctype,
		'now': frappe.utils.now_datetime(),
	})
	frappe.db.commit()
