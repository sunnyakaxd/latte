import frappe
import pymysql
import numpy
import sqlalchemy.pool as pool
from frappe import as_unicode
from six import text_type, string_types
from markdown2 import UnicodeWithAttrs
from pymysql.constants import ER, FIELD_TYPE
from pymysql.converters import conversions
from frappe.database import Database as UnpatchedDatabase
from latte.utils import get_system_setting
from latte.utils.caching import cache_in_mem
from latte.utils.logger import get_logger
from time import perf_counter
from frappe.installer import update_site_config
# from datetime import datetime
from ciso8601 import parse_datetime
try:
	from pymysql import escape_string
except ImportError:
	from pymysql.converters import escape_string

from pymysql.err import (
	OperationalError,
	InterfaceError,
	ProgrammingError
)
from frappe import local
conversions.update({
	FIELD_TYPE.NEWDECIMAL: float,
	# FIELD_TYPE.DATETIME: frappe.utils.get_datetime,
	FIELD_TYPE.DATETIME: parse_datetime,
	UnicodeWithAttrs: conversions[text_type],
	numpy.float64: lambda val, _: float(val),
})

# import warnings
# warnings.simplefilter('error')
class DBShieldException(Exception):
	pass

class PatchedDatabase(UnpatchedDatabase):
	con_pool = {}

	__slots__ = [
		'host', 'port', 'user', 'password', 'db_name', 'autocommit',
		'__run_after_commit', '__run_before_commit',
		'_conn', '_cursor', 'value_cache',
		'transaction_writes', 'unpatched_sql', 'connection_string',
		'read_only', 'cur_db_name', 'read_only_session', 'pool_id'
	]

	def __init__(self, host=None, port=None, user=None, password=None, db_name=None, autocommit=False, use_db=True, read_only_session=False):
		self.host = host or frappe.conf.db_host or '127.0.0.1'
		self.port = port or frappe.conf.db_port or 3306
		self.user = user or frappe.conf.db_user or frappe.conf.db_name
		self.password = password or frappe.conf.db_password
		self.db_name = (db_name or frappe.conf.db_name) if use_db else None
		self.autocommit = autocommit
		self.__run_after_commit = []
		self.__run_before_commit = []
		self._conn = None
		self._cursor = None
		self.value_cache = {}
		self.transaction_writes = 0
		self.unpatched_sql = super().sql
		self.read_only_session = read_only_session
		self.connection_string = f'mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db_name}'

	def copy(self):
		return PatchedDatabase(
			host=self.host,
			port=self.port,
			user=self.user,
			password=self.password,
			db_name=self.db_name,
			autocommit=self.autocommit,
		)

	def __enter__(self):
		return self

	def __exit__(self, type, value, traceback):
		self.close()

	def check_transaction_status(self, *_, **__):
		pass

	def execute(self, query, values, debug=False):
		if not self._conn:
			self.connect()

		if values != () and not isinstance(values, (dict, tuple, list)):
			values = (values,)

		return self._cursor.execute(query, values, debug=debug)

	def execute_many(self, query, values, debug=False):
		if not self._conn:
			self.connect()

		return self._cursor.executemany(query, values)

	def get_value(self, doctype, filters=None, fieldname="name", ignore=None, as_dict=False,
		debug=False, order_by=None, cache=False):

		ret = self.get_values(doctype, filters, fieldname, ignore, as_dict, debug,
			order_by, cache=cache, limit=1)

		return ((len(ret[0]) > 1 or as_dict) and ret[0] or ret[0][0]) if ret else None

	def get_values(self, doctype, filters=None, fieldname="name", ignore=None, as_dict=False,
		debug=False, order_by=None, update=None, cache=False, limit=None):
		out = None
		if cache and isinstance(filters, string_types) and \
			(doctype, filters, fieldname) in self.value_cache:
			return self.value_cache[(doctype, filters, fieldname)]

		if not order_by: order_by = 'modified desc'

		if isinstance(filters, list):
			out = self._get_value_for_many_names(doctype, filters, fieldname, debug=debug)

		else:
			fields = fieldname
			if fieldname!="*":
				if isinstance(fieldname, string_types):
					fields = [fieldname]
				else:
					fields = fieldname

			if (filters is not None) and (filters!=doctype or doctype=="DocType"):
				try:
					out = self._get_values_from_table(fields, filters, doctype, as_dict, debug, order_by, update, limit)
				except Exception as e:
					if ignore and e.args[0] in (1146, 1054):
						# table or column not found, return None
						out = None
					elif (not ignore) and e.args[0]==1146:
						# table not found, look in singles
						out = self.get_values_from_single(fields, filters, doctype, as_dict, debug, update)
					else:
						raise
			else:
				out = self.get_values_from_single(fields, filters, doctype, as_dict, debug, update)

		if cache and isinstance(filters, string_types):
			self.value_cache[(doctype, filters, fieldname)] = out

		return out

	def _get_values_from_table(self, fields, filters, doctype, as_dict, debug, order_by=None, update=None, limit=None):
		fl = []
		if isinstance(fields, (list, tuple)):
			for f in fields:
				if "(" in f or " as " in f: # function
					fl.append(f)
				else:
					fl.append("`" + f + "`")
			fl = ", ".join(fl)
		else:
			fl = fields
			if fields=="*":
				as_dict = True

		conditions, values = self.build_conditions(filters)

		order_by = ("order by " + order_by) if order_by else ""

		limit = f" limit {limit}" if limit else ""
		r = self.sql(
			f"select {fl} from `tab{doctype}` {'where' if conditions else ''} {conditions} {order_by}{limit}",
			values,
			as_dict=as_dict,
			debug=debug,
			update=update,
		)

		return r

	def _get_value_for_many_names(self, doctype, names, field, debug=False):
		names = list(filter(None, names))

		if names:
			return dict(self.sql(
				f'select name, `{field}` from `tab{doctype}` where name in ({", ".join(["%s"]*len(names))})',
				names,
				debug=debug,
			))
		else:
			return {}

	def sql(self, query, values=(), as_dict=False, as_simple_dict=False, as_list=False, formatted=False,
		debug=False, ignore_ddl=False, as_utf8=False, auto_commit=False, update=None, explain=False,
		# statement_variables=None
		):
		"""Execute a SQL query and fetch all rows.

		:param query: SQL query.
		:param values: List / dict of values to be escaped and substituted in the query.
		:param as_dict: Return as a dictionary.
		:param as_list: Always return as a list.
		:param formatted: Format values like date etc.
		:param debug: Print query and `EXPLAIN` in debug log.
		:param ignore_ddl: Catch exception if table, column missing.
		:param as_utf8: Encode values as UTF 8.
		:param auto_commit: Commit after executing the query.
		:param update: Update this dict to all rows (if returned `as_dict`).

		Examples:

			# return customer names as dicts
			frappe.db.sql("select name from tabCustomer", as_dict=True)

			# return names beginning with a
			frappe.db.sql("select name from tabCustomer where name like %s", "a%")

			# values as dict
			frappe.db.sql("select name from tabCustomer where name like %(name)s and owner=%(owner)s",
				{"name": "a%", "owner":"test@example.com"})

		"""

		if frappe.local.flags.sheild and query.startswith('select'):
			self.optimized_query_check(query, values)

		# in transaction validations
		# self.check_transaction_status(query)

		# autocommit
		if auto_commit: self.commit()

		# execute
		try:
			if debug:
				time_start = perf_counter()

			self.execute(query, values, debug=debug)

			if debug:
				time_end = perf_counter()
				print(("Execution time: {0} sec").format(round(time_end - time_start, 2)))

		except Exception as e:
			if ignore_ddl and e.args[0] in (ER.BAD_FIELD_ERROR, ER.NO_SUCH_TABLE,
				ER.CANT_DROP_FIELD_OR_KEY):
				pass
			else:
				raise

		if auto_commit: self.commit()

		# scrub output if required
		if as_dict:
			ret = self.fetch_as_dict(formatted, as_utf8)
			if update:
				for r in ret:
					r.update(update)
			return ret
		elif as_simple_dict:
			return self.fetch_as_simple_dict()
		elif (as_list or as_utf8):
			return self.convert_to_lists(self._cursor.fetchall(), formatted, as_utf8)
		else:
			return self._cursor.fetchall()

	def fetch_as_simple_dict(self):
		"""Internal. Converts results to dict."""
		result = self._cursor.fetchall()
		if not result:
			return []

		keys = [column[0] for column in self._cursor.description]
		enumerator = list(enumerate(keys))
		return [
			{
				key: row[i]
				for i, key in enumerator
			}
			for row in result
		]

	def get_single_value(self, doctype, fieldname, cache=False):
		if local.conf.use_cached_doc_for_single:
			return frappe.get_cached_value(doctype, doctype, fieldname)
		else:
			return super().get_single_value(doctype, fieldname, cache=cache)

	def get_system_setting(self, key):
		return get_system_setting(key)

	@cache_in_mem(key=lambda _,table: table, timeout=3600)
	def get_db_table_columns(self, table):
		"""Returns list of column names from given table."""
		return [r[0] for r in self.sql("DESC `%s`" % table)]

	def run_before_commit(self, fn, *args, **kwargs):
		self.__run_before_commit.append(
			(fn, args, kwargs)
		)

	def run_after_commit(self, fn, *args, **kwargs):
		self.__run_after_commit.append(
			(fn, args, kwargs)
		)

	def commit(self):
		if not self._conn:
			return

		self.process_before_commit_queue()
		self.sql('commit')
		self.process_after_commit_queue()
		if not self.autocommit:
			super().commit()

	def process_before_commit_queue(self):
		local_queue = self.__run_before_commit
		self.__run_before_commit = []
		for fn, args, kwargs in local_queue:
			fn(*args, **kwargs)

	def process_after_commit_queue(self):
		local_queue = self.__run_after_commit
		self.__run_after_commit = []
		for fn, args, kwargs in local_queue:
			fn(*args, **kwargs)


	def rollback(self):
		self.__run_before_commit = []
		self.__run_after_commit = []

		if (not self.autocommit) and self._conn:
			try:
				super().rollback()
			except InterfaceError:
				pass
			except OperationalError as e:
				if e.args[0] not in (1927, 2013):
					raise

	def connect(self, retry_count=0):
		self.autocommit = not not self.autocommit
		self.pool_id = f'{self.user}|{self.host}|{self.port}|{self.db_name}|{self.autocommit}'
		self._conn = self.get_pool().connect()
		self._conn.ping(reconnect=True)
		self.cur_db_name = self.db_name
		self._cursor = self._conn.cursor()
		if self.read_only_session:
			self.sql('start transaction READ ONLY')
		elif local.conf.use_read_committed_session:
			self.sql('set session transaction isolation level READ COMMITTED')

	def get_pool(self):
		try:
			return self.con_pool[self.pool_id]
		except KeyError:
			con_pool = self.con_pool[self.pool_id] = pool.QueuePool(
				lambda *_:self.get_connection(),
				max_overflow=10,
				pool_size=100,
				use_lifo=True,
			)

		return con_pool

	def get_connection(self):
		return pymysql.connect(
			host=self.host,
			user=self.user,
			password=self.password,
			port=int(self.port),
			charset='utf8mb4',
			use_unicode=True,
			conv=conversions,
			db=self.db_name,
			autocommit=self.autocommit,
		)

	def read_only_sql(self, *args, **kwargs):
		with self.copy() as read_only_conn:
			read_only_conn.sql('start transaction READ ONLY')
			return read_only_conn.sql(*args, **kwargs)

	@property
	def open(self):
		return self._conn and self._conn.open

	def mogrify(self, query, filters):
		if not self.open:
			self.connect()

		return self._cursor.mogrify(query, filters)

	def close(self):
		"""Close database connection."""
		if self._conn and self._conn.open:
			# self._cursor.close()
			self._conn.close()
			self._cursor = None
			self._conn = None

	def build_conditions(self, filters):
		if isinstance(filters, (int, float)):
			filters = str(filters)
		return super().build_conditions(filters)

	def optimized_query_check(self,query, values):
		result = self.unpatched_sql(f'explain {query}', values or (), as_dict=1)

		for row in result:
			if row['key'] is None and row['rows'] is not None and int(row['rows']) > 100000:
				raise DBShieldException()

	def processlist(self):
		return self.sql('''
			select
				id,
				user,
				host,
				db,
				command,
				time_ms,
				state,
				info,
				stage,
				progress,
				memory_used,
				max_memory_used,
				examined_rows,
				query_id,
				tid
			from
				information_schema.processlist
			where
				command != 'Sleep'
		''', as_simple_dict=True)

	def get_descendants(self, doctype, name):
		'''Return descendants of the current record'''
		node_location_indexes = self.get_value(doctype, name, ('lft', 'rgt'))
		if node_location_indexes:
			lft, rgt = node_location_indexes
			return self.sql_list(f'''
				select
					name from `tab{doctype}`
				where
					lft between {lft} and {rgt}
					and name != %(name)s
			''', {
				'name': name,
			})
		else:
			# when document does not exist
			return []

	def escape(self, s, percent=True):
		"""Excape quotes and percent in given string."""
		# pymysql expects unicode argument to escape_string with Python 3
		s = as_unicode(escape_string(as_unicode(s)), "utf-8").replace("`", "\\`")

		# NOTE separating % escape, because % escape should only be done when using LIKE operator
		# or when you use python format string to generate query that already has a %s
		# for example: sql("select name from `tabUser` where name=%s and {0}".format(conditions), something)
		# defaulting it to True, as this is the most frequent use case
		# ideally we shouldn't have to use ESCAPE and strive to pass values via the values argument of sql
		if percent:
			s = s.replace("%", "%%")

		return s


def switch_replica():
	conf = frappe.conf

	if not conf.use_slave_for_read_only:
		update_site_config('use_slave_for_read_only', True)

	allowed_lag = conf.slave_lag_tolerance or 60
	pool_configs = frappe.local.conf.slave_db_pool

	if not pool_configs:
		return

	for config in pool_configs:
		user = conf.db_replication_client_user
		password = conf.db_replication_client_password
		slave_host = config['host']
		slave_port = config['port']

		db = PatchedDatabase(
			host=slave_host,
			port=slave_port,
			user=user,
			password=password,
			use_db=False,
		)
		db.use = lambda x: None
		slave_status = None
		try:
			slave_status = db.sql('show slave status', as_dict=True)
		except Exception:
			frappe.log_error(title=f'slave_connect_failed_{slave_host}')
		finally:
			db.close()

		if (not (slave_status and slave_status[0])) or (slave_status[0].get('Seconds_Behind_Master') is None):
			slave_lag = float('inf')
		else:
			slave_lag = slave_status[0].get('Seconds_Behind_Master')

		if slave_lag > allowed_lag:
			frappe.log_error(f'''
				Slave host {slave_host}
				is lagging by {slave_lag}
			''', 'replica_info')
			continue
		break
	else:
		frappe.log_error(f'''
			All Slave hosts have failed.
		''', 'replica_info')
		if not conf.no_shift_to_primary_on_lag:
			slave_host = conf.db_host
			slave_port = conf.db_port

	if conf.slave_host != slave_host:
		update_site_config('slave_host', slave_host)

	if conf.slave_port != slave_port:
		update_site_config('slave_port', slave_port)

def log_processlist():
	processlist = frappe.db.processlist()
	logger = get_logger(index_name='processlist')
	for row in processlist:
		logger.info(row)
