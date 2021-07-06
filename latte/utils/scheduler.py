# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
"""
Events:
	always
	daily
	monthly
	weekly
"""

from __future__ import unicode_literals, print_function

import frappe
import latte
import json
import gevent
import frappe.utils
import os
from frappe.utils import get_sites
from datetime import datetime
from frappe.utils.background_jobs import queue_timeout
from latte.utils.background.job import enqueue
from frappe.limits import has_expired
from frappe.utils.data import get_datetime, now_datetime, DATETIME_FORMAT
from frappe.core.doctype.user.user import STANDARD_USERS
from frappe.installer import update_site_config
from six import string_types
from croniter import croniter
from frappe import local

# imports - third-party libraries
import pymysql
from pymysql.constants import ER

CRON_MAP = {}

def extract_params(handler):
	handler = handler[:]
	try:
		attr, params = handler.split('(')
		params = params[:-1]
		params = [frappe.safe_eval(p) for p in params.split(',')]
	except ValueError:
		attr = handler
		params = []
	return attr, params

def get_cron_map():
	try:
		return CRON_MAP[local.site]
	except:
		pass
	site_cron_map = CRON_MAP[local.site] = {
		"yearly": "0 0 1 1 *",
		"annual": "0 0 1 1 *",
		"monthly": "0 0 1 * *",
		"monthly_long": "0 0 1 * *",
		"weekly": "0 0 * * 0",
		"weekly_long": "0 0 * * 0",
		"daily": "0 0 * * *",
		"daily_long": "0 0 * * *",
		"midnight": "0 0 * * *",
		"hourly": "0 * * * *",
		"hourly_long": "0 * * * *",
		"all": "0/" + str((frappe.get_conf().scheduler_interval or 240) // 60) + " * * * *",
	}
	return site_cron_map

def start_scheduler():
	'''Run enqueue_events_for_all_sites every 2 minutes (default).
	Specify scheduler_interval in seconds in common_site_config.json'''

	from datetime import datetime
	from gevent import sleep, spawn
	while True:
		sleep_for = ((60 - datetime.now().second) % 60) or 60
		print('Scheduler Tick at', datetime.now(), 'Sleeping for', sleep_for, 'seconds')
		sleep(sleep_for)
		spawn(enqueue_events_for_all_sites)

def enqueue_events_for_all_sites():
	'''Loop through sites and enqueue events that are not already queued'''

	if os.path.exists(os.path.join('.', '.restarting')):
		# Don't add task to queue if webserver is in restart mode
		return

	sites = get_sites(sites_path='.')

	for site in sites:
		try:
			enqueue_events_for_site(site=site)
		except:
			# it should try to enqueue other sites
			print(frappe.get_traceback())

def enqueue_events_for_site(site):
	def log_and_raise():
		frappe.logger(__name__).error('Exception in Enqueue Events for Site {0}'.format(site) +
			'\n' + frappe.get_traceback())
		raise # pylint: disable=misplaced-bare-raise

	try:
		latte.init(site=site)
		if local.conf.maintenance_mode:
			return

		frappe.connect()
		if is_scheduler_disabled():
			return

		enqueue_events(site=site)

		frappe.logger(__name__).debug('Queued events for site {0}'.format(site))
	except pymysql.OperationalError as e:
		if e.args[0]==ER.ACCESS_DENIED_ERROR:
			frappe.logger(__name__).debug('Access denied for site {0}'.format(site))
		else:
			log_and_raise()
	except:
		log_and_raise()

	finally:
		frappe.destroy()

def enqueue_events(site):
	nowtime = frappe.utils.now()
	last = frappe.db.get_value('System Settings', 'System Settings', 'scheduler_last_event')

	# set scheduler last event
	frappe.db.sql('''
		insert into `tabSingles`
			(doctype, field, value)
		values
			('System Settings', 'scheduler_last_event', %(now)s)
		on duplicate key update
			value = %(now)s
	''', {
		'now': nowtime,
	})
	frappe.db.commit()

	out = []
	if last:
		last = datetime.strptime(last, DATETIME_FORMAT)
		out = enqueue_applicable_events(site, nowtime, last)

	return '\n'.join(out)

def enqueue_applicable_events(site, nowtime_str, last):
	out = []

	enabled_events = get_enabled_scheduler_events()

	def trigger_if_enabled(site, event, last):
		trigger(site, event, last)
		_log(event)

	def _log(event):
		out.append("{time} - {event} - queued".format(time=nowtime_str, event=event))

	for event in enabled_events:
		trigger_if_enabled(site, event, last)

	if "all" not in enabled_events:
		trigger_if_enabled(site, "all", last)

	return out

def trigger(site, event, last=None):
	"""Trigger method in hooks.scheduler_events."""

	queue = 'long' if event.endswith('_long') else 'short'
	timeout = queue_timeout[queue]

	if frappe.flags.in_test:
		frappe.flags.ran_schedulers.append(event)

	events_from_hooks = get_scheduler_events(event)
	if not events_from_hooks:
		return

	events = []
	if event == "cron":
		for e in events_from_hooks:
			e = get_cron_map().get(e, e)
			if croniter.is_valid(e):
				if croniter(e, last).get_next(datetime) <= frappe.utils.now_datetime():
					events.extend(events_from_hooks[e])
			else:
				frappe.log_error("Cron string " + e + " is not valid", "Error triggering cron job")
				frappe.logger(__name__).error('Exception in Trigger Events for Site {0}, Cron String {1}'.format(site, e))

	else:
		if croniter(get_cron_map()[event], last).get_next(datetime) <= frappe.utils.now_datetime():
			events.extend(events_from_hooks)

	for handler in events:
		handler, params = extract_params(handler)
		job_name = f'scheduler_job:{handler}'
		kwargs = {'params': params} if params else {}
		enqueue(
			handler,
			queue,
			timeout,
			event,
			job_name=job_name,
			**kwargs
		)

def get_scheduler_events(event):
	'''Get scheduler events from hooks and integrations'''
	return frappe.get_hooks("scheduler_events").get(event) or []

def log(method, message=None):
	"""log error in patch_log"""
	message = frappe.utils.cstr(message) + "\n" if message else ""
	message += frappe.get_traceback()

	if not (frappe.db and frappe.db._conn):
		frappe.connect()

	frappe.db.rollback()
	frappe.db.begin()

	d = frappe.new_doc("Error Log")
	d.method = method
	d.error = message
	d.insert(ignore_permissions=True)

	frappe.db.commit()

	return message

def get_enabled_scheduler_events():
	if 'enabled_events' in frappe.flags and frappe.flags.enabled_events:
		return frappe.flags.enabled_events

	enabled_events = frappe.db.get_global("enabled_scheduler_events")
	if frappe.flags.in_test:
		# TEMP for debug: this test fails randomly
		print('found enabled_scheduler_events {0}'.format(enabled_events))

	if enabled_events:
		if isinstance(enabled_events, string_types):
			enabled_events = json.loads(enabled_events)
		return enabled_events

	return ["all", "hourly", "hourly_long", "daily", "daily_long",
		"weekly", "weekly_long", "monthly", "monthly_long", "cron"]

def is_scheduler_disabled():
	if frappe.conf.disable_scheduler:
		return True

	return not frappe.utils.cint(frappe.db.get_single_value("System Settings", "enable_scheduler"))

def toggle_scheduler(enable):
	frappe.db.set_value("System Settings", None, "enable_scheduler", 1 if enable else 0)

def enable_scheduler():
	toggle_scheduler(True)

def disable_scheduler():
	toggle_scheduler(False)

def get_errors(from_date, to_date, limit):
	errors = frappe.db.sql("""select modified, method, error from `tabError Log`
		where date(modified) between %s and %s
		and error not like '%%[Errno 110] Connection timed out%%'
		order by modified limit %s""", (from_date, to_date, limit), as_dict=True)
	return ["""<p>Time: {modified}</p><pre><code>Method: {method}\n{error}</code></pre>""".format(**e)
		for e in errors]

def get_error_report(from_date=None, to_date=None, limit=10):
	from frappe.utils import get_url, now_datetime, add_days

	if not from_date:
		from_date = add_days(now_datetime().date(), -1)
	if not to_date:
		to_date = add_days(now_datetime().date(), -1)

	errors = get_errors(from_date, to_date, limit)

	if errors:
		return 1, """<h4>Error Logs (max {limit}):</h4>
			<p>URL: <a href="{url}" target="_blank">{url}</a></p><hr>{errors}""".format(
			limit=limit, url=get_url(), errors="<hr>".join(errors))
	else:
		return 0, "<p>No error logs</p>"

def scheduler_task(site, event, handler, now=False):
	'''This is a wrapper function that runs a hooks.scheduler_events method'''
	frappe.logger(__name__).info('running {handler} for {site} for event: {event}'.format(handler=handler, site=site, event=event))
	try:
		if not now:
			frappe.connect(site=site)

		frappe.flags.in_scheduler = True
		frappe.get_attr(handler)()

	except Exception:
		frappe.db.rollback()
		traceback = log(handler, "Method: {event}, Handler: {handler}".format(event=event, handler=handler))
		frappe.logger(__name__).error(traceback)
		raise

	else:
		frappe.db.commit()

	frappe.logger(__name__).info('ran {handler} for {site} for event: {event}'.format(handler=handler, site=site, event=event))

def reset_enabled_scheduler_events(login_manager):
	if login_manager.info.user_type == "System User":
		try:
			if frappe.db.get_global('enabled_scheduler_events'):
				# clear restricted events, someone logged in!
				frappe.db.set_global('enabled_scheduler_events', None)
		except pymysql.InternalError as e:
			if e.args[0]==ER.LOCK_WAIT_TIMEOUT:
				frappe.log_error(frappe.get_traceback(), "Error in reset_enabled_scheduler_events")
			else:
				raise
		else:
			is_dormant = frappe.conf.get('dormant')
			if is_dormant:
				update_site_config('dormant', 'None')

def disable_scheduler_on_expiry():
	if has_expired():
		disable_scheduler()

def restrict_scheduler_events_if_dormant():
	if is_dormant():
		restrict_scheduler_events()
		update_site_config('dormant', True)

def restrict_scheduler_events(*args, **kwargs):
	val = json.dumps(["hourly", "hourly_long", "daily", "daily_long", "weekly", "weekly_long", "monthly", "monthly_long", "cron"])
	frappe.db.set_global('enabled_scheduler_events', val)

def is_dormant(since = 345600):
	last_user_activity = get_last_active()
	if not last_user_activity:
		# no user has ever logged in, so not yet used
		return False
	last_active = get_datetime(last_user_activity)
	# Get now without tz info
	now = now_datetime().replace(tzinfo=None)
	time_since_last_active = now - last_active
	if time_since_last_active.total_seconds() > since:  # 4 days
		return True
	return False

def get_last_active():
	return frappe.db.sql("""select max(last_active) from `tabUser`
		where user_type = 'System User' and name not in ({standard_users})"""\
		.format(standard_users=", ".join(["%s"]*len(STANDARD_USERS))),
		STANDARD_USERS)[0][0]
