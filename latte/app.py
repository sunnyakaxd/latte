from time import perf_counter
from six import string_types
from werkzeug.wrappers import Request, Response
from werkzeug.exceptions import HTTPException, NotFound, BadRequest
from frappe.core.doctype.communication.comment import update_comments_in_parent_after_request
from uuid import uuid4
import frappe
import latte
import os
import pymysql
# from latte import _dict
from latte.json import loads
from latte.utils.logger import get_logger
from datetime import datetime
from latte.json import loads, JSONDecodeError
# from werkzeug.wsgi import wrap_file
from frappe import local
from frappe.utils import get_site_name
from pymysql.constants import ER
from frappe.api import validate_oauth, validate_auth_via_api_keys, build_response
from gevent.timeout import Timeout
from frappe import local
from frappe.utils import cint

_sites_path = os.environ.get("SITES_PATH", ".")

@Request.application
def application(request):
	response = None
	log_info = {}
	log_info['request_start'] = datetime.utcnow()
	traceback = None

	timeout_handler = None
	try:
		rollback = True

		init_request(request)
		log_info['remote_addr'] = latte.get_remote_ip()
		log_info['request_path'] = local.request.path

		if local.request.path.startswith("/api/"):
			# if local.form_dict.data is None:
			# 	local.form_dict.data = request.get_data(as_text=True)
			call, doctype, name = get_cmd()
			timeout_handler = start_timeout(doctype)
			response = api_handle(call, doctype, name)

		elif cmd := local.form_dict.cmd:
			timeout_handler = start_timeout(cmd)
			response = throttled_handle(cmd)

		# elif local.request.path.startswith('/private/files/'):
		#	response = frappe.utils.response.download_private_file(request.path)
		elif local.request.path.startswith("/app-health"):
			response = Response()
			response.data = 'Healthy'

		# elif local.request.path.startswith("/accept"):
		# 	f = open('./assets/latte/html/acceptance.html')
		# 	response = Response(wrap_file(local.request.environ, f), direct_passthrough=True)
		# 	response.content_type = 'text/html'

		elif local.request.path.startswith('/get_csrf'):
			# local.flags.ignore_csrf = True
			response = Response()
			response.data = local.session.data.csrf_token or ''

		# elif cmd := get_handler_for_url():
		# 	local.form_dict.cmd = cmd
		# 	response = throttled_handle(cmd)

		elif local.request.method in ('GET', 'HEAD', 'POST'):
			timeout_handler = start_timeout()
			cmd = get_handler_for_url()
			if cmd:
				# This is needed as frappe.handler.handle() picks it up from form_dict.
				local.form_dict.cmd = cmd
				handler_response = throttled_handle(cmd)
				if isinstance(handler_response, string_types) or isinstance(handler_response, dict):
					response = Response()
					response.data = handler_response
				elif isinstance(handler_response, Response):
					response = handler_response
				else:
					raise BadRequest
			else:
				local.flags.current_running_method = local.request.path
				response = frappe.website.render.render()

		else:
			raise NotFound

		rollback = after_request(rollback)

	except HTTPException as e:
		if timeout_handler:
			timeout_handler.close()

		traceback = frappe.get_traceback()
		local.db.rollback()
		return e

	except frappe.SessionStopped as e:
		if timeout_handler:
			timeout_handler.close()

		local.db.rollback()
		response = frappe.utils.response.handle_session_stopped()

	except Timeout as e:
		if e is not timeout_handler:
			raise

		e.http_status_code = 504
		traceback = frappe.get_traceback()
		if not local.db.open:
			local.db.connect()

		response = handle_exception(e)

		local.db.rollback()

	except Exception as e:
		if timeout_handler:
			timeout_handler.close()

		traceback = frappe.get_traceback()
		response = handle_exception(e)
		local.db.rollback()

	finally:
		# set cookies
		if timeout_handler:
			timeout_handler.close()

		if response and hasattr(local, 'cookie_manager'):
			local.cookie_manager.flush_cookies(response=response)
		try:
			log_info['headers'] = {k: v for k, v in request.headers.items()}
			log_info['request_end'] = datetime.utcnow()
			tat = log_info['turnaround_time'] = (log_info['request_end'] - log_info['request_start']).total_seconds()
			log_info['cmd'] = local.form_dict.cmd if hasattr(local, 'form_dict') else None
			log_info['type'] = 'request_log'
			log_info['cache_balancer_time'] = local.cache_balancer_time
			log_info['status_code'] = response.status_code if response else 500
			log_info['doctype'] = local.form_dict.doctype if hasattr(local, 'form_dict') else None
			sql_time = log_info['sql_time'] = local.sql_time
			cache_access_time = log_info['cache_access_time'] = local.cache_access_time
			sql_logging_time = log_info['sql_logging_time'] = local.sql_logging_time
			log_info['python_time'] = tat - sql_time - cache_access_time - sql_logging_time
			if traceback:
				log_info['traceback'] = traceback

			if local.conf.log_query_type:
				log_info['sql_selects'] = local.sql_selects
				log_info['sql_updates'] = local.sql_updates
				log_info['sql_deletes'] = local.sql_deletes
				log_info['sql_inserts'] = local.sql_inserts

			log_info['read_only_db_logs'] = local.read_only_db_logs
			log_info['greenlet_time'] = local.greenlet_time + perf_counter() - local.greenlet_start

			get_logger(module='latte.app', index_name='web-access-log').info(log_info)
		except Exception as e:
			print(e)

		if traceback and local.conf.developer_mode:
			print(traceback)

		latte.destroy()

	return response

def start_timeout(cmd=None):
	if (skip := local.conf.skip_timeout_for) and cmd and cmd in skip:
		return

	if timeout := local.conf.web_timeout:
		timeout_handler = Timeout(timeout)
		timeout_handler.start()
		local.append_statement_to_query = 'set statement max_statement_time=' + str(timeout) + ' for'
		return timeout_handler

def get_handler_for_url():
	logger = get_logger(module='latte.app', index_name='web-access-log')
	handler = None
	logger.debug(f"Handling custom url {local.request.path}")
	paths = local.request.path.split('/')

	if paths[0]:
		base_path = paths[0]
		sub_path = "/".join(paths[1:])
		sub_path = f"/{sub_path}"
	else:
		base_path = paths[1]
		sub_path = "/".join(paths[2:])
		sub_path = f"/{sub_path}"
	logger.debug(f"Base Path - {base_path}")
	if base_path == 'desk':
		return None
	logger.debug(f"Sub Path - {sub_path}")
	handler = get_hook_for_url(base_path, sub_path)
	if not handler:
		# Check in doctype configuration instead of hooks - this allows for dynamically adding pre-defined handlers
		# for urls. This is not expected to be used frequently and is provided only as an alternative.
		try:
			handler_doc = frappe.get_cached_doc('URL Handler', base_path)
			for subpath_handler in handler_doc.sub_path_handlers:
				if subpath_handler.sub_path == sub_path:
					handler = subpath_handler.handler
					logger.debug(f'Found handler {handler} for sub_path {sub_path}')
					break
		except frappe.DoesNotExistError:
			logger.error(f"Could not find custom URL Handler for base path '{base_path}'")
	return handler


def get_hook_for_url(base_path, sub_path):
	hooks = frappe.get_hooks('url_handlers')
	handlers = None
	handler = None
	if hooks and isinstance(hooks, dict):
		handlers = hooks.get(base_path)

	if handlers:
		if isinstance(handlers, string_types):
			handler = handlers
		elif isinstance(handlers, dict):
			handler = handlers.get(sub_path, None)
		if isinstance(handler, list):
			handler = handler[0]
	return handler


@frappe.whitelist(allow_guest=True, xss_safe=True)
def default_handler():
	response = Response()
	response.data = 'Healthy'
	return response

def throttled_handle(cmd):
	throttling = local.conf.throttling
	local.flags.current_running_method = cmd
	throttle_limit = throttling and throttling.get(cmd)

	if not throttle_limit:
		return frappe.handler.handle()

	cur_count = frappe.cache().incr(f'throttle.{cmd}')
	if cur_count > throttle_limit:
		# Too many requests for this command
		frappe.cache().decr(f'throttle.{cmd}')
		log_throttle_msg(cmd)
		err = ThrottlingException()
		err.http_status_code = 429
		raise err

	try:
		return frappe.handler.handle()
	finally:
		frappe.cache().decr(f'throttle.{cmd}')


def get_cmd():
	"""
	Handler for `/api` methods

	### Examples:

	`/api/method/{methodname}` will call a whitelisted method

	`/api/resource/{doctype}` will query a table
		examples:
		- `?fields=["name", "owner"]`
		- `?filters=[["Task", "name", "like", "%005"]]`
		- `?limit_start=0`
		- `?limit_page_length=20`

	`/api/resource/{doctype}/{name}` will point to a resource
		`GET` will return doclist
		`POST` will insert
		`PUT` will update
		`DELETE` will delete

	`/api/resource/{doctype}/{name}?run_method={method}` will run a whitelisted controller method
	"""

	validate_oauth()
	validate_auth_via_api_keys()

	parts = local.request.path[1:].split("/", 3)
	call = doctype = name = None

	if len(parts) > 1:
		call = parts[1]

	if len(parts) > 2:
		doctype = parts[2]

	if len(parts) > 3:
		name = parts[3]

	if call == "method":
		local.form_dict.cmd = doctype

	return call, doctype, name

def api_handle(call, doctype, name):
	"""
	Handler for `/api` methods

	### Examples:

	`/api/method/{methodname}` will call a whitelisted method

	`/api/resource/{doctype}` will query a table
		examples:
		- `?fields=["name", "owner"]`
		- `?filters=[["Task", "name", "like", "%005"]]`
		- `?limit_start=0`
		- `?limit_page_length=20`

	`/api/resource/{doctype}/{name}` will point to a resource
		`GET` will return doclist
		`POST` will insert
		`PUT` will update
		`DELETE` will delete

	`/api/resource/{doctype}/{name}?run_method={method}` will run a whitelisted controller method
	"""
	if call == "method":
		local.form_dict.cmd = doctype
		return throttled_handle(doctype)

	elif call == "resource":
		if "run_method" in local.form_dict:
			method = local.form_dict.pop("run_method")
			doc = frappe.get_doc(doctype, name)
			doc.is_whitelisted(method)

			if local.request.method == "GET":
				if not doc.has_permission("read"):
					frappe.throw("Not permitted", frappe.PermissionError)
				local.response.update({"data": doc.run_method(method, **local.form_dict)})

			if local.request.method == "POST":
				if not doc.has_permission("write"):
					frappe.throw("Not permitted", frappe.PermissionError)

				local.response.update({"data": doc.run_method(method, **local.form_dict)})
				local.db.commit()

		else:
			if name:
				if local.request.method == "GET":
					doc = frappe.get_doc(doctype, name)
					if not doc.has_permission("read"):
						raise frappe.PermissionError
					local.response.update({"data": doc})

				if local.request.method == "PUT":
					data = local.form_dict  # loads(local.form_dict.data)
					doc = frappe.get_doc(doctype, name)

					if "flags" in data:
						del data["flags"]

					# Not checking permissions here because it's checked in doc.save
					doc.update(data)

					local.response.update({
						"data": doc.save().as_dict()
					})
					local.db.commit()

				if local.request.method == "DELETE":
					# Not checking permissions here because it's checked in delete_doc
					frappe.delete_doc(doctype, name, ignore_missing=False)
					local.response.http_status_code = 202
					local.response.message = "ok"
					local.db.commit()


			elif doctype:
				if local.request.method == "GET":
					if local.form_dict.get('fields'):
						local.form_dict['fields'] = loads(local.form_dict['fields'])
					local.form_dict.setdefault('limit_page_length', 20)
					local.response.update({
						"data": frappe.call(frappe.client.get_list,
											doctype, **local.form_dict)})

				if local.request.method == "POST":
					data = local.form_dict  # loads(local.form_dict.data)
					data.update({
						"doctype": doctype
					})
					local.response.update({
						"data": frappe.get_doc(data).insert().as_dict()
					})
					local.db.commit()
			else:
				raise frappe.DoesNotExistError

	else:
		raise frappe.DoesNotExistError

	return build_response("json")


def log_throttle_msg(cmd):
	log_info = {}
	log_info['cmd'] = cmd
	log_info['message'] = 'Throttled request'
	get_logger(module='latte.app', index_name='throttled_api_log').info(log_info)


class ThrottlingException(Exception):
	pass


@Request.application
def applicationperf(request):
	user = None
	try:
		# import cProfile
		# cProfile.runctx('init_request(request, sessionless=True)', {
		# 	'init_request': init_request,
		# 	'request': request,
		# }, {}, sort='cumtime')
		init_request(request, sessionless=True)
		user = frappe.session.user
	finally:
		frappe.destroy()
	return Response(user)


def init_request(request, sessionless=False):
	local.request = request
	local.is_ajax = frappe.get_request_header("X-Requested-With") == "XMLHttpRequest"

	site = request.headers.get('X-Frappe-Site-Name') or get_site_name(request.host)
	latte.init(site=site, sites_path=_sites_path)

	request_id = frappe.get_request_header('X-Request-Id')
	if not request_id:
		request_id = str(uuid4())
	frappe.flags.task_id = frappe.flags.request_id = request_id
	frappe.flags.runner_type = 'web'

	if not (local.conf and local.conf.db_name):
		# site does not exist
		raise NotFound

	if local.conf.get('maintenance_mode'):
		print('''
################################  ERROR  ################################
Maintainence mode is enabled in site_config.
This possibly means a broken app installation.
Kindly remove "maintainence_mode": 1 from site_config/common_site_config
to suppress this error, however only do so if you can ignore the error
or handle it manually, else reinstallation of the db might be required.
#########################################################################
		''')
		raise frappe.SessionStopped

	local.flags.sessionless = sessionless
	latte.connect(admin=False)
	# # local.db.connect()
	make_form_dict(request)
	local.http_request = latte.auth.HTTPRequest()

def after_request(rollback):
	if (local.request.method in ("POST", "PUT") or local.flags.commit) and local.db:
		local.db.commit()
		rollback = False

	# update session
	if getattr(local, "session_obj", None):
		updated_in_db = local.session_obj.update()
		if updated_in_db:
			local.db.commit()
			rollback = False

	update_comments_in_parent_after_request()

	return rollback

def make_form_dict(request):
	request_data = request.get_data(as_text=True)
	if 'application/json' in (request.content_type or '') and request_data:
		try:
			args = loads(request_data)
		except JSONDecodeError:
			frappe.throw('Unable to decode json:' + str(request_data))
	else:
		args = request.form or request.args

	# try:
	#     local.form_dict = frappe._dict({
	#         k: v[0] if isinstance(v, (list, tuple)) else v
	#         for k, v in args.items()
	#     })
	# except IndexError:
	#     local.form_dict = frappe._dict(args)

	local.form_dict = frappe._dict(args)
	if "_" in local.form_dict:
		# _ is passed by $.ajax so that the request is not cached by the browser. So, remove _ from form_dict
		local.form_dict.pop("_")


def handle_exception(e):
	response = None
	http_status_code = getattr(e, "http_status_code", 500)
	return_as_message = False

	if frappe.get_request_header('Accept') and (
			local.is_ajax or 'application/json' in frappe.get_request_header('Accept')):

		try:
			allow_error_traceback = cint(frappe.db.get_system_setting('allow_error_traceback'))
		except:
			allow_error_traceback = 0

		# handle ajax responses first
		# if the request is ajax, send back the trace or error message
		if allow_error_traceback and not frappe.local.flags.disable_traceback:
			frappe.errprint(frappe.utils.get_traceback())

		response = build_response("json")
		response.status_code = http_status_code

	elif (http_status_code == 500
		  and isinstance(e, pymysql.InternalError)
		  and e.args[0] in (ER.LOCK_WAIT_TIMEOUT, ER.LOCK_DEADLOCK)):
		http_status_code = 508

	elif http_status_code == 401:
		frappe.respond_as_web_page(
				"Session Expired",
				"Your session has expired, please login again to continue.",
				http_status_code=http_status_code, indicator_color='red'
		)
		return_as_message = True

	elif http_status_code == 403:
		frappe.respond_as_web_page(
				"Not Permitted",
				"You do not have enough permissions to complete the action",
				http_status_code=http_status_code, indicator_color='red'
		)
		return_as_message = True

	elif http_status_code == 404:
		frappe.respond_as_web_page(
				"Not Found",
				"The resource you are looking for is not available",
				http_status_code=http_status_code, indicator_color='red')
		return_as_message = True

	else:
		traceback = "<pre>" + frappe.get_traceback() + "</pre>"
		if local.flags.disable_traceback:
			traceback = ""

		frappe.respond_as_web_page("Server Error",
								   traceback, http_status_code=http_status_code,
								   indicator_color='red', width=640)
		return_as_message = True

	if e.__class__ == frappe.AuthenticationError:
		if hasattr(local, "login_manager"):
			local.login_manager.clear_cookies()

	if http_status_code >= 500:
		frappe.logger().error('Request Error', exc_info=True)

	if return_as_message:
		response = frappe.website.render.render("message",
												http_status_code=http_status_code)

	return response
