import re
import frappe
from latte.utils.background.job import enqueue
from latte.latte_core.naming.lockless_gapless_autoname import lockless_gapless_autoname

allowed_seq_names = re.compile('[a-z0-9A-Z_]')

def lockless_autoname(doc, _=None):
	if doc.meta.autoname == 'auto_increment':
		return

	if doc.get('naming_series'):
		set_meta(doc)
		naming_series = doc.naming_series.replace('.', '').replace('#', '')
		digits = doc.naming_series.split('.')[-1].count('#') or 5
		doc.name = naming_series + \
			getseries(naming_series, doc.doctype, digits, 0)
		# print("####### doc.name - ", doc.name)

		# REVIEW: Do we need the below logic still as doubly sure check?
		while frappe.local.db.get_value(doc.doctype, doc.name, 'name'):
			new_name = naming_series + \
				getseries(naming_series, doc.doctype, digits, 0)
			# print("####### new.name - ", doc.name)
			if new_name == doc.name:
				frappe.throw('Infinite Loop detected, failing')
			doc.name = new_name

def set_meta(doc):
	if doc.meta.autoname == 'auto_increment':
		return

	meta = frappe.get_meta(doc.doctype)
	if not (meta.autoname or '').startswith('naming_series:'):
		meta.autoname = 'naming_series:'

def getseries(naming_series, doctype, digits, failures):
	# print('Parsing', naming_series, digits, failures)
	cache = frappe.cache()
	next_val = None
	current_val = cache.get(naming_series)

	if not current_val:  # Sequence name not found in cache - LazyLoading
		current_val = fetch_currentMax_from_db(naming_series, doctype)
		# Set only if another thread / request has not already set it (NX=True)
		cache.set(naming_series, current_val, nx=True)

	# Dont just increment current_val, another thread could have, so rely on redis.incr!
	next_val = cache.incr(naming_series)
	# print('NEXT_VAL=', next_val)

	# REVIEW: Check when to sync with DB. For after every 1000 keys issued.
	if next_val % 1000 == 0:
		enqueue(
			sync_cache_with_db,
			key=naming_series,
			enqueue_after_commit=True,
			monitor=False,
			job_name=naming_series,
			queue='long',
		)

	return ('%0' + str(digits) + 'd') % next_val

def fetch_currentMax_from_db(naming_series, doctype, failures=0):
	if failures > 5:
		frappe.throw('Unable to process sequence after 5 failures')
	# try:
	if not allowed_seq_names.match(str(naming_series)):
		frappe.throw('Bad sequence name detected, ' + naming_series)

	# First check in tabSeries
	# Also get the max from docType table and return max of the two.
	# REVIEW: Can we avoid looking up tabSeries altogether. I would say no for honouring frappe constructs??
	# current_val = frappe.local.db.sql('select current from `tabSeries` where name = %(name)s', {
	#     'name': naming_series,
	# })
	# print("########### recd cur val - ", current_val)
	# current_val = current_val[0][0] if current_val else 0
	current_val = 0
	# Even if we get from tabSeries, lets check in doctype table for last max insert.
	# Since we are syncing to tabSeries post every 1000 increments.
	max_val = frappe.local.db.sql(f'''
		SELECT
			name
		from
			`tab{doctype}`
		where
			name like %(naming_series)s
			and name regexp "^{frappe.local.db.escape(naming_series)}[0-9]+$"
			order by name desc
			limit 1
	''', {
		'naming_series': f'{naming_series}%',
	})
	max_val = max_val[0][0] if max_val else 0
	current_val = int(
		max_val[len(naming_series):]) if max_val else 0

	# current_val = current_val if current_val >= value else value

	# except (AttributeError, OperationalError, InterfaceError, IntegrityError, IndexError) as ie:
	#     return fetch_currentMax_from_db(naming_series, doctype, failures + 1)

	return current_val

def sync_cache_with_db(key):
	cache = frappe.cache()
	if value := cache.get(key):
		value = int(value)
		upsert_series_table(key, value)

def upsert_series_table(key, value):

	# wish I could do this -> INSERT INTO `tabSeries` VALUES (%(key)s,%(value)s) ON DUPLICATE KEY UPDATE current=%(value)s;
	# But tabSeries doesnt have unique key.
	frappe.local.db.sql('''
		INSERT INTO
			`tabSeries`
		VALUES (%(key)s,%(value)s)
		ON DUPLICATE KEY
		UPDATE current=%(value)s
	''', {
		'key': key,
		'value': value,
	})
