def do_nothing(*_, **__):
    return

ENQUEUED = []

import latte.monkey_patches.frappe
import latte.monkey_patches.frappe.handler
import latte.monkey_patches.frappe.permissions
import latte.monkey_patches.frappe.email.queue
import latte.monkey_patches.frappe.email.smtp
import latte.monkey_patches.frappe.email.email_body
import latte.monkey_patches.frappe.installer
import latte.monkey_patches.frappe.utils.data
import latte.monkey_patches.frappe.utils.file_manager
import latte.monkey_patches.frappe.utils.jinja
import latte.monkey_patches.frappe.utils.logger
import latte.monkey_patches.frappe.utils.nestedset
import latte.monkey_patches.frappe.utils.pdf
import latte.monkey_patches.frappe.utils.user
import latte.monkey_patches.frappe.utils.xlsxutils
import latte.monkey_patches.frappe.model.meta
import latte.monkey_patches.frappe.model.document
import latte.monkey_patches.frappe.model.base_document
import latte.monkey_patches.frappe.model.db_query
import latte.monkey_patches.frappe.model.db_schema
import latte.monkey_patches.frappe.model.delete_doc
import latte.monkey_patches.frappe.model.naming
import latte.monkey_patches.frappe.model.rename_doc
import latte.monkey_patches.frappe.model.sync
import latte.monkey_patches.frappe.defaults
import latte.monkey_patches.frappe.core.doctype.doctype.doctype
import latte.monkey_patches.frappe.core.doctype.error_log.error_log
import latte.monkey_patches.frappe.core.doctype.file.file
import latte.monkey_patches.frappe.core.doctype.data_export.exporter
import latte.monkey_patches.frappe.core.doctype.data_import.data_import
import latte.monkey_patches.frappe.core.doctype.data_import.importer
import latte.monkey_patches.frappe.core.doctype.notification.notification
import latte.monkey_patches.frappe.core.doctype.sms_settings.sms_settings
import latte.monkey_patches.frappe.core.doctype.user.user
import latte.monkey_patches.frappe.core.page.permission_manager.permission_manager
import latte.monkey_patches.frappe.core.page.permission_manager.permission_manager
import latte.monkey_patches.frappe.custom.doctype.customize_form.customize_form
import latte.monkey_patches.frappe.desk.doctype.desktop_icon.desktop_icon
import latte.monkey_patches.frappe.desk.form.run_method
import latte.monkey_patches.frappe.desk.form.save
import latte.monkey_patches.frappe.desk.query_report
import latte.monkey_patches.frappe.desk.reportview
import latte.monkey_patches.frappe.modules.utils
import latte.monkey_patches.frappe.website.doctype.web_form.web_form
import latte.monkey_patches.frappe.website.doctype.website_theme.website_theme
import latte.monkey_patches.frappe.website.router

import frappe.database
from latte.database_utils.connection_pool import PatchedDatabase
frappe.database.Database = PatchedDatabase

import latte.monkey_patches.pymysql.cursors
import latte.monkey_patches.werkzeug.local
import latte.monkey_patches.pandas
import latte.monkey_patches.kafka.client_async

from latte.utils.background.job import enqueue
import frappe.utils.background_jobs
frappe.utils.background_jobs.enqueue = enqueue
from latte.utils.file_patcher import patch
patch('from frappe.utils.background_jobs import enqueue', 'enqueue', enqueue)

frappe.utils.background_jobs.execute_job = lambda *_,**__: frappe.throw('''
    Latte monkeypatching has failed to patch background jobs. Are you sure you're using bench serve??
''')
import frappe.limits
frappe.limits.update_space_usage = do_nothing


import frappe
import latte
frappe.init = latte.init
frappe.connect = latte.connect
frappe.destroy = latte.destroy

from latte.realtime import publish_realtime
from frappe import realtime
realtime.publish_realtime = publish_realtime
