
from functools import wraps
from os import read
from random import choice
import frappe
import datetime
from latte.utils.caching import cache_me_if_you_can, get_args_for, cache_in_mem, get_cache
from latte.database_utils.connection_pool import PatchedDatabase
from frappe import call, local
import inspect

def read_only(key=None, force_primary=False, replica_priority=None):
	def decorator(fn):
		method = f'{fn.__module__}.{fn.__qualname__}'
		@wraps(fn)
		def decorated(*args, **kwargs):

			new_args, new_kwargs = get_args_for(fn, args, kwargs)

			if isinstance(key, int):
				acceptable_data_lag = key
			elif not key:
				acceptable_data_lag = local.conf.acceptable_replica_lag or 30
			elif callable(key):
				acceptable_data_lag = key(*new_args, **new_kwargs) or 1200
			else:
				acceptable_data_lag = 1200

			did_i_set_replica = False
			method_priority = None
			if acceptable_data_lag and not local.flags.replica_is_set:
				if (method_priority := decide_priority(fn)) is None:
					if isinstance(replica_priority, int):
						method_priority = replica_priority
					elif callable(replica_priority):
						if (method_priority := replica_priority(*new_args, **new_kwargs)) is None:
							method_priority = 0
					else:
						method_priority = 0

				local.flags.replica_is_set = did_i_set_replica = \
					connect_to_replica(acceptable_data_lag, force_primary, method_priority)

			try:
				retval = fn(*new_args, **new_kwargs)
			finally:
				if did_i_set_replica:
					slave_db = local.slave_db
					local.read_only_db_logs.append({
						'method': method,
						'db': f'{slave_db.host}:{slave_db.port}',
						'method_priority': method_priority,
					})
					slave_db.close()
					local.db = local.primary_db
					local.flags.replica_is_set = False

			return retval
		return decorated
	return decorator

def decide_priority(fn):
	'''
		Deciding logic for which method
		returns 1 (highest priority) by default

		selected functions can be in site_config with some priority 1-100

		1-100 can be considered the speed for now... like 1 fns are very transactional and fast,
		whereas the bigger number represents vastness of a method, like a big report or dashboard

		local.conf.method_replica_priority will be hardcoded at first... and then will slowly be more intelligent

		Site Config
		conf.method_replica_priority = {
			"frappe.ping": 1,
			"withrun.ping": 10
		}
	'''

	if not (decided_fns := local.conf.method_replica_priority):
		return

	qual_name = f"{fn.__module__}.{fn.__qualname__}"
	if qual_name in decided_fns:
		return decided_fns[qual_name]

	return

def connect_to_replica(acceptable_data_lag=0, force_primary=False, priority=None):
	if hasattr(frappe.local, 'slave_db') and frappe.local.db is frappe.local.slave_db:
		return

	db_choices = get_relevant_replicas(acceptable_data_lag, priority)

	if (not db_choices) and (force_primary or not local.conf.no_shift_to_primary_on_lag):
		return

	sticky_replica = get_sticky_replica()

	if sticky_replica not in db_choices:
		sticky_replica = assign_sticky_replica(db_choices)

	# print('Assigned sticky replica', sticky_replica)
	if not sticky_replica:
		return

	frappe.local.slave_db = PatchedDatabase(
		host=sticky_replica[0],
		port=sticky_replica[1],
		read_only_session=True,
	)
	frappe.local.slave_db.read_only = True

	# assign slave db
	frappe.local.db = frappe.local.slave_db
	frappe.local.db.connect()
	return True

def get_relevant_replicas(acceptable_data_lag, method_priority=None):
	'''
		Returns replica(s) based on the given params.
		If acceptable_data_lag: Decide replicas based on lag.
		If method_priority: Decide replica based on method_priority
	'''
	replica_details = get_all_replica_details()
	db_choices = []

	priority_wise_replicas = []
	if (method_priority is not None and replica_details):
		priority_wise_replicas = prioritise_db_choices(replica_details, method_priority)

	for replica in (priority_wise_replicas or replica_details or []):
		if replica.lag <= acceptable_data_lag:
			db_choices.append((replica['host'], replica['port'],))

	return db_choices

def prioritise_db_choices(replica_details, needed_priority):
	'''
		logic to assign priority from to the given db choices
		0 => Highest Priority, RR between good servers
		1 => Low Priority, RR between bad servers
	'''

	if needed_priority == 0:
		return [row for row in replica_details if row.get('priority') == 'low']
	elif needed_priority == 1:
		return [row for row in replica_details if row.get('priority') != 'low']

	return replica_details

@cache_in_mem(timeout=30)
@cache_me_if_you_can(expiry=60)
def get_all_replica_details():
	replica_details = []
	# get all replicas lag and return replica details with < lag
	pool_configs = local.conf.slave_db_pool
	if not pool_configs:
		return

	for config in pool_configs:
		user = frappe.conf.db_replication_client_user
		password = frappe.conf.db_replication_client_password
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
			# print(frappe.get_traceback())
		finally:
			db.close()

		if (not (slave_status and slave_status[0])):
			slave_lag = float('inf')

		elif (slave_status[0].get('Seconds_Behind_Master') is None):
			last_success_lag = frappe.cache().get(f'__LAST_SUCCESS_HIT_REPLICA:{slave_host}:{slave_port}')
			if not last_success_lag:
				slave_lag = float('inf')
			else:
				last_hit, slave_lag = last_success_lag.decode('utf-8').split('|')
				last_hit = datetime.datetime.strptime(last_hit, frappe.utils.DATETIME_FORMAT)
				slave_lag = (frappe.utils.now_datetime() - last_hit).total_seconds() + int(slave_lag)
		else:
			slave_lag = slave_status[0].get('Seconds_Behind_Master')
			frappe.cache().set(
				f'__LAST_SUCCESS_HIT_REPLICA:{slave_host}:{slave_port}',
				f'{frappe.utils.get_datetime_str(frappe.utils.now_datetime())}|{slave_lag}'
			)

		config = frappe._dict(config)
		config.lag = slave_lag

		replica_details.append(config)

	replica_details.sort(key=lambda x: x.lag, reverse=True)

	return replica_details

def get_sticky_replica():
	if local.conf.replica_stickiness and (user := local.session.user.lower()) not in ('administrator', 'guest'):
		if cached_val := get_cache().get(f'sticky_replica|{user}'):
			sticky_replica_arr = str(cached_val, 'utf-8').split('|')
			sticky_replica = (sticky_replica_arr[0], int(sticky_replica_arr[1]),)
			return sticky_replica

def assign_sticky_replica(db_choices):
	if not db_choices:
		db_choices = [(replica['host'], replica['port'],) for replica in (get_all_replica_details() or [])]

	if not db_choices:
		return

	connect_host, connect_port = choice(db_choices)
	if local.conf.replica_stickiness and ((user := local.session.user.lower()) not in ('administrator', 'guest')):
		get_cache().set(f'sticky_replica|{user}', f'{connect_host}|{connect_port}', ex=3600)

	return connect_host, connect_port
