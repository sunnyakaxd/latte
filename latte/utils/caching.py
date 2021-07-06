import sys
import frappe
import inspect
import pickle
import gevent
from time import perf_counter
import traceback
import latte
from xxhash import xxh64_hexdigest, xxh64_intdigest
from gevent.lock import BoundedSemaphore
from functools import wraps
from werkzeug.local import get_ident
from redis import Redis
from frappe import local
from frappe.utils import cstr
from latte.utils.logger import get_logger
from redis.exceptions import ConnectionError, TimeoutError, ResponseError
import re
from traceback import walk_stack

PENDING = pickle.dumps('__PENDING__')

GLOBAL_REDIS_CACHE = None

class RecursiveCall(Exception):
	pass

class Disconnected(Exception):
	pass

class Lock(BoundedSemaphore):
	@staticmethod
	def get_thread_identity():
		return get_ident()

	def __init__(self):
		super().__init__()
		self.__lock_owner = None
		self.__owner_acquisition_count = 0

	@property
	def owner(self):
		return self.__lock_owner

	def acquire(self):
		thread_id = Lock.get_thread_identity()

		if self.__lock_owner == thread_id:
			self.__owner_acquisition_count += 1
			return

		super().acquire()
		self.__lock_owner = thread_id

	def release(self):
		if self.__owner_acquisition_count:
			self.__owner_acquisition_count -= 1
			return

		self.__lock_owner = None
		super().release()

def get_args_for(fn, passed_args, passed_kwargs):
	inspection = inspect.getfullargspec(fn)

	args = []
	varargs = []
	kwargs = {}
	idx = 0
	for idx, arg in enumerate(inspection.args):
		try:
			args.append(passed_args[idx])
		except IndexError:
			for i in range(idx, len(inspection.args)):
				arg = inspection.args[i]
				try:
					kwargs[arg] = passed_kwargs[arg]
				except KeyError:
					pass
			break
	else:
		if inspection.varargs:
			varargs = list(passed_args[idx:])

	if inspection.varkw:
		kwargs = passed_kwargs
	else:
		for key in inspection.kwonlyargs:
			kwargs[key] = passed_kwargs[key]

	return args + list(varargs), kwargs

INVALIDATION_ON = '__latte_cache_invalidation'

def get_cache():
	global GLOBAL_REDIS_CACHE
	if (not GLOBAL_REDIS_CACHE):
		if redis_uri := local.conf.redis_big_cache:
			GLOBAL_REDIS_CACHE = RedisWrapper.from_url(redis_uri, socket_timeout=5, socket_connect_timeout=1)
			GLOBAL_REDIS_CACHE.__cache_uri = redis_uri
		else:
			GLOBAL_REDIS_CACHE = RedisWrapper.from_url(local.conf.redis_cache, socket_timeout=5, socket_connect_timeout=1)
			GLOBAL_REDIS_CACHE.__cache_uri = local.conf.redis_cache

	return GLOBAL_REDIS_CACHE
class MigratingException(Exception):
	pass

def cache_me_if_you_can(expiry=5, build_expiry=30, key=None, invalidate=None, nocache=None):
	def decorator(fn):
		method_name = f'{fn.__module__}.{fn.__qualname__}'

		@wraps(fn)
		def decorated(*args, **kwargs):
			new_args, new_kwargs = get_args_for(fn, args, kwargs)
			if (
				local.flags.in_migrate
				or local.flags.in_install_app
				or local.flags.in_install
				or (nocache and nocache(*new_args, **new_kwargs))
			):
				return fn(*new_args, **new_kwargs)

			if not hasattr(local, 'cache_access_time'):
				local.cache_access_time = 0

			logger = get_logger(index_name='cache_performance')
			site_slug = f'{local.site}|{method_name}'

			if key is not None:
				if isinstance(key, str):
					key_and_expiry = key
				else:
					key_and_expiry = key(*new_args, **new_kwargs)

				if isinstance(key_and_expiry, tuple):
					param_slug_string, _expiry = key_and_expiry
				elif isinstance(key_and_expiry, str):
					param_slug_string = key_and_expiry
					_expiry = expiry
				else:
					raise ValueError('Only string keys are allowed')

			else:
				param_slug_string = frappe.as_json(args) + frappe.as_json(kwargs)
				_expiry = expiry

			slug = xxh64_hexdigest(param_slug_string.encode()) + '|' + site_slug + '|' + str(len(param_slug_string))

			cache_queue = local.building_cache_for = getattr(local, 'building_cache_for', None) or set()

			if slug in cache_queue: # Recursive call
				raise RecursiveCall(f'''
					Recursive call while building same slug in cache:
					{slug=}
					{site_slug=}
					{param_slug_string=}
				''')

			cache = get_cache()

			if invalidate is not None:
				if callable(invalidate):
					invalidate_key = invalidate(*new_args, **new_kwargs)
				else:
					invalidate_key = invalidate
			else:
				invalidate_key = None

			cache_time_start = perf_counter()
			try:
				cached_value = cache.get(slug, shard_key=invalidate_key, probe_on_error=True)
				if (cached_value != PENDING) and (cached_value is not None):
					logger.info({
						'cache_key': slug,
						'status': 'HIT',
						'method_name': method_name,
						'lock': 0,
						'size': len(cached_value),
						'param_slug_string': param_slug_string if key else '',
					})
					return pickle.loads(cached_value)

			except Disconnected as e:
				print(f'Failed to connect to redis {getattr(cache, "identity", "big_cache")}, emulating cache miss', e)
				local.cache_access_time += perf_counter() - cache_time_start
				return fn(*new_args, **new_kwargs)

			cached_value = PENDING
			breakctr = build_expiry or 10
			cache_time_start = perf_counter()
			exclusive = cache.set(slug, PENDING, nx=True, ex=build_expiry, shard_key=invalidate_key)
			# print('Got exclusive lock?', slug, exclusive, local.flags.request_id)
			# if 'cache_access_time' not in local:
			# 	local.cache_access_time = 0
			local.cache_access_time += perf_counter() - cache_time_start
			while (not exclusive) and cached_value == PENDING and breakctr:
				breakctr -= 1
				cache_time_start = perf_counter()
				cached_value = cache.get(slug, shard_key=invalidate_key)
				local.cache_access_time += perf_counter() - cache_time_start
				# print('Am i pending', slug, cached_value == PENDING)
				if cached_value == PENDING:
					gevent.sleep(1)
					continue
				elif not cached_value:
					break
				else:
					logger.info({
						'cache_key': slug,
						'status': 'HIT',
						'method_name': method_name,
						'lock': 1,
						'size': len(cached_value),
						'param_slug_string': param_slug_string if key else '',
					})
					return pickle.loads(cached_value)

			try:
				cache_queue.add(slug)
				response = fn(*new_args, **new_kwargs)
				cached_value = pickle.dumps(response)

				cache_time_start = perf_counter()

				cache.set(
					slug,
					cached_value,
					ex=(_expiry or None),
					shard_key=invalidate_key,
					invalidate_key=invalidate_key,
				)
				local.cache_access_time += perf_counter() - cache_time_start

				# if invalidate:
				# 	invalidate_key = invalidate if isinstance(invalidate, str) else invalidate(*new_args, **new_kwargs)
				# 	pipeline = cache.pipeline()
				# 	pipeline.set(slug, cached_value, ex=(_expiry or None))
				# 	pipeline.sadd(f'__cache_invalidate|{local.site}|{invalidate_key}', slug)
				# 	cache_time_start = perf_counter()
				# 	pipeline.execute()
				# 	local.cache_access_time += perf_counter() - cache_time_start
				# else:
				# 	cache_time_start = perf_counter()
				# 	cache.set(slug, cached_value, ex=(_expiry or None))
				# 	local.cache_access_time += perf_counter() - cache_time_start

				logger.info({
					'cache_key': slug,
					'status': 'MISS',
					'method_name': method_name,
					'size': len(cached_value),
					'param_slug_string': param_slug_string if key else '',
				})

				return response
			except:
				cache_time_start = perf_counter()
				cache.delete(slug, shard_key=invalidate_key)
				local.cache_access_time += perf_counter() - cache_time_start
				raise
			finally:
				cache_queue.discard(slug)

		return decorated
	return decorator

def invalidate(key):
	invalidate_wrapped(key)
	frappe.db.run_after_commit(invalidate_wrapped, key)

def invalidate_wrapped(key):
	try:
		get_cache().invalidate(key)
	except (ConnectionError, TimeoutError, ResponseError):
		pass

def invalidate_by_key(fn_path, key):
	try:
		get_cache().delete(xxh64_hexdigest(key.encode()) + '|' + local.site + '|' + fn_path + '|' + str(len(key)))
	except (ConnectionError, TimeoutError, ResponseError):
		pass

RUNNING_CACHE = {}
CACHE = {}
GC_MAP = {}
INVALIDATE_MAP = {}
CLEAR_CACHE_EVERY = 15 * 60

def cache_in_mem(key=None, site_scoped=True, timeout=None, lock_cache=False, invalidate=None, no_cache=None, postprocess=None):
	def decorator(fn):
		@wraps(fn)
		def decorated(*args, **kwargs):
			if callable(no_cache) and no_cache(*args, **kwargs):
				return fn(*args, **kwargs)

			cache_key = f'{fn.__module__}.{fn.__qualname__}|{key(*args, **kwargs) if key else ""}'
			if site_scoped:
				cache_key = f'{local.site}_{cache_key}'

			try:
				cache_time, value = CACHE[cache_key]
				if timeout and (perf_counter() - cache_time) > timeout:
					del GC_MAP[cache_key] #this can also raise a KeyError
					raise KeyError

				return value

			except KeyError:
				if lock_cache:
					try:
						cache_lock = RUNNING_CACHE[cache_key]
						if Lock.get_thread_identity() == cache_lock.owner:
							raise KeyError

						cache_lock.acquire()
						try:
							_, value = CACHE[cache_key]
							return value
						except KeyError:
							RUNNING_CACHE.pop(cache_key, None)
							raise Exception('Cache key missing even after waiting for runner')
						finally:
							cache_lock.release()

					except KeyError:
						cache_lock = RUNNING_CACHE[cache_key] = Lock()
						cache_lock.acquire()
						try:
							# value = CACHE[cache_key] = (perf_counter(), fn(*args, **kwargs),)
							value = add_to_cache(cache_key, timeout, fn, args, kwargs, invalidate, postprocess)
						finally:
							cache_lock.release()
							RUNNING_CACHE.pop(cache_key, None)

						return value

				else:
					# value = fn(*args, **kwargs)
					# CACHE[cache_key] = (perf_counter(), value,)
					value = add_to_cache(cache_key, timeout, fn, args, kwargs, invalidate, postprocess)
					return value

		return decorated
	return decorator

def add_to_cache(key, timeout, fn, args, kwargs, invalidate, postprocess):
	value = fn(*args, **kwargs)
	if postprocess:
		value = postprocess(value)

	timestamp = perf_counter()
	CACHE[key] = (timestamp, value,)
	if timeout:
		GC_MAP[key] = (timestamp + timeout)

	if invalidate:
		invalidate_key = RedisWrapper.get_invalidate_key(invalidate(*args, **kwargs))
		if not (invalidate_set := INVALIDATE_MAP.get(invalidate_key)):
			invalidate_set = INVALIDATE_MAP[invalidate_key] = set()
		invalidate_set.add(key)

	return value

def cache_invalidation_listener():
	latte.init(site='')
	pubsub = Redis.from_url(get_cache().__cache_uri).pubsub()
	pubsub.subscribe([INVALIDATION_ON])
	try:
		print('SUBSCRIBING')
		for item in pubsub.listen():
			if item['type'] == 'message':
				invalidate_key = str(item['data'], 'utf-8')
				if invalidate_key == 'flushall':
					CACHE.clear()
					GC_MAP.clear()
					INVALIDATE_MAP.clear()
				elif invalidate_set := INVALIDATE_MAP.get(invalidate_key):
					for key in invalidate_set:
						# print('Popping', key)
						CACHE.pop(key, None)
					INVALIDATE_MAP.pop(invalidate_key, None)

	except Exception as e:
		print('Invalidation Subscription failed', e)
		gevent.sleep(5)
		gevent.spawn(cache_invalidation_listener)

gevent.spawn(cache_invalidation_listener)

def collect_garbage():
	cur_timestamp = perf_counter()
	to_pop = []
	for key, timeout in GC_MAP.items():
		# print(key, timeout, cur_timestamp)
		if timeout < cur_timestamp:
			to_pop.append(key)
		else:
			break

	for key in to_pop:
		CACHE.pop(key, None)
		del GC_MAP[key]

def gc_orchestrator():
	while True:
		gevent.sleep(CLEAR_CACHE_EVERY)
		try:
			collect_garbage()
		except:
			traceback.print_exc()

gevent.spawn(gc_orchestrator)

def cache_in_local(key):
	def decorator(fn):
		@wraps(fn)
		def decorated(*args, **kwargs):
			try:
				local_cache = local.latte_cache
			except AttributeError:
				local_cache = local.latte_cache = {}

			cache_key = fn.__module__ + '|' + fn.__qualname__ + '|' + (key(*args, **kwargs) if key else '')

			if cache_key in local_cache:
				return local_cache[cache_key]
			else:
				retval = local_cache[cache_key] = fn(*args, **kwargs)
				return retval

		return decorated
	return decorator

def flushall(*_, **__):
	Balancer.flushall()
	try:
		big_cache = get_cache()
		big_cache.flushall()
		big_cache.publish(INVALIDATION_ON, 'flushall')
	except (ConnectionError, TimeoutError):
		pass
	try:
		frappe.cache().flushall()
	except (ConnectionError, TimeoutError):
		pass


class RedisWrapper(Redis):
	"""Redis client that will automatically prefix conf.db_name"""
	def connected(self):
		try:
			self.ping()
			return True
		except (ConnectionError, TimeoutError):
			return False

	@staticmethod
	def get_hash_key(hashname, key):

		if isinstance(hashname, bytes):
			hashname = str(hashname, 'utf-8')

		if isinstance(key, bytes):
			key = str(key, 'utf-8')

		return f'hash|{hashname}|{key}'

	def make_key(self, key, user=None, shared=False):
		if shared:
			return key
		if user:
			if user == True:
				user = local.session.user

			key = f"user:{user}:{key}"

		return f"{local.conf.db_name}|{key}".encode('utf-8')

	def set_value(self, key, val, user=None, expires_in_sec=None):
		"""Sets cache value.

		:param key: Cache key
		:param val: Value to be cached
		:param user: Prepends key with User
		:param expires_in_sec: Expire value of this key in X seconds
		"""
		key = self.make_key(key, user)

		if not expires_in_sec:
			local.cache[key] = val

		try:
			self.set(key, pickle.dumps(val), ex=expires_in_sec)

		except (ConnectionError, TimeoutError):
			return None

	def get_value(self, key, generator=None, user=None, expires=False):
		"""Returns cache value. If not found and generator function is
			given, it will call the generator.

		:param key: Cache key.
		:param generator: Function to be called to generate a value if `None` is returned.
		:param expires: If the key is supposed to be with an expiry, don't store it in local
		"""
		original_key = key
		key = self.make_key(key, user)

		val = None
		try:
			val = local.cache[key]

		except KeyError:
			try:
				val = self.get(key)
			except (ConnectionError, TimeoutError):
				pass

			if val is not None:
				val = pickle.loads(val)

			if not expires:
				if val is None and generator:
					val = generator()
					self.set_value(original_key, val, user=user)

				else:
					local.cache[key] = val

		return val

	def get_all(self, key):
		ret = {}
		for k in self.get_keys(key):
			ret[key] = self.get_value(k)

		return ret

	def get_keys(self, key):
		"""Return keys starting with `key`."""
		try:
			key = self.make_key(key + "*")
			return self.keys(key)

		except (ConnectionError, TimeoutError):
			regex = re.compile(cstr(key).replace("|", "\|").replace("*", "[\w]*"))
			return [k for k in list(local.cache) if regex.match(k.decode())]

	def delete_keys(self, key):
		"""Delete keys with wildcard `*`."""
		try:
			self.delete_value(self.get_keys(key), make_keys=False)
		except (ConnectionError, TimeoutError):
			pass

	def delete_key(self, *args, **kwargs):
		self.delete_value(*args, **kwargs)

	def delete_value(self, keys, user=None, make_keys=True, shared=False):
		"""Delete value, list of values."""
		if not isinstance(keys, (list, tuple)):
			keys = (keys, )

		for key in keys:
			if make_keys:
				key = self.make_key(key, shared=shared)

			if key in local.cache:
				del local.cache[key]

			try:
				self.delete(key)
			except (ConnectionError, TimeoutError):
				pass

	def lpush(self, key, value):
		super().lpush(self.make_key(key), value)

	def rpush(self, key, value):
		super().rpush(self.make_key(key), value)

	def lpop(self, key):
		return super().lpop(self.make_key(key))

	def llen(self, key):
		return super().llen(self.make_key(key))

	def hset(self, name, key, value, shared=False):
		_name = self.make_key(name, shared=shared)

		# set in local
		if not _name in local.cache:
			local.cache[_name] = {}
		local.cache[_name][key] = value

		hash_key = RedisWrapper.get_hash_key(_name, key)

		# set in redis
		try:
			super().set(hash_key, pickle.dumps(value))
		except (ConnectionError, TimeoutError):
			pass

	def hgetall(self, name):
		hash_name = self.make_key(name)
		hash_keys_pattern = f'hash|{hash_name}|*'
		keys = self.keys(hash_keys_pattern)
		return {
			key[len(hash_keys_pattern) - 1]: pickle.loads(super().get(key))
			for key in keys
		}

	def hget(self, name, key, generator=None, shared=False):
		_name = self.make_key(name, shared=shared)
		if not _name in local.cache:
			local.cache[_name] = {}

		if key in local.cache[_name]:
			return local.cache[_name][key]

		value = None
		hash_key = RedisWrapper.get_hash_key(_name, key)
		try:
			value = super().get(hash_key)
		except (ConnectionError, TimeoutError):
			pass

		if value:
			value = pickle.loads(value)
			local.cache[_name][key] = value
		elif generator:
			value = generator()
			try:
				super().set(hash_key, pickle.dumps(value))
			except (ConnectionError, TimeoutError):
				pass
		return value

	def hdel(self, name, key, shared=False):
		_name = self.make_key(name, shared=shared)

		hash_key = RedisWrapper.get_hash_key(_name, key)

		if _name in local.cache:
			if key in local.cache[_name]:
				del local.cache[_name][key]
		try:
			super().delete(hash_key)
		except (ConnectionError, TimeoutError):
			pass

	def hdel_keys(self, name_starts_with, key):
		raise NotImplementedError

		# """Delete hash names with wildcard `*` and key"""
		# for name in frappe.cache().get_keys(name_starts_with):
		# 	name = name.split("|", 1)[1]
		# 	self.hdel(name, key)

	def hkeys(self, name):
		raise NotImplementedError

		# try:
		# 	return super(RedisWrapper, self).hkeys(self.make_key(name))
		# except (ConnectionError, TimeoutError):
		# 	return []

	def sadd(self, name, *values):
		"""Add a member/members to a given set"""
		super().sadd(self.make_key(name), *values)

	def srem(self, name, *values):
		"""Remove a specific member/list of members from the set"""
		super().srem(self.make_key(name), *values)

	def sismember(self, name, value):
		"""Returns True or False based on if a given value is present in the set"""
		return super().sismember(self.make_key(name), value)

	def spop(self, name):
		"""Removes and returns a random member from the set"""
		return super().spop(self.make_key(name))

	def srandmember(self, name, count=None):
		"""Returns a random member from the set"""
		return super().srandmember(self.make_key(name))

	def smembers(self, name):
		"""Return all members of the set"""
		return super().smembers(self.make_key(name))

	def setex(self, key, value, time):
		return self.set(key, value, ex=time)

	@staticmethod
	def get_invalidate_key(key):
		return f'__cache_invalidate|{local.site}|{key}'.replace('"', '\\"')

	def invalidate(self, key):
		invalidate_key = RedisWrapper.get_invalidate_key(key)
		cache = Balancer.get_rr_cache_url(key)
		# print('invalidating on', cache.identity, invalidate_key)
		logger = get_logger(index_name='cache_invalidation')
		stack_trace = '\n'.join(
			f'{frame.f_code.co_filename} | {frame.f_code.co_name} | {lineno}'
			for frame, lineno in
			walk_stack(None)
		)
		logger.info({
			'key': str(key),
			'stack': stack_trace,
		})
		cache.invalidator([invalidate_key])
		self.publish(INVALIDATION_ON, invalidate_key)

	def incr(self, key, amount=1, shard_key=None):
		perf_start = perf_counter()
		cache = Balancer.get_rr_cache_url(shard_key or key)
		retval = cache.incr(key, amount)
		perf_time = perf_counter() - perf_start
		local.cache_balancer_time = getattr(local, 'cache_balancer_time', 0) + perf_time
		logger = get_logger(index_name='redis_balancer')
		logger.info({
			'key': str(key),
			'redis_method': 'INCR',
			'identity': cache.identity,
			'time_taken': perf_time,
		})
		return retval

	incrby = incr

	def incrbyfloat(self, key, amount=1.0, shard_key=None):
		perf_start = perf_counter()
		cache = Balancer.get_rr_cache_url(shard_key or key)
		retval = cache.incrbyfloat(key, amount)
		perf_time = perf_counter() - perf_start
		local.cache_balancer_time = getattr(local, 'cache_balancer_time', 0) + perf_time
		logger = get_logger(index_name='redis_balancer')
		logger.info({
			'key': str(key),
			'redis_method': 'INCRBYFLOAT',
			'identity': cache.identity,
			'time_taken': perf_time,
		})
		return retval

	def set(self, key, value, *args, shard_key=None, invalidate_key=None, **kwargs):
		perf_start = perf_counter()
		cache = Balancer.get_rr_cache_url(shard_key or key)
		if invalidate_key:
			invalidate_key = RedisWrapper.get_invalidate_key(invalidate_key)
			# print('setting invalidate on', cache.identity, invalidate_key)
			pipeline = cache.pipeline()
			pipeline.set(key, value, *args, **kwargs)
			pipeline.sadd(invalidate_key, key)
			pipeline.execute()
			retval = None
		else:
			retval = cache.set(key, value, *args, **kwargs)

		perf_time = perf_counter() - perf_start
		local.cache_balancer_time = getattr(local, 'cache_balancer_time', 0) + perf_time
		logger = get_logger(index_name='redis_balancer')
		logger.info({
			'key': str(key),
			'redis_method': 'SET',
			'identity': cache.identity,
			'time_taken': perf_time,
		})
		return retval

	def get(self, key, *args, shard_key=None, probe_on_error=False, **kwargs):
		perf_start = perf_counter()
		cache = Balancer.get_rr_cache_url(shard_key or key)
		try:
			retval = cache.get(key, *args, **kwargs)
		except Disconnected:
			if probe_on_error:
				raise
			raise ConnectionError
		except (TimeoutError, ResponseError, ConnectionError) as e:
			print(f'Connection Error in {cache.identity}:', e)
			if probe_on_error:
				Balancer.disconnect_and_probe(cache)
				raise Disconnected
			raise

		perf_time = perf_counter() - perf_start
		local.cache_balancer_time = getattr(local, 'cache_balancer_time', 0) + perf_time
		logger = get_logger(index_name='redis_balancer')
		logger.info({
			'key': str(key),
			'redis_method': 'GET',
			'identity': cache.identity,
			'time_taken': perf_time,
		})
		return retval

	def delete(self, key, *args, shard_key=None, **kwargs):
		perf_start = perf_counter()
		cache = Balancer.get_rr_cache_url(shard_key or key)
		retval = cache.delete(key)
		perf_time = perf_counter() - perf_start
		local.cache_balancer_time = getattr(local, 'cache_balancer_time', 0) + perf_time
		logger = get_logger(index_name='redis_balancer')
		logger.info({
			'key': str(key),
			'redis_method': 'DELETE',
			'identity': cache.identity,
			'time_taken': perf_time,
		})
		return retval

class Balancer(object):
	'''
		Return a connection appropriate for a given key to
	'''

	INSTANCES = {}

	DEFAULT_CACHE = None

	@staticmethod
	def get_default_cache():
		if Balancer.DEFAULT_CACHE:
			return Balancer.DEFAULT_CACHE

		Balancer.DEFAULT_CACHE = Redis(**get_cache().connection_pool.connection_kwargs)
		Balancer.register_invalidator(Balancer.DEFAULT_CACHE)
		Balancer.set_identity(Balancer.DEFAULT_CACHE)

		return Balancer.DEFAULT_CACHE

	@staticmethod
	def get_rr_cache_url(shard_key):
		if not (active_instances := local.conf.redis_caches):
			return Balancer.get_default_cache()

		intkey = xxh64_intdigest(shard_key)
		modulo_on = len(active_instances)
		conn_index = intkey % modulo_on
		cache_url = active_instances[conn_index]
		# print('shard key', shard_key, cache_url)
		if cache_url in Balancer.INSTANCES:
			return Balancer.INSTANCES[cache_url]
		else:
			cache = Balancer.INSTANCES[cache_url] = Redis.from_url(
				cache_url,
				socket_timeout=5,
				socket_connect_timeout=1,
			)

			Balancer.register_invalidator(cache)
			Balancer.set_identity(cache)
			return cache

	@staticmethod
	def set_identity(cache):
		conn_kwargs = cache.connection_pool.connection_kwargs
		cache.identity = f'{conn_kwargs["host"]}:{conn_kwargs["port"]}'

	@staticmethod
	def register_invalidator(cache):
		invalidate_script = f'''
			for _, key in ipairs(redis.call("smembers", KEYS[1])) do
				redis.call('del', key)
			end
			redis.call('del', KEYS[1])
		'''
		cache.invalidator = cache.register_script(invalidate_script)
		cache.old_get = cache.get

	@staticmethod
	def disconnect_and_probe(cache):
		Balancer.probing = True
		print('Disconnected')
		def new_get(*args, **kwargs):
			raise Disconnected(f'{cache.identity} Disconnected')

		cache.get = new_get
		gevent.spawn(redis_probe)

	@staticmethod
	def flushall():
		if not local.conf.redis_caches:
			return

		for uri in list(local.conf.redis_caches):
			try:
				# print('Flushing', uri)
				Redis.from_url(
					uri,
					socket_timeout=5,
					socket_connect_timeout=1,
				).flushall()
			except Exception as e:
				print('Warning: Unable to flush', uri, 'due to', e, file=sys.stderr)
				if (local.flags.in_migrate
				or local.flags.in_install_app
				or local.flags.in_install):
					local.conf.redis_caches.remove(uri)

def redis_probe(cache):
	for i in range(5):
		try:
			cache.ping()
		except Exception as e:
			print(f'Cache connection failed', e, file=sys.stderr)
			gevent.sleep(5)
		else:
			cache.get = cache.old_get
			return

	cache.get = cache.old_get
