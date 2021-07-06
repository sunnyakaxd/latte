# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "latte"
app_title = "Latte"
app_publisher = "Sachin Mane"
app_description = "Frappe Latte"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "support@with.run"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/latte/css/latte.css"
app_include_js = [
	"/assets/js/gridstack.min.js",
	"/assets/js/latte.min.js",
	"/assets/js/latte-upload.min.js",
]

app_include_css = [
	"/assets/css/gridstack.min.css"
]

# include js, css files in header of web template
# web_include_css = "/assets/latte/css/latte.css"
web_include_js = "/assets/latte/js/latte-socketio-client.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {"Report": "public/js/report.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

broadcast_channels = {
	'Email': 'latte.reminder_alert_and_notification.channels.email.EmailChannel',
	'SMS': 'latte.reminder_alert_and_notification.channels.sms.SmsChannel'
}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "latte.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "latte.install.before_install"
# after_install = "latte.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "latte.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Job Run": {
		"on_status_change": "latte.job.doctype.job.job.update_job_on_job_run_status_change",
	},
	"DocType": {
		# "before_save": "latte.utils.nestedset.update_fieldtype",
		"on_update": [
			"latte.docevents.doctype.on_update",
		],
	},
	"Custom Field": {
		"on_update": [
			"latte.docevents.custom_field.on_update",
		],
	},
	"Property Setter": {
		"on_update": [
			"latte.docevents.property_setter.on_update",
		],
	},
	(
		'Webhook', 'Notification', 'Powerflow Configuration',
		'Autoincrement Refresh', 'Scheduler Event',
	): {
		'on_update': "latte.model.hook_registry.invalidate",
	},
	"*": {
		"on_trash": [
			'latte.file_storage.file.remove_files',
		]
	}
}

# Persistence
# ---------------
persistence = {
	'Report': ['timeout', 'datasource', 'prepared_report', 'disable_prepared_report',
			   'caching_scope', 'cache_expiry', 'acceptable_data_lag', 'disabled', 'replica_priority']
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"all": [
		"latte.job.background_jobs.job_executor.job_executor",
	],
	"daily": [
		"latte.reminder_alert_and_notification.doctype.broadcast.broadcast.trigger_daily_alerts",
	],
	"cron": {
		"* * * * *": [
			'latte.database_utils.connection_pool.log_processlist',
			'latte.database_utils.connection_pool.switch_replica',
			'latte.utils.k8s.refresh_cache_host_list',
		],
		"*/10 * * * *": [
			"latte.latte_core.naming.lockless_gapless_autoname.reconcile",
			'latte.job.background_jobs.job_fixer.fix_stuck_jobs',
		],
		"0 3 * * *": [
			'latte.latte_core.doctype.job_run.job_run.remove_old_logs',
		],
		# "30 7,9,12,3 * * *": [
		# 	"latte.utils.nestedset.rebuild_all_trees",
		# ],
	}
}

dynamic_hooks = [
	'latte.quartz.doctype.scheduler_event.scheduler_event.get_hooks',
	'latte.business_process.powerflow.powerflow.get_hooks',
	'latte.dynamic_hooks.webhooks.load_webhooks',
	'latte.dynamic_hooks.notification.load_notification_hooks',
	'latte.dynamic_hooks.notification.load_broadcast_hooks',
	'latte.latte_dev_utils.doctype.autoincrement_refresh.autoincrement_refresh.get_hooks',
]

# Testing
# -------

# before_tests = "latte.install.before_tests"

# Overriding Whitelisted Methods
# ------------------------------
#
override_whitelisted_methods = {
	"frappe.core.doctype.system_settings.system_settings.load":
		"latte.overrides.core.doctype.system_settings.system_settings.load",
	"frappe.core.doctype.data_export.exporter.export_data":
		"latte.monkey_patches.frappe.core.doctype.data_export.exporter.read_only_export_data",
	"frappe.desk.form.linked_with.get_linked_docs": "latte.overrides.desk.form.linked_with.read_only_get_linked_docs",
	"frappe.desk.form.linked_with.get_linked_doctypes": "latte.overrides.desk.form.linked_with.read_only_get_linked_doctypes",
	"frappe.desk.form.load.getdoc": "latte.overrides.desk.form.load.getdoc",
	"frappe.desk.form.save.savedocs": "latte.overrides.desk.form.save.savedocs",
	"frappe.desk.query_report.export_query": "latte.overrides.desk.reportview.export_query",
	"frappe.desk.query_report.run": "latte.overrides.desk.reportview.patched_run",
	"frappe.desk.reportview.get": "latte.overrides.desk.reportview.patched_get",
	"frappe.desk.search.search_link": "latte.overrides.desk.search.search_link",
	"frappe.desk.search.search_widget": "latte.overrides.desk.search.ordered_search_widget",
	"frappe.model.db_query.get_list": "latte.overrides.frappe.model.db_query.get_list",
	"frappe.website.doctype.web_form.web_form.get_form_data": "latte.overrides.web_form.web_form.get_form_data",
	"frappe.www.printview.get_html_and_style": "latte.overrides.frappe.www.printview.get_html_and_style",
	"uploadfile": "latte.file_storage.file.uploadfile",
}

before_migrate = [
	'latte.utils.caching.flushall',
	'latte.latte_core.naming.auto_increment.move_non_auto_to_hash',
	'latte.latte_core.naming.auto_increment.cache',
	'latte.utils.persistence.persist',
	# 'latte.utils.nestedset.update_types',
]

after_migrate = [
	'latte.utils.standard_creation_tools.sync_standard_documents',
	'latte.latte_core.naming.auto_increment.reset',
	'latte.utils.indexing.index_all',
	'latte.utils.persistence.restore',
	'latte.utils.caching.flushall',
]

auto_increment_doctypes = [
	'Job Run',
	'Version',
]

boot_session = [
	"latte.boot.dashboard_access",
	"latte.boot.file_size_limit",
]

standard_doctypes = [
	'Dashboard Data Slice',
	'Dashboard Configuration',
	'Dashboard Theme',
]

# Custom URL Handlers
# url_handlers = {
# Use direct handler for the base url
#	"/app-health": "latte.app.default_handler"
# Or use a base path with multiple sub paths
#   "/apiv2": {
#		"apiname1": "qualified.path.to.handler1",
#		"apiname2": "qualified.path.to.handler2"
#   }
# }
