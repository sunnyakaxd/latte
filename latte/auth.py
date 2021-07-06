# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
from typing import cast
import frappe
from frappe.utils import cint, get_datetime, datetime
from frappe.auth import HTTPRequest, CookieManager, check_session_stopped
from frappe.sessions import (
	Session,
	clear_sessions,
	delete_session,
	get_geo_ip_country
)
from frappe.core.doctype.activity_log.activity_log import add_authentication_log
from frappe.utils.password import check_password, delete_login_failed_cache
from frappe.twofactor import (
	should_run_2fa,
	authenticate_for_2factor,
	confirm_otp_token,
	get_cached_user_pass
)
from six import text_type
from latte.utils.caching import cache_in_mem, cache_me_if_you_can
from latte.utils import get_system_setting
from frappe import local

class PatchedSession(Session):
	def start(self):
		"""start a new session"""
		# generate sid
		if self.user=='Guest':
			sid = 'Guest'
		else:
			sid = frappe.generate_hash()

		self.data.user = self.user
		self.data.sid = sid
		self.data.data.user = self.user
		self.data.data.session_ip = local.request_ip
		if self.user != "Guest":
			self.data.data.update({
				"last_updated": frappe.utils.now(),
				"session_expiry": get_expiry_period(self.device, self.user),
				"full_name": self.full_name,
				"user_type": self.user_type,
				"device": self.device,
				"session_country": get_geo_ip_country(local.request_ip) if local.request_ip else None,
			})

		# insert session
		if self.user!="Guest":
			self.insert_session_record()
			local.db.commit()

	def update(self, force=False):
		"""extend session expiry"""
		if (frappe.session['user'] == "Guest" or frappe.form_dict.cmd=="logout"):
			return

		now = frappe.utils.now()

		self.data['data']['last_updated'] = now
		self.data['data']['lang'] = text_type(frappe.lang)

		# update session in db
		last_updated = frappe.cache().hget("last_db_session_update", self.sid)
		time_diff = frappe.utils.time_diff_in_seconds(now, last_updated) if last_updated else None

		# database persistence is secondary, don't update it too often
		updated_in_db = False
		if force or (time_diff==None) or (time_diff > 600):
			# update sessions table
			local.db.sql("""update tabSessions set sessiondata=%s,
				lastupdate=NOW() where sid=%s""" , (str(self.data['data']),
				self.data['sid']))

			# update last active in user table
			local.db.sql("""update `tabUser` set last_active=%(now)s where name=%(name)s""", {
				"now": now,
				"name": frappe.session.user
			})

			local.db.commit()
			frappe.cache().hset("last_db_session_update", self.sid, now)

			updated_in_db = True

		# set in memcache
		frappe.cache().hset("session", self.sid, self.data)

		return updated_in_db

class PatchedHTTPRequest(object):
	def __init__(self):
		# Get Environment variables
		self.domain = frappe.request.host
		if self.domain and self.domain.startswith('www.'):
			self.domain = self.domain[4:]

		local.ignore_2fa = 0
		if frappe.get_request_header('X-Forwarded-For'):
			local.request_ip = (frappe.get_request_header('X-Forwarded-For').split(",")[0]).strip()

		elif frappe.get_request_header('REMOTE_ADDR'):
			local.request_ip = frappe.get_request_header('REMOTE_ADDR')

		else:
			local.request_ip = '127.0.0.1'

		if frappe.get_request_header('x-ignore-2fa'):
			local.ignore_2fa = frappe.get_request_header('x-ignore-2fa') or 0

		# load cookies
		local.cookie_manager = CookieManager()

		# login
		local.login_manager = LoginManager()

		# if frappe.form_dict._lang:
		# 	lang = get_lang_code(frappe.form_dict._lang)
		# 	if lang:
		# 		local.lang = lang

		self.validate_csrf_token()

		# write out latest cookies
		local.cookie_manager.init_cookies()

		# check status
		check_session_stopped()

	def validate_csrf_token(self):
		if local.request and local.request.method=="POST":
			if not local.session: return
			if not local.session.data.csrf_token \
				or local.session.data.device=="mobile" \
				or frappe.conf.get('ignore_csrf', None):
				# not via boot
				return

			csrf_token = frappe.get_request_header("X-Frappe-CSRF-Token")
			if not csrf_token and "csrf_token" in local.form_dict:
				csrf_token = local.form_dict.csrf_token
				del local.form_dict["csrf_token"]

			if local.session.data.csrf_token != csrf_token:
				local.flags.disable_traceback = True
				frappe.throw("Invalid Request", frappe.CSRFTokenError)

HTTPRequest = PatchedHTTPRequest

class LoginManager(object):
	__slots__ = ['user', 'info', 'full_name', 'user_type', 'user_details', 'resume']
	def __init__(self):
		self.user = None
		self.info = None
		self.full_name = None
		self.user_type = None
		self.user_details = None

		if local.form_dict.get('cmd')=='login' or local.request.path=="/api/method/login":
			if not self.login():
				return

			self.resume = False
			# run login triggers
			self.run_trigger('on_session_creation')
		else:
			try:
				self.resume = True
				self.make_session(resume=True)
				self.load_user_info()
				self.set_user_info(resume=True)
			except AttributeError:
				self.user = "Guest"
				self.load_user_info()
				self.make_session()
				self.set_user_info()

	def login(self):
		# clear cache
		frappe.clear_cache(user = frappe.form_dict.get('usr'))
		user, pwd = get_cached_user_pass()
		self.authenticate(user=user, pwd=pwd)
		if not local.ignore_2fa and should_run_2fa(self.user):
			authenticate_for_2factor(self.user)
			if not confirm_otp_token(self):
				return False
		self.post_login()

	def post_login(self):
		self.run_trigger('on_login')
		self.validate_ip_address()
		self.validate_hour()
		self.load_user_info()
		self.make_session()
		self.set_user_info()

	def load_user_info(self, resume=False):
		self.info = self.user_details or LoginManager.fetch_user_info(self.user)

		self.user_type = self.info.user_type

	@staticmethod
	@cache_me_if_you_can(key=lambda user: (user, 120))
	def fetch_user_info(user):
		return local.db.get_value(
			"User",
			user,
			["enabled", "user_type", "first_name", "last_name", "user_image"],
			as_dict=1,
		)

	def set_user_info(self, resume=False):
		# set sid again
		local.cookie_manager.init_cookies()

		self.full_name = " ".join(filter(None, [self.info.first_name,
			self.info.last_name]))

		if self.info.user_type=="Website User":
			local.cookie_manager.set_cookie("system_user", "no")
			if not resume:
				local.response["message"] = "No App"
				local.response["home_page"] = get_website_user_home_page(self.user)
		else:
			local.cookie_manager.set_cookie("system_user", "yes")
			if not resume:
				local.response['message'] = 'Logged In'
				local.response["home_page"] = "/desk"

		if not resume:
			frappe.response["full_name"] = self.full_name

		# redirect information
		# redirect_to = frappe.cache().hget('redirect_after_login', self.user)
		# if redirect_to:
		# 	local.response["redirect_to"] = redirect_to
		# 	frappe.cache().hdel('redirect_after_login', self.user)


		local.cookie_manager.set_cookie("full_name", self.full_name)
		local.cookie_manager.set_cookie("user_id", self.user)
		local.cookie_manager.set_cookie("user_image", self.info.user_image or "")

	def make_session(self, resume=False):
		# start session
		local.session_obj = PatchedSession(user=self.user, resume=resume,
			full_name=self.full_name, user_type=self.user_type)

		# reset user if changed to Guest
		self.user = local.session_obj.user
		local.session = local.session_obj.data
		self.clear_active_sessions()

	def clear_active_sessions(self):
		"""Clear other sessions of the current user if `deny_multiple_sessions` is not set"""
		if not (
			cint(frappe.conf.get("deny_multiple_sessions"))
			or cint(get_system_setting('deny_multiple_sessions'))
		):
			return

		# if frappe.session.user != "Guest":
		# 	clear_sessions(frappe.session.user, keep_current=True)
		pass

	@staticmethod
	@cache_me_if_you_can(key=lambda user:user, expiry=360)
	def get_user_id(user):
		mob_user = None
		name_user = None
		if user.isdigit() and cint(get_system_setting('allow_login_using_mobile_number')):
			mob_user = local.db.get_value("User", filters={"mobile_no": user}, fieldname="name")

		if not mob_user and cint(get_system_setting('allow_login_using_user_name')):
			name_user = local.db.get_value("User", filters={"username": user}, fieldname="name")

		return mob_user or name_user or user

	def authenticate(self, user=None, pwd=None):
		if not (user and pwd):
			user, pwd = frappe.form_dict.get('usr'), frappe.form_dict.get('pwd')
		if not (user and pwd):
			self.fail('Incomplete login details', user=user)

		user = LoginManager.get_user_id(user)

		self.check_if_enabled(user)
		self.user = self.check_password(user, pwd)

	def check_if_enabled(self, user):
		"""raise exception if user not enabled"""
		consecutive_login_attempts_allowed = cint(get_system_setting('allow_consecutive_login_attempts'))

		if consecutive_login_attempts_allowed > 0:
			LoginManager.check_consecutive_login_attempts(user, consecutive_login_attempts_allowed)

		if user=='Administrator': return
		self.user_details = LoginManager.fetch_user_info(user)
		if not cint(self.user_details and self.user_details['enabled']):
			self.fail('User disabled or missing', user=user)

	@staticmethod
	def check_consecutive_login_attempts(user, consecutive_login_attempts_allowed):
		allow_login_after_fail = cint(get_system_setting('allow_login_after_fail'))

		login_failed_count = get_login_failed_count(user)
		last_login_tried = (get_last_tried_login_data(user, True)
			+ datetime.timedelta(seconds=allow_login_after_fail))

		if login_failed_count >= consecutive_login_attempts_allowed:
			locked_account_time = frappe.cache().hget('locked_account_time', user)
			if not locked_account_time:
				frappe.cache().hset('locked_account_time', user, get_datetime())

			if last_login_tried > get_datetime():
				frappe.throw(
					f"Your account has been locked and will resume after {allow_login_after_fail} seconds",
					frappe.SecurityException
				)
			else:
				delete_login_failed_cache(user)

	def check_password(self, user, pwd):
		"""check password"""
		try:
			# returns user in correct case
			return check_password(user, pwd)
		except frappe.AuthenticationError:
			self.update_invalid_login(user)
			self.fail('Incorrect password', user=user)

	def fail(self, message, user=None):
		if not user:
			user = 'Unknown User'
		local.response['message'] = message
		add_authentication_log(message, user, status="Failed")
		local.db.commit()
		raise frappe.AuthenticationError

	def update_invalid_login(self, user):
		last_login_tried = get_last_tried_login_data(user)

		failed_count = 0
		if last_login_tried > get_datetime():
			failed_count = get_login_failed_count(user)

		frappe.cache().hset('login_failed_count', user, failed_count + 1)

	def run_trigger(self, event='on_login'):
		for method in frappe.get_hooks().get(event, []):
			frappe.call(frappe.get_attr(method), login_manager=self)

	def validate_ip_address(self):
		"""check if IP Address is valid"""
		user = frappe.get_doc("User", self.user)
		ip_list = user.get_restricted_ip_list()
		if not ip_list:
			return

		bypass_restrict_ip_check = 0
		# check if two factor auth is enabled
		enabled = int(frappe.get_system_settings('enable_two_factor_auth') or 0)
		if enabled:
			#check if bypass restrict ip is enabled for all users
			bypass_restrict_ip_check = int(frappe.get_system_settings('bypass_restrict_ip_check_if_2fa_enabled') or 0)
			if not bypass_restrict_ip_check:
				#check if bypass restrict ip is enabled for login user
				bypass_restrict_ip_check = int(local.db.get_value('User', self.user, 'bypass_restrict_ip_check_if_2fa_enabled') or 0)
		for ip in ip_list:
			if local.request_ip.startswith(ip) or bypass_restrict_ip_check:
				return

		frappe.throw("Not allowed from this IP Address", frappe.AuthenticationError)

	def validate_hour(self):
		"""check if user is logging in during restricted hours"""
		login_before = int(local.db.get_value('User', self.user, 'login_before', ignore=True) or 0)
		login_after = int(local.db.get_value('User', self.user, 'login_after', ignore=True) or 0)

		if not (login_before or login_after):
			return

		from frappe.utils import now_datetime
		current_hour = int(now_datetime().strftime('%H'))

		if login_before and current_hour > login_before:
			frappe.throw("Login not allowed at this time", frappe.AuthenticationError)

		if login_after and current_hour < login_after:
			frappe.throw("Login not allowed at this time", frappe.AuthenticationError)

	def login_as_guest(self):
		"""login as guest"""
		self.login_as("Guest")

	def login_as(self, user):
		self.user = user
		self.post_login()

	def logout(self, arg='', user=None):
		if not user: user = frappe.session.user
		self.run_trigger('on_logout')

		if user == frappe.session.user:
			delete_session(frappe.session.sid, user=user, reason="User Manually Logged Out")
			self.clear_cookies()
		else:
			clear_sessions(user)

	def clear_cookies(self):
		clear_cookies()

def clear_cookies():
	if hasattr(local, "session"):
		frappe.session.sid = ""
	local.cookie_manager.delete_cookie(["full_name", "user_id", "sid", "user_image", "system_user"])

def get_login_failed_count(user):
	return cint(frappe.cache().hget('login_failed_count', user)) or 0

def get_website_user_home_page(user):
	home_page_method = frappe.get_hooks('get_website_user_home_page')
	if home_page_method:
		home_page = frappe.get_attr(home_page_method[-1])(user)
		return '/' + home_page.strip('/')
	elif frappe.get_hooks('website_user_home_page'):
		return '/' + frappe.get_hooks('website_user_home_page')[-1].strip('/')
	else:
		return '/me'

def get_last_tried_login_data(user, get_last_login=False):
	locked_account_time = frappe.cache().hget('locked_account_time', user)
	if get_last_login and locked_account_time:
		return locked_account_time

	last_login_tried = frappe.cache().hget('last_login_tried', user)
	if not last_login_tried or last_login_tried < get_datetime():
		last_login_tried = get_datetime() + datetime.timedelta(seconds=60)

	frappe.cache().hset('last_login_tried', user, last_login_tried)

	return last_login_tried

def get_profile_expiry(role_profile):
	try:
		return frappe.get_cached_doc('Role Profile Session Expiry', role_profile).session_time
	except frappe.DoesNotExistError:
		try:
			frappe.get_doc({
				'doctype': 'Role Profile Session Expiry',
				'role_profile': role_profile,
			}).insert(ignore_permissions=True)
		except frappe.DuplicateEntryError:
			pass

def get_expiry_period(device="desktop", user=None):
	if device=="mobile":
		key = "session_expiry_mobile"
		default = "720:00:00"
	else:
		key = "session_expiry"
		default = "06:00:00"
	if user and (role_profile := frappe.get_cached_doc('User', user).role_profile_name):
		role_profile_session_expiry = get_profile_expiry(role_profile)
	else:
		role_profile_session_expiry = None

	exp_sec = role_profile_session_expiry or frappe.defaults.get_global_default(key) or default

	# incase seconds is missing
	if len(exp_sec.split(':')) == 2:
		exp_sec = exp_sec + ':00'

	return exp_sec