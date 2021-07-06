import frappe
from frappe.model.document import Document
import redis
import kafka
import latte
from latte.app import _sites_path as SITES_PATH
from six import string_types
from types import FunctionType, MethodType
from functools import wraps
from uuid import uuid4
from pickle import dumps as pickle_dumps
from gevent.pool import Pool as GeventPool
from latte import _dict
from latte.utils.logger import get_logger
from time import perf_counter, time_ns
from sys import stderr
from zlib import compress
from frappe import local
from datetime import datetime
from latte.utils.caching import cache_in_mem, cache_me_if_you_can
from latte.latte_core.doctype.background_job_config.background_job_config import BackgroundJobConfig

GLOBAL_REDIS_CONN = None
SUCCESS = 'Success'
FAILURE = 'Failure'
STARTED = 'Started'

def enqueue(method, queue='default', timeout=None, event=None, monitor=False, set_user=None,
	method_name=None, job_ident=None, job_name=None, now=False, enqueue_after_commit=False,
	sessionless=False, partition_key=None, akka_pattern=False, parse_to_primitives=False,
	job_priority=1,
	**kwargs):
	'''
		Enqueue method to be executed using a background worker

		:param method: method string or method object
		:param queue: should be either long, default or short
		:param timeout: should be set according to the functions
		:param event: this is passed to enable clearing of jobs from queues
		:param job_name: can be used to name an enqueue call, which can be used to prevent duplicate calls
		:param now: if now=True, the method is executed via frappe.call
		:param kwargs: keyword arguments to be passed to the method
	'''

	kwargs.pop('async', None)
	kwargs.pop('is_async', None)

	if now or local.flags.in_migrate or local.flags.in_install_app or local.flags.in_install:
		if isinstance(method, str):
			method = frappe.get_attr(method)
		return method(**kwargs)

	if not method_name:
		if type(method) in (FunctionType, MethodType):
			method_name = f'{method.__module__}.{method.__qualname__}'
		else:
			method_name = str(method)

	if admin_config := get_job_configs().get(method_name):
		if admin_config.job_disabled:
			return

		queue = admin_config.queue or queue
		job_priority = admin_config.priority or job_priority

	job_run_id = monitor and create_job_run(method, queue, ident=job_ident).name
	if not queue:
		queue = 'default'

	if job_name:
		job_name = f'{method_name}:{job_name}'

	docs = []
	method_meta = None

	if parse_to_primitives:
		for key, value in kwargs.items():
			if isinstance(value, Document):
				docs.append((key, value.doctype, value.name,))
				kwargs[key] = None

		if type(method) == MethodType and isinstance(method.__self__, Document):
			method_meta = [
				method.__self__.doctype,
				method.__self__.name,
				method.__name__,
			]
			method = None

	queue_args = {
		"akka_pattern": akka_pattern,
		"docs": docs,
		"event": event,
		"job_name": job_name or str(uuid4()),
		"job_run_id": job_run_id,
		"kwargs": kwargs,
		"log_flags": {},
		"method": method,
		"method_meta": method_meta,
		"method_name": method_name,
		"partition_key": partition_key,
		"priority": job_priority,
		"queue": queue,
		"request_id": local.flags.request_id,
		"sessionless": sessionless,
		"site": local.site,
		"timeout": timeout,
		"user": set_user or frappe.session.user,
	}

	if enqueue_after_commit:
		frappe.db.run_after_commit(enqueue_to_queue, queue_args)
	else:
		enqueue_to_queue(queue_args)

@cache_in_mem(
	invalidate=BackgroundJobConfig.get_invalidate_key,
)
@cache_me_if_you_can(
	invalidate=BackgroundJobConfig.get_invalidate_key,
	expiry=None,
)
def get_job_configs():
	try:
		return {
			row.job_name: row
			for row in
			frappe.get_all('Background Job Config', fields=['job_name', 'queue', 'priority', 'job_disabled'])
		}
	except:
		return {}

def enqueue_to_queue(queue_args):
	queue_args["log_flags"]["enqueued_at"] = datetime.utcnow()
	if queue_args['akka_pattern'] or queue_args['partition_key'] is not None:
		enqueue_to_kafka(queue_args)
	else:
		enqueue_to_redis(queue_args)

def enqueue_to_kafka(queue_args):
	process_producer = get_producer()

	pickled = pickle_dumps(queue_args)
	compressed = compress(pickled)
	partition_key = queue_args['partition_key']

	process_producer.send(
		get_kafka_queue_name(queue_args['queue']),
		value=compressed,
		key=str(partition_key).encode() if partition_key is not None else partition_key,
	)
	return True

LATTE_QUEUE_PREFIX = 'latte-queue'
def get_kafka_queue_name(queue):
	conf = local.conf.kafka_queue
	return f'{LATTE_QUEUE_PREFIX}-{conf["queue_prefix"]}-{queue}'

PRODUCERS = {}

def get_producer():
	try:
		return PRODUCERS[local.site]
	except KeyError:
		pass

	conf = local.conf.kafka_queue
	if not conf:
		raise Exception('Kafka Queue Producer not configured but called')

	#get kafka connection
	kafka_config_host = conf['bootstrap_servers']
	kafka_client_id = conf['client_id']

	process_producer = PRODUCERS[local.site] = kafka.KafkaProducer(
		bootstrap_servers=kafka_config_host,
		client_id=kafka_client_id,
	)

	if local.conf.developer_mode or conf.get('always_flush'):
		old_send = process_producer.send

		def send(*args, **kwargs):
			retval = old_send(*args, **kwargs)
			process_producer.flush()
			return retval

		process_producer.send = send

	return process_producer

def enqueue_to_redis(queue_args):
	conn = get_redis_conn()
	queue_name = f'latte:squeue:{queue_args["queue"]}'
	pickled = pickle_dumps(queue_args)
	job_name = queue_args['job_name']
	priority = queue_args['priority']
	job_score = int(time_ns() / (10 ** priority))
	# compressed = compress(pickled)
	conn.enqueue_job([
		queue_name,
		job_name,
		job_score,
		pickled,
	])

QUEUE_UNIQUE_HASH = 'latte:queueuniquehash'

def get_redis_conn():
	global GLOBAL_REDIS_CONN

	if GLOBAL_REDIS_CONN:
		return GLOBAL_REDIS_CONN
	else:
		redis_connection = GLOBAL_REDIS_CONN = redis.from_url(local.conf.redis_queue)

		# 1 - queue name
		# 2 - job_name
		# 3 - priority
		# 4 - pickled
		redis_connection.enqueue_job = redis_connection.register_script(f'''
			redis.call('zadd', KEYS[1], KEYS[3], KEYS[2])
			redis.call('hset', "{QUEUE_UNIQUE_HASH}", KEYS[2], KEYS[4])
		''')

		return redis_connection

def set_job_status(job_id, status):
	if not job_id:
		return

	if status == STARTED:
		frappe.db.set_value('Job Run', job_id, 'started', frappe.utils.now_datetime())
	elif status in (SUCCESS, FAILURE):
		frappe.db.set_value('Job Run', job_id, 'finished', frappe.utils.now_datetime())

	#frappe.db.set_value('Job Run', job_id, 'status', status)
	frappe.get_doc("Job Run", job_id).update_status(status)

def set_error_log_to_job(job_id, error_log):
	if not job_id:
		return

	frappe.db.set_value('Job Run', job_id, 'error_log', error_log)

def create_job_run(method, queue=None, ident=None):
	if type(method) in (FunctionType, MethodType):
		method = f'{method.__module__}.{method.__qualname__}'
	else:
		method = str(method)
	doc = frappe.get_doc({
		'doctype': 'Job Run',
		'method': method,
		'ident': ident,
		'title': method,
		'status': 'Enqueued',
		'enqueued_at': frappe.utils.now_datetime(),
		'queue_name': queue,
	})
	doc.db_insert()
	return doc

def background(identity=None, enqueue_after_commit=True, partition_key=None, parse_to_primitives=False, **dec_args):
	def decorator(fn):
		@wraps(fn)
		def decorated(*pos_args, __run__now=False, __pos__args=[], __primitive_pos_args={}, **kw_args):
			if __run__now:
				if parse_to_primitives:
					for idx, (dt, dn) in __primitive_pos_args.items():
						__pos__args[idx] = frappe.get_doc(dt, dn)

				fn(*__pos__args, **kw_args)
			else:
				calc_partition_key = partition_key(*pos_args, **kw_args) if callable(partition_key) else partition_key
				kw_args.update(dec_args)
				job_ident = identity and identity(*pos_args, **kw_args)
				if parse_to_primitives:
					pos_args = list(pos_args)
					for idx in range(len(pos_args)):
						if isinstance((value := pos_args[idx]), Document):
							__primitive_pos_args[idx] = (value.doctype, value.name,)
							pos_args[idx] = None

				return enqueue(
					decorated,
					__run__now=True,
					__pos__args=pos_args,
					__primitive_pos_args=__primitive_pos_args,
					job_ident=job_ident,
					monitor=True,
					partition_key=calc_partition_key,
					parse_to_primitives=parse_to_primitives,
					enqueue_after_commit=enqueue_after_commit,
					**kw_args,
				)
		return decorated
	return decorator

def clocked():
	def decorator(fn):
		method_key = f'{fn.__module__}.{fn.__qualname__}'
		def decorated(key:str=''):
			last_job_run = get_last_job_run(method_key, key)
			job = create_job_run(method_key, ident=key)
			try:
				set_job_status(job.name, STARTED)
				fn(last_job_run, job.enqueued_at, key)
				set_job_status(job.name, SUCCESS)
			except:
				set_job_status(job.name, FAILURE)
				raise
		return decorated
	return decorator

def get_last_job_run(method_key, key):
	last_run = frappe.db.sql(f'''
		select
			max(started)
		from
			`tabJob Run`
		where
			method = %(method)s
			and ident = %(ident)s
			and status = '{SUCCESS}'
	''', {
		'method': method_key,
		'ident': key,
	})[0][0]
	if not last_run:
		last_run = '1970-01-01'
	return last_run

class Task(object):
	__slots__ = ['id', 'site', 'method', 'user', 'method_name', 'job_name', 'kwargs', 'queue',
				'request_id', 'job_run_id', 'sessionless', 'log_flags', 'flags', 'docs']

	pool = GeventPool(50)

	class DontCatchMe(Exception):
		pass

	def __init__(self, site, method, user, queue, request_id=None, job_run_id=None, job_name=None, kwargs={},
		method_name='', sessionless=False, log_flags={}, docs=[], **flags):
		self.id = str(uuid4())
		self.site = site
		self.method = method
		self.user = user

		if not method_name:
			if isinstance(method, string_types):
				method_name = method
			else:
				method_name = f'{self.method.__module__}.{self.method.__qualname__}'

		self.method_name = method_name
		self.kwargs = kwargs
		self.queue = queue
		self.request_id = request_id
		self.job_name = job_name
		self.job_run_id = job_run_id
		self.sessionless = sessionless
		self.flags = _dict(flags)
		self.log_flags = log_flags
		self.docs = docs

	def process_task(self):
		return self.pool.spawn(fastrunner, self)

def fastrunner(task, before_commit=None):
	task.log_flags['started_at'] = datetime.utcnow()
	latte.init(site=task.site, sites_path=SITES_PATH, force=True)
	latte.local.flags.sessionless = task.sessionless
	local.flags.request_id = task.request_id
	local.flags.task_id = str(uuid4())
	local.flags.runner_type = f'fastrunner-{task.queue}'
	log = get_logger(index_name='bg_info')

	log.info({
		'method': task.method_name,
		'job_name': task.job_name,
		'pool_size': len(task.pool),
		'stage': 'Executing',
		'log_flags': task.log_flags,
	})

	start_time = perf_counter()
	try:
		latte.connect(admin=False)
		local.lang = frappe.db.get_default('lang')
		if task.user:
			frappe.set_user(task.user)
		else:
			frappe.set_user('Administrator')

		set_job_status(task.job_run_id, STARTED)

		if task.method is None and (meta := task.flags.get('method_meta')):
			task.method = getattr(frappe.get_doc(meta[0], meta[1]), meta[2])

		if isinstance(task.method, string_types):
			task.method = frappe.get_attr(task.method)
		local.flags.current_running_method = task.method_name

		for key, dt, dn in task.docs:
			task.kwargs[key] = frappe.get_doc(dt, dn)

		task.method(**task.kwargs)
		if before_commit:
			before_commit(task)
		end_time = perf_counter()
		frappe.db.commit()
		set_job_status(task.job_run_id, SUCCESS)

		tat = end_time - start_time
		log_info = {
			'turnaround_time': tat,
			'sql_time': local.sql_time,
			'method': task.method_name,
			'job_name': task.job_name,
			'pool_size': len(task.pool),
			'stage': 'Completed',
			'log_flags': task.log_flags,
			'sql_selects': local.sql_selects,
			'sql_updates': local.sql_updates,
			'sql_deletes': local.sql_deletes,
			'sql_inserts': local.sql_inserts,
			'cache_balancer_time': local.cache_balancer_time,
			'read_only_db_logs': local.read_only_db_logs,
			'greenlet_time': local.greenlet_time + perf_counter() - local.greenlet_start,
		}
		sql_time = log_info['sql_time'] = local.sql_time
		cache_access_time = log_info['cache_access_time'] = local.cache_access_time
		sql_logging_time = log_info['sql_logging_time'] = local.sql_logging_time
		log_info['python_time'] = tat - sql_time - cache_access_time - sql_logging_time
		log.info(log_info)

	except Exception as e:
		end_time = perf_counter()
		traceback = frappe.get_traceback()
		tat = end_time - start_time
		log_info = {
			'turnaround_time': tat,
			'sql_time': local.sql_time,
			'cache_balancer_time': local.cache_balancer_time,
			'method': task.method_name,
			'job_name': task.job_name,
			'pool_size': len(task.pool),
			'stage': 'Failed',
			'traceback': traceback,
			'log_flags': task.log_flags,
			'sql_selects': local.sql_selects,
			'sql_updates': local.sql_updates,
			'sql_deletes': local.sql_deletes,
			'sql_inserts': local.sql_inserts,
			'read_only_db_logs': local.read_only_db_logs,
			'greenlet_time': local.greenlet_time + perf_counter() - local.greenlet_start,
		}

		sql_time = log_info['sql_time'] = local.sql_time
		cache_access_time = log_info['cache_access_time'] = local.cache_access_time
		sql_logging_time = log_info['sql_logging_time'] = local.sql_logging_time
		log_info['python_time'] = tat - sql_time - cache_access_time - sql_logging_time
		log.info(log_info)
		frappe.db.rollback()
		error_log = frappe.log_error(title=task.method_name, message=traceback)

		if task.job_run_id:
			set_job_status(task.job_run_id, FAILURE)
			set_error_log_to_job(task.job_run_id, error_log.name)
			frappe.db.commit()

		print(traceback, file=stderr)

		if isinstance(e, Task.DontCatchMe):
			raise

	finally:
		frappe.destroy()
