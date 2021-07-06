from werkzeug.local import Local
import latte
import os
import greenlet
from frappe import local
from time import perf_counter
from gevent import hub

if os.environ.get('PATCH_WERKZEUG_LOCAL'):
	slots = [
		'error_log', 'message_log', 'debug_log', 'realtime_log',
		'flags', 'rollback_observers', 'test_objects', 'site',
		'sites_path', 'site_path', 'request_ip', 'response',
		'task_id', 'conf', 'lang', 'lang_full_dict', 'module_app',
		'app_modules', 'system_settings', 'user', 'user_perms',
		'session', 'role_permissions', 'valid_columns', 'new_doc_templates',
		'link_count', 'jenv', 'jloader', 'cache', 'document_cache',
		'meta_cache', 'form_dict', 'sql_time', 'initialised', 'db',
		'touch', 'request', 'is_ajax', 'ignore_2fa',
		'cookie_manager', 'user_lang', 'session_obj', 'login_manager',
		'http_request', 'user_format', 'building_cache_for', 'sql_time',
		'sql_logging_time', 'cache_access_time', 'append_statement_to_query',
		'sql_selects', 'sql_updates', 'sql_deletes', 'sql_inserts',
		'cache_balancer_time', 'greenlet_time', 'greenlet_start',
	]
	slotted_class = latte.get_slotted_class(slots, dict_needed=True)

	def slotted_dict_maker(self, name, value):
		ident = self.__ident_func__()
		storage = local.__storage__
		try:
			# storage[ident][name] = value
			storage[ident].__setattr__(name, value)
		except KeyError:
			# storage[ident] = {name: value}
			thread_local = storage[ident] = slotted_class()
			thread_local.__setattr__(name, value)

	Local.__setattr__ = slotted_dict_maker

	def getattribute(self, key):
		return self.__storage__[self.__ident_func__()].__getattribute__(key)
	Local.__getattr__ = getattribute

	storage = local.__storage__
	def callback(event, args):
		if event in ('switch', 'throw'):
			origin, target = args
			if origin is not hub and (origin_greenlet := storage.get(origin)):
				origin_greenlet.greenlet_time += (perf_counter() - origin_greenlet.greenlet_start)

			if target is not hub and (target_greenlet := storage.get(target)):
				target_greenlet.greenlet_start = perf_counter()

	greenlet.settrace(callback)
