from traceback import walk_stack
from gevent.pool import Group
import latte
from pymysql.cursors import Cursor
from latte.utils.logger import get_logger
from latte.database_utils.connection_pool import PatchedDatabase
from time import perf_counter
from datetime import datetime
from latte.utils.background.job import enqueue
from latte.json import dumps, loads
from zlib import compress, decompress
from frappe import local, errprint, get_traceback
from xxhash import xxh64_hexdigest
from redis import ConnectionError, Redis

def execute(self, query, args=None, *, debug=False):
	while self.nextset():
		pass

	query = query.strip()
	if not args:
		parsed_query = query
	else:
		parsed_query = self.mogrify(query, args)

	if debug:
		print(parsed_query)

	start_time = perf_counter()
	if local.conf.log_query_type:
		query_type = query.split(' ', 1)[0].lower()
		attr_name = f'sql_{query_type}s'
		setattr(local, attr_name, getattr(local, attr_name, 0) + 1)

	try:
		result = self._query(f'/*{local.flags.current_running_method}|{local.session.user}*/ {local.append_statement_to_query} {parsed_query}')

	finally:
		end_time = perf_counter()
		query_time = end_time - start_time
		local.sql_time = getattr(local, 'sql_time', 0) + query_time
		try:
			if (
				(not getattr(self, '__no_logging', False))
				and query_time > (local.conf.sql_log_query_time_min or 1)
				and (sql_log_verbosity := local.conf.sql_log_verbosity) in ('explain', 'analyze', 'trace')
			):
				log_start = perf_counter()
				log_explain(query, parsed_query, query_time, sql_log_verbosity)
				local.sql_logging_time += perf_counter() - log_start

		except AttributeError:
			pass
		except:
			print(parsed_query)
			print(get_traceback())

	self._executed = parsed_query
	return result

Cursor.execute = execute

PUSHER_GROUP = Group()

def log_explain(query, parsed_query, query_time, sql_log_verbosity):
	if len(PUSHER_GROUP) > (local.conf.sql_log_pool_size or 5):
		return

	hash = query_analyzed(parsed_query)
	if not hash:
		return

	query_type = query.strip()[:6].lower()

	if query_type not in ('select'):
		return

	if "`name` = '" in parsed_query:
		return

	if "`parent` = '" in parsed_query:
		return

	if 'for update' in parsed_query:
		return

	# logging_threshold = local.conf.sql_log_rows_threshold or 1000
	stack_trace = '\n'.join(
		f'{frame.f_code.co_filename} | {frame.f_code.co_name} | {lineno}'
		for frame, lineno in
		walk_stack(None)
	)

	log_dict = {
		'query_time': query_time,
		'stack': stack_trace,
		'query_hash': hash,
		'parsed_query': parsed_query,
		'site': local.site,
		'log_time': datetime.utcnow(),
		'log_identity': local.flags.log_identity,
		'method': local.flags.current_running_method,
		'user': local.session.user,
		'request_id': local.flags.request_id,
		'task_id': local.flags.task_id,
	}

	if sql_log_verbosity in ('explain_off', 'analyze'):
		buffer_analyse(
			parsed_query,
			log_dict,
			local.conf.sql_log_analysis_buffer_size
		)
	elif sql_log_verbosity == 'trace':
		get_logger(index_name='sql_trace').info(log_dict)

BUFFER = []
def buffer_analyse(parsed_query, log_dict, buffer_size):
	if buffer_size is None:
		buffer_size = 10
	BUFFER.append([parsed_query, log_dict])
	if len(BUFFER) >= buffer_size:
		to_load = compress(dumps(BUFFER))
		BUFFER.clear()
		PUSHER_GROUP.spawn(async_enqueue, site=local.site, to_load=to_load)

def async_enqueue(site, to_load):
	latte.init(site=site)
	latte.connect()
	try:
		enqueue(
			bulk_analyse,
			data=to_load,
			akka_pattern=True,
			queue='sqlanalysis',
		)
	finally:
		latte.destroy()

def bulk_analyse(data):
	original_request_id = local.flags.request_id
	original_task_id = local.flags.task_id
	for row in loads(decompress(data)):
		analyse(*row)
	local.flags.request_id = original_request_id
	local.flags.task_id = original_task_id

def analyse(parsed_query, log_dict):
	analysis_db = get_analysis_db()
	try:
		analysis = analysis_db.sql(f'''
		analyze {parsed_query}''', as_simple_dict=1)
		log_dict['analysis'] = analysis
		for row in analysis:
			row['rows'] = float(str(row['rows'] or 0).split(' (')[0])
			row['r_rows'] = float(str(row['r_rows'] or 0).split(' (')[0])
	except Exception as e:
		log_dict['analysis_error'] = str(e)
	local.flags.request_id = log_dict['request_id']
	local.flags.task_id = log_dict['task_id']
	get_logger(index_name='sql_analysis').info(log_dict)

def get_analysis_db():
	try:
		analysis_db = getattr(local, 'analysis_db')
	except AttributeError:
		conf = local.conf.analysis_db_conf
		if not conf:
			return

		analysis_db = local.analysis_db = PatchedDatabase(**conf)
		analysis_db.autocommit = 1
		analysis_db.connect()
		analysis_db._cursor.__no_logging = True

	return analysis_db

def query_analyzed(query):
	_hash = xxh64_hexdigest(query.encode()) + '|' + str(len(query))
	key = f"_LATTE_QUERY_ANALYZER|{local.site}|{_hash}"
	try:
		if get_cache().set(key, 1, nx=True, ex=(local.conf.sql_log_analysis_cache_expiry or 300)):
			return _hash
	except ConnectionError:
		return

cache = None
def get_cache():
	global cache
	if (not cache):
		cache = Redis.from_url(
			local.conf.redis_sql_cache or local.conf.redis_big_cache or local.conf.redis_cache or 'redis://localhost:13000',
			socket_timeout=5,
			socket_connect_timeout=1,
		)

	return cache