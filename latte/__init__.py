# -*- coding: utf-8 -*-
from __future__ import unicode_literals


import frappe

__version__ = '2.0.0'
import os
import sys
import gevent
import latte.auth
from frappe import local, setup_module_map as frappe_setup_module_map, get_file_json, set_user
from latte.dict import _dict, dict
from latte.database_utils.connection_pool import PatchedDatabase as Database
from latte.utils.caching import cache_in_mem
from latte.utils.connect_replica import read_only
from google.auth.exceptions import DefaultCredentialsError
from werkzeug.local import release_local
from latte.utils.mqtt import publish_mqtt
from time import perf_counter

def init(site, sites_path=None, new_site=False, force=False):
	"""Initialize frappe for the current site. Reset thread locals `frappe.local`"""
	local.touch = True
	if getattr(local, "initialised", None) and not force:
		return

	if not sites_path:
		sites_path = '.'

	local.error_log = []
	local.message_log = []
	local.debug_log = []
	local.realtime_log = []
	local.flags = _dict({
		"ran_schedulers": [],
		"currently_saving": [],
		"redirect_location": "",
		"in_install_db": False,
		"in_install_app": False,
		"in_import": False,
		"in_test": False,
		"mute_messages": False,
		"ignore_links": False,
		"mute_emails": False,
		"has_dataurl": False,
		"new_site": new_site,
		"log_identity": "",
	})
	local.rollback_observers = []
	local.test_objects = {}

	local.site = site
	local.sites_path = sites_path
	local.site_path = os.path.join(sites_path, site)

	local.request_ip = None
	local.response = _dict({"docs":[]})
	local.task_id = None

	local.conf = get_site_config(force=force)
	local.lang = local.conf.lang or "en"
	local.lang_full_dict = None

	local.module_app = None
	local.app_modules = None
	local.system_settings = _dict()

	local.user = None
	local.user_perms = None
	local.session = None
	local.role_permissions = {}
	local.valid_columns = {}
	local.new_doc_templates = {}
	local.link_count = {}

	local.jenv = None
	local.jloader = None
	local.cache = {}
	local.latte_cache = {}
	local.document_cache = {}
	local.meta_cache = {}
	local.form_dict = _dict()
	local.session = _dict()
	local.sql_time = 0
	local.greenlet_start = perf_counter()
	local.greenlet_time = 0
	local.sql_logging_time = 0
	local.cache_access_time = 0
	local.cache_balancer_time = 0
	local.sql_selects = 0
	local.sql_updates = 0
	local.sql_deletes = 0
	local.sql_inserts = 0
	local.read_only_db_logs = []
	local.append_statement_to_query = ''
	local.sql_running = False

	setup_module_map()
	local.initialised = True

def migrating():
	return (
		local.flags.in_migrate
		or local.flags.in_install_app
		or local.flags.in_install
	)

@cache_in_mem(
	key=lambda sites_path=None,**__: f'{sites_path or ""}_SITE_CONFIG',
	timeout=10,
	lock_cache=True,
	no_cache=lambda force=False, **__: force,
)
def get_site_config(sites_path=None, site_path=None, force=False):
	"""Returns `site_config.json` combined with `sites/common_site_config.json`.
	`site_config` is a set of site wide settings like database name, password, email etc."""
	config = {}

	sites_path = sites_path or getattr(local, "sites_path", None)
	site_path = site_path or getattr(local, "site_path", None)

	if sites_path:
		common_site_config = os.path.join(sites_path, "common_site_config.json")
		if os.path.exists(common_site_config):
			config.update(get_file_json(common_site_config))

	if site_path:
		site_config = os.path.join(site_path, "site_config.json")
		if os.path.exists(site_config):
			config.update(get_file_json(site_config))
		elif local.site and not local.flags.new_site:
			print(f"{local.site} does not exist")
			sys.exit(1)
	return get_slotted_dict(config, extra_slots=[
		'admin_password',
		'developer_mode',
	])

def get_slotted_dict(config, extra_slots=[]):
	slotted_class = get_slotted_class(list(config), extra_slots=extra_slots)
	conf = slotted_class()

	for key, value in config.items():
		if isinstance(value, dict):
			conf[key] = get_slotted_dict(value)
		else:
			conf[key] = value

	return conf

def get_slotted_class(slots, dict_needed=False, extra_slots=[]):
	try:
		good_keys = []
		for key in slots:
			if key.isidentifier() and not key.startswith('__'):
				good_keys.append(key)
			else:
				dict_needed = True

		if not (dict_needed or good_keys):
			return _dict

		if dict_needed or migrating():
			good_keys += ['__dict__']

		good_keys += extra_slots

		class Slotted(object):
			__slots__ = list(set(good_keys))

			def __contains__(self, key):
				try:
					self.__getattr__(key, throws=True)
					return True
				except AttributeError:
					return False

			def __setitem__(self, key, value):
				return self.__setattr__(key, value)

			def __getattr__(self, key, throws=False):
				try:
					return super().__getattribute__(key)
				except AttributeError:
					if throws:
						raise

			def get(self, key, default=None):
				try:
					return super().__getattribute__(key)
				except AttributeError:
					return default

			def __getitem__(self, key):
				try:
					return super().__getattribute__(key)
				except AttributeError:
					raise KeyError(key)

			def __iter__(self):
				if self.__dict__ is None:
					return iter(self.__slots__)
				else:
					return iter(self.__slots__[:-1] + list(self.__dict__.keys()))

			def __repr__(self):
				return str({
					key: getattr(self, key) for key in self
				})

			def __str__(self):
				return self.__repr__()

			def __len__(self):
				if self.__dict__ is None:
					return len(self.__slots__)
				else:
					return len(self.__slots__) + len(self.__dict__) - 1

			def items(self):
				return (
					(k, self[k]) for k in self
				)

			def keys(self):
				return list(self)

			def values(self):
				return (self[k] for k in self)

		return Slotted
	except TypeError:
		return _dict

def setup_module_map():
	local.app_modules, local.module_app = get_module_meta()

@cache_in_mem(timeout=360, lock_cache=True)
def get_module_meta():
	frappe_setup_module_map()
	return (local.app_modules, local.module_app,)

profiler_started = False
def connect(site=None, db_name=None, admin=True):
	global profiler_started
	"""Connect to site database instance.

	:param site: If site is given, calls `frappe.init`.
	:param db_name: Optional. Will use from `site_config.json`."""
	if site:
		init(site)

	if not profiler_started and local.conf.stackdriver_profile:
		profiler_started = True
		gevent.spawn(
			start_stackdriver_profiler,
			**local.conf.stackdriver_profile
		)

	local.primary_db = local.db = Database(autocommit=local.flags.sessionless)
	local.db.connect()

	if admin:
		set_user("Administrator")

def destroy():
	if hasattr(local, 'db'):
		local.db.close()

	if hasattr(local, 'analysis_db'):
		local.analysis_db.close()

	release_local(local)

import latte.monkey_patches

def start_stackdriver_profiler(service, verbosity, project_id):
	import googlecloudprofiler
	# Profiler initialization. It starts a daemon thread which continuously
	# collects and uploads profiles. Best done as early as possible.
	try:
		googlecloudprofiler.start(
			service=service,
			service_version='1.0.1',
			verbose=verbosity,
			project_id=project_id,
		)
	except (ValueError, NotImplementedError, DefaultCredentialsError) as exc:
		print(exc)  # Handle errors here

def get_remote_ip():
	try:
		return local.request.headers['X-Remote-Addr']
	except (KeyError, AttributeError):
		return

@frappe.whitelist(allow_guest=True)
def get_installed_apps():
	return frappe.get_installed_apps()

@frappe.whitelist(allow_guest=True)
def whoami():
	return frappe.local.session.user
