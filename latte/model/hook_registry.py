import frappe
from frappe.model.document import run_webhooks
from latte.model.document import get_controller
from functools import wraps
from latte.utils.caching import cache_in_mem, cache_me_if_you_can
import sys
from frappe import local

class Registry(object):
	@staticmethod
	def generate_handler(doctype, event):
		handlers = Registry.__build_handlers(doctype, event)
		if not handlers:
			return

		def handler(self, *args, **kwargs):
			for fn in handlers:
				# print(fn.__module__, fn, event, args, kwargs)
				fn(self, event, *args, **kwargs)

		return handler

	@staticmethod
	def __build_handlers(doctype, event):
		doc_events = frappe.get_hooks('doc_events')
		if doc_events:
			doctype_doc_events = doc_events.get(doctype) or {}
			all_doctype_doc_events = doc_events.get('*') or {}
			doc_event_handlers = [
				frappe.get_attr(method_string) for method_string in
				(
					(doctype_doc_events.get(event) or [])
					+ (all_doctype_doc_events.get(event) or [])
				)
			]
		else:
			doc_event_handlers = []

		class_method = getattr(get_controller(doctype), event, None)
		if class_method:
			@wraps(class_method)
			def wrapped(self, method, *args, **kwargs):
				class_method(self, *args, **kwargs)

			doc_event_handlers = [wrapped] + doc_event_handlers

		return doc_event_handlers

def run_method(self, method, *args, **kwargs):
	"""run standard triggers, plus those in hooks"""
	if "flags" in kwargs:
		del kwargs["flags"]

	# print('Triggered', self.doctype, self.name, method)
	trigger_method = f'__run_{method}'
	try:
		doc_event_trigger = getattr(self.__class__, trigger_method)
	except AttributeError:
		doc_event_trigger = Registry.generate_handler(self.doctype, method)
		setattr(self.__class__, trigger_method, doc_event_trigger)

	doc_event_trigger and doc_event_trigger(self, *args, **kwargs)

def get_hooks(hook=None, default=None, app_name=None):
	flags = local.flags
	dynamic = not (flags.in_migrate or flags.in_install_app or flags.in_install)

	recursive = False
	if flags.building_hooks:
		recursive = True
	else:
		flags.building_hooks = True

	# print('Recursive===>', recursive)
	# import traceback
	# traceback.print_stack()

	hooks = load_hooks(app_name=app_name, dynamic=dynamic, rec=recursive)

	if not recursive:
		flags.building_hooks = False

	if hook:
		return hooks.get(hook, default if default is not None else [])
	return hooks

@cache_in_mem(
	key=lambda app_name, dynamic, rec: f'{app_name}|{dynamic}|{rec}',
	lock_cache=True,
	invalidate=lambda app_name, dynamic, rec: 'hooks',
)
@cache_me_if_you_can(
	key=lambda app_name, dynamic, rec: (f'{app_name}|{dynamic}|{rec}', 3600,),
	invalidate=lambda app_name, dynamic, rec: 'hooks'
)
def load_hooks(app_name, dynamic, rec):
	"""Get hooks via `app/hooks.py + db -> scheduler event doctype`

	:param hook: Name of the hook. Will gather all hooks for this name and return as a list.
	:param default: Default if no hook found.
	:param app_name: Filter by app."""

	try:
		return frappe._dict(local.app_hooks_loader[app_name])
	except (AttributeError, KeyError):
		pass

	if app_name:
		apps = [app_name]
	else:
		apps = frappe.get_installed_apps(sort=True)

	app_hooks = load_app_hooks(apps)

	hook_loader = local.app_hooks_loader = getattr(local, 'app_hooks_loader', {})
	hook_loader[app_name] = app_hooks

	if dynamic:
		hooks = load_dynamic_hooks(apps, app_hooks)
	else:
		hooks = app_hooks

	del hook_loader[app_name]
	return frappe._dict(hooks)

def load_app_hooks(apps):
	hooks = {}
	for app in apps:
		try:
			app_hooks_module = frappe.get_module(f"{app}.hooks")
		except ImportError:
			if local.flags.in_install_app:
				# if app is not installed while restoring
				# ignore it
				pass
			print('Could not find app "{0}"'.format(app))
			if not frappe.request:
				sys.exit(1)
			raise
		for key in dir(app_hooks_module):
			if not key.startswith("_"):
				frappe.append_hook(hooks, key, getattr(app_hooks_module, key))

	doc_events = hooks.get('doc_events')
	if doc_events:
		tuple_keys = list((key, doc_events[key],) for key in doc_events if isinstance(key, tuple))

		for key, value in tuple_keys:
			del doc_events[key]
			for doctype in key:
				frappe.append_hook(doc_events, doctype, value)

	return hooks

def load_dynamic_hooks(apps, hooks):
	for app in apps:
		app_hooks_module = frappe.get_module(f"{app}.hooks")
		try:
			dynamic_hook_loaders = app_hooks_module.dynamic_hooks
		except AttributeError:
			continue

		# TODO: Make a report on get_hooks
		for dynamic_hook_loader in dynamic_hook_loaders:
			dynamic_hooks = frappe.get_attr(dynamic_hook_loader)()
			for hook_name, value in dynamic_hooks.items():
				frappe.append_hook(hooks, hook_name, value)

	return hooks

def invalidate(*_, **__):
	from latte.utils.caching import invalidate
	invalidate('hooks')
