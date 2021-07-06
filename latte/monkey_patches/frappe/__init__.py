import frappe
from latte.utils.caching import (
	cache_in_local,
	cache_in_mem,
	cache_me_if_you_can,
	get_args_for,
	get_cache,
	invalidate_by_key,
	RedisWrapper,
	INVALIDATION_ON,
)
from frappe.model.meta import Meta
from latte.database_utils.connection_pool import PatchedDatabase
from frappe import get_attr
from frappe import local
import latte
from latte.model.document import get_controller
from frappe.model.base_document import BaseDocument
from frappe.model.document import Document
from latte.utils.logger import get_logger
from traceback import walk_stack

def meta_invalidate(doctype, cached=True):
	return f'meta|{doctype}'

@cache_in_mem(
	key=lambda doctype, cached=None:doctype,
	invalidate=meta_invalidate
)
@cache_me_if_you_can(
	key=lambda doctype, cached=None: doctype,
	build_expiry=300,
	nocache=lambda doctype, cached=True: not cached,
	invalidate=meta_invalidate,
)
def get_meta(doctype, cached=True):
	local.db._cursor.__no_logging = True
	meta = Meta(doctype)
	meta._fields = {
		row.fieldname: row
		for row in meta.fields
	}
	local.db._cursor.__no_logging = False
	return meta

def get_doc(*args, __for_update=False, **kwargs):
	"""returns a frappe.model.Document object.

	:param arg1: Document dict or DocType name.
	:param arg2: [optional] document name.

	There are multiple ways to call `get_doc`

		# will fetch the latest user object (with child table) from the database
		user = get_doc("User", "test@example.com")

		# create a new object
		user = get_doc({
			"doctype":"User"
			"email_id": "test@example.com",
			"roles: [
				{"role": "System Manager"}
			]
		})

		# create new object with keyword arguments
		user = get_doc(doctype='User', email_id='test@example.com')
	"""

	if args:
		if isinstance(args[0], BaseDocument):
			# already a document
			return args[0]
		elif isinstance(args[0], str):
			doctype = args[0]

		elif isinstance(args[0], dict):
			# passed a dict
			kwargs = args[0]

		else:
			raise ValueError('First non keyword argument must be a string or dict')

	if kwargs:
		doctype = kwargs['doctype']

	controller = get_controller(doctype)
	if controller:
		return controller(*args, __for_update=__for_update, **kwargs)

	raise ImportError(doctype)

@cache_in_mem(
	key=lambda doctype:doctype,
	invalidate=meta_invalidate
)
def get_immutable_class(doctype):
	controller = get_controller(doctype)
	class ImmutableDocument(controller):
		def __init__(self, doc):
			super().__setattr__('__initialising__', True)
			if isinstance(doc, dict):
				super().__init__(doc)
			elif isinstance(doc, Document):
				super().__init__(doc.as_dict())

				for field in frappe.get_meta(doc.doctype).get_table_fields():
					table = []
					for row in getattr(doc, field.fieldname):
						table.append(ImmutableDocument(row.as_dict()))
					super().__setattr__(field.fieldname, table)

			else:
				raise TypeError('Invalid type')

			super().__setattr__('__initialising__', False)

		@property
		def meta(self):
			return get_meta(self.doctype)

		def __setattr__(self, name, value):
			if not self.__initialising__:
				raise TypeError('Setting value is not allowed in cached document')
			return super().__setattr__(name, value)

		def set(self, *args, **kwargs):
			if not self.__initialising__:
				raise TypeError('Setting value is not allowed in cached document')
			return super().set(*args, **kwargs)

		def append(self, *args, **kwargs):
			if not self.__initialising__:
				raise TypeError('Setting value is not allowed in cached document')
			return super().append(*args, **kwargs)

	return type(f'Immutable{controller.__name__}', (ImmutableDocument,), {})

@cache_in_local(lambda doctype, docname=None: f'{doctype}|{docname or doctype}')
@cache_in_mem(
	key=lambda doctype, docname=None: f'{doctype}|{docname or doctype}',
	no_cache=lambda doctype, docname=None: not frappe.get_meta(doctype).memory_cachable,
	invalidate=lambda doctype, docname=None: f'get_cached_doc|{doctype}|{docname or doctype}',
	postprocess=lambda doc: get_immutable_class(doc.doctype)(doc),
)
@cache_me_if_you_can(
	key=lambda doctype, docname=None: (f'{doctype}|{docname or doctype}', frappe.get_meta(doctype).cache_timeout,),
	nocache=lambda doctype, _=None: frappe.get_meta(doctype).not_cachable,
)
def get_cached_doc(doctype, docname=None):
	if not docname:
		docname = doctype

	doc = get_doc(doctype, docname)
	if (
		(not doc.meta.not_cachable)
		and (not doc.meta.cachable)
		and not (
			local.flags.in_migrate
			or local.flags.in_install_app
			or local.flags.in_install
		)
	):
		doc.meta.cachable = 1
		frappe.utils.background_jobs.enqueue(
			push_to_config,
			doctype=doctype,
		)

	return doc
	# return ImmutableDocument(doc)

def push_to_config(doctype):
	try:
		frappe.get_doc({
			'doctype': 'DocType Meta',
			'ref_doctype': doctype,
			'cachable': 1,
			'cache_timeout': 3600,
		}).insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		pass

frappe.get_local_cached_doc = cache_in_local(lambda dt, dn=None: f'{dt}|{dn}')(get_doc)

def clear_document_cache(doctype, docname):
	meta = frappe.get_meta(doctype)
	if meta.not_cachable or not meta.cachable:
		return
	invalidate_by_key('latte.monkey_patches.frappe.get_cached_doc', f'{doctype}|{docname}')
	if meta.memory_cachable:
		invalidate_key = f'get_cached_doc|{doctype}|{docname or doctype}'
		logger = get_logger(index_name='cache_invalidation')
		stack_trace = '\n'.join(
			f'{frame.f_code.co_filename} | {frame.f_code.co_name} | {lineno}'
			for frame, lineno in
			walk_stack(None)
		)
		logger.info({
			'key': str(invalidate_key),
			'stack': stack_trace,
		})

		get_cache().publish(INVALIDATION_ON, RedisWrapper.get_invalidate_key(invalidate_key))

old_get_lang_dict = frappe.get_lang_dict

def get_lang_dict(*args, **kwargs):
	if not local.conf.enable_translations:
		return {}
	return old_get_lang_dict(*args, **kwargs)

def has_changed(doc, field):
	doc_before_save = doc.get_doc_before_save()
	if not doc_before_save:
		return True

	return getattr(doc_before_save, field) != getattr(doc, field)

def has_changed_with_values(doc, field, old_value, new_value):
	doc_before_save = doc.get_doc_before_save()
	if not doc_before_save:
		return True

	if getattr(doc_before_save, field) == getattr(doc, field):
		return False

	if (getattr(doc_before_save, field) == old_value) and (getattr(doc, field) == new_value):
		return True

def connect_read_only():

	if hasattr(local, 'read_only_db') and local.db is local.read_only_db:
		return

	local.read_only_db = PatchedDatabase(
		host=local.conf.slave_host,
		port=local.conf.slave_port,
		password=local.conf.slave_db_password,
	)
	local.read_only_db.connect()

	local.read_only_db.read_only = True

	# swap db connections
	local.master_db = local.db
	local.db = local.read_only_db

@cache_in_mem()
def get_tables():
	return set(local.db.sql_list("select name from tabDocType where istable=1"))

@cache_in_mem(key=lambda dt: dt)
def is_table(doctype):
	return doctype in get_tables()

class AppendSet(set):
	def append(self, data):
		self.add(data)

def call(fn, *args, **kwargs):
	"""Call a function and match arguments."""
	if isinstance(fn, str):
		fn = get_attr(fn)

	newvargs, newkwargs = get_args_for(fn, args, kwargs)

	return fn(*newvargs, **newkwargs)

def get_conf(site=None):
	try:
		return local.conf
	except (KeyError, AttributeError):
		with init_site(site):
			return local.conf

class init_site(object):
	def __init__(self, site=None):
		'''If site==None, initialize it for empty site ('') to load common_site_config.json'''
		self.site = site or ''

	def __enter__(self):
		latte.init(self.site)
		return local

	def __exit__(self, type, value, traceback):
		latte.destroy()

redis_server = None

def cache():
	"""Returns memcache connection."""
	global redis_server
	if not redis_server:
		redis_server = RedisWrapper.from_url(local.conf.get('redis_cache')
			or "redis://localhost:11311")
	return redis_server

frappe.cache = cache
frappe.init_site = init_site
frappe.get_conf = get_conf
frappe.call = call
frappe.clear_document_cache = clear_document_cache
frappe.whitelisted = AppendSet(frappe.whitelisted)
frappe.guest_methods = AppendSet(frappe.guest_methods)
frappe.xss_safe_methods = AppendSet(frappe.xss_safe_methods)

frappe.is_table = is_table
frappe.get_lang_dict = get_lang_dict
frappe.get_meta = get_meta
frappe.get_doc = get_doc
frappe.get_cached_doc = get_cached_doc
frappe.has_changed = has_changed
frappe.has_changed_with_values = has_changed_with_values
frappe.connect_read_only = connect_read_only

from latte.model.hook_registry import get_hooks
frappe.get_hooks = get_hooks
