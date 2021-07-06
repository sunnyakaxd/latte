import sys
import frappe

import signal

import redis

from sys import exit
from latte.utils import errprint
from latte.utils.logger import get_logger
from latte.utils.scheduler import start_scheduler
import latte

GRACEFUL_SHUTDOWN_WAIT = 10

def start(queues=None, enable_scheduler=False):
	from gevent import spawn
	from gevent.signal import signal as handle_signal
	if not queues:
		queues = 'short,long,default'
	if isinstance(queues, str):
		queues = queues.split(',')
	latte.init(site='')
	errprint(f'Starting Gevent worker for queues {queues}')
	handle_signal(signal.SIGHUP, graceful_shutdown)
	handle_signal(signal.SIGINT, graceful_shutdown)
	handle_signal(signal.SIGTERM, graceful_shutdown)
	if enable_scheduler:
		spawn(scheduler)
	deque_and_enqueue(queues, frappe.local.conf)

def scheduler():
	from gevent import spawn
	spawn(start_scheduler)

def fetch_jobs_from_redis(queues, conf):
	from pickle import loads
	from latte.utils.background.job import QUEUE_UNIQUE_HASH, Task
	redis_queue_host = conf.get('redis_queue', 'redis://localhost:11000')
	log = get_logger(index_name='bg_info')
	conn = None
	errprint('Connecting to', redis_queue_host)
	conn = redis.StrictRedis.from_url(redis_queue_host)
	errprint('Connected')
	script_runner = conn.register_script(f'''
		local pickled_data = redis.call('hget', '{QUEUE_UNIQUE_HASH}', KEYS[1])
		if pickled_data ~= nil then
			redis.call('hdel', '{QUEUE_UNIQUE_HASH}', KEYS[1])
		end
		return {{pickled_data}}
	''')
	rq_queues = [f'latte:squeue:{queue}' for queue in queues]
	while True:
		queue_name, job_name, _ = conn.execute_command(
			'BZPOPMIN',
			*rq_queues,
			0,
		)
		# job_meta = zlib.decompress(job_dict.data)
		try:
			unique_job_meta_list = script_runner([job_name])
			if (unique_job_meta := (unique_job_meta_list and unique_job_meta_list[0])):
				job_meta = loads(unique_job_meta)
			else:
				continue

			yield Task(**job_meta)

		except Exception:
			print(frappe.get_traceback(), file=sys.stderr)
			log.info({
				'queue_name': str(queue_name, 'utf-8'),
				'method': '__NONE__',
				'pool_size': 0,
				'stage': 'Fatal',
				'traceback': frappe.get_traceback(),
			})

def deque_and_enqueue(queues, conf):
	for task in fetch_jobs_from_redis(queues, conf):
		task.process_task()

def graceful_shutdown(*args, **kwargs):
	from latte.utils.background.job import Task
	print('Warm shutdown requested')
	graceful = Task.pool.join(timeout=GRACEFUL_SHUTDOWN_WAIT)
	print('Shutting down, Gracefully=', graceful)
	exit(0 if graceful else 1)