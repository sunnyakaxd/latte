import frappe

from functools import wraps
from gevent import getcurrent, sleep
from pymysql.err import InternalError
from frappe.utils import cint
from latte.utils.logger import get_logger
from latte.utils.caching import get_args_for
from gevent.timeout import Timeout
from math import ceil
from frappe import local
from latte.utils.caching import (
	Disconnected,
	ConnectionError,
	TimeoutError,
	ResponseError,
)

def watch_blacklist(
	key=None,
	get_timeout=None,
	consecutive_fails=None,
	failure_window=None,
	exclude=None,
	blacklist_time=None,
):
	def decorator(fn):
		fn_name = f'{fn.__module__}.{fn.__qualname__}'
		@wraps(fn)
		def decorated(*args, **kwargs):
			args, kwargs = get_args_for(fn, args, kwargs)
			if exclude and exclude(*args, **kwargs):
				return fn(*args, **kwargs)

			conf = local.conf
			black_list_key = f'_LATTE_FN_BLACK_LISTING|{fn_name}|{key(*args, **kwargs) if key else ""}'
			# print(black_list_key)
			allowed_consecutive_failures = consecutive_fails(*args, **kwargs) if consecutive_fails else (
				conf.blacklist_consecutive_fails or 5
			)

			_review_black_list(black_list_key, allowed_consecutive_failures)
			timeout = get_timeout(*args, **kwargs) if get_timeout else (
				conf.blacklist_function_timeout or 30
			)
			time_guard_watcher = Timeout(timeout)
			time_guard_watcher.start()

			try:
				local.append_statement_to_query = f' set statement max_statement_time={timeout} for '
				resp = fn(*args, **kwargs)
				local.append_statement_to_query = ''
				return resp

			except Timeout as e:
				if e is not time_guard_watcher:
					raise

				local.db.connect() # Restore new connection for logging errors
				_blacklist(
					black_list_key,
					failure_window and failure_window(*args, **kwargs),
					allowed_consecutive_failures,
					blacklist_time, args, kwargs
				)
				frappe.throw('Request timed out, kindly retry')
				# raise WaitTimedOut(black_list_key, timeout, 'Runtime Terminated')

			except InternalError as e:
				# 1969 max_statement_time exceeded
				# 2013 Lost connection to mysql during query
				time_guard_watcher.close()
				if e.args[0] in (1969, 2103):
					_blacklist(
						black_list_key,
						failure_window and failure_window(*args, **kwargs),
						allowed_consecutive_failures,
						blacklist_time, args, kwargs
					)
					frappe.throw('Request timed out, kindly retry')
				raise

			finally:
				time_guard_watcher.close()

		return decorated

	return decorator

def _review_black_list(black_list_key, allowed_consecutive_failures):
	cache = frappe.cache()

	try:
		failures = cint(cache.get(black_list_key))
	except (Disconnected, ConnectionError, TimeoutError, ResponseError):
		failures = 0

	if failures >= allowed_consecutive_failures:
		frappe.throw(f'''
			This request is timing out too often across many users.
			Kindly retry after {ceil((cache.ttl(black_list_key) or 0)/60)} minutes
		''')

def _blacklist(black_list_key, failure_window, allowed_consecutive_failures, blacklist_time, args, kwargs):
	cache = frappe.cache()
	try:
		count = cache.incr(black_list_key)
	except (Disconnected, ConnectionError, TimeoutError, ResponseError):
		return

	conf = local.conf
	if count == 1:
		expiry = failure_window or conf.blacklist_expiry or 900 # 15 minutes default
		cache.expire(black_list_key, expiry)

	if count >= allowed_consecutive_failures:
		expiry = blacklist_time(*args, **kwargs) if blacklist_time else (conf.blacklist_time or 1800) # 30 minutes defualt
		cache.expire(black_list_key, expiry)
		error_dict = {
			'key': black_list_key,
			'allowed_consecutive_failures': allowed_consecutive_failures,
			'blacklist_time': expiry,
		}
		get_logger(index_name='blacklisted').error(error_dict)
		frappe.log_error(error_dict, 'blacklisted')
