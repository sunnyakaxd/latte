import frappe
from frappe.core.doctype.error_log.error_log import ErrorLog
from latte.utils.logger import get_logger
from frappe import local

def log_to_logger(self):
	try:
		get_logger(index_name='error_log').error(self)
	except:
		pass

old_insert = ErrorLog.insert

def insert(self, *_, **__):
	if local.conf.db_error_log_disabled and not self.flags.save_to_db:
		log_to_logger(self)
		return self

	retval = old_insert(self, *_, **__)
	log_to_logger(self)
	return retval

ErrorLog.insert = insert

def set_old_logs_as_seen():
	pass

@frappe.whitelist()
def clear_error_logs():
	'''Flush all Error Logs'''
	frappe.only_for('System Manager')
	frappe.db.commit()
	frappe.db.sql('''truncate `tabError Log`''')

frappe.core.doctype.error_log.error_log.set_old_logs_as_seen = set_old_logs_as_seen
frappe.core.doctype.error_log.error_log.clear_error_logs = clear_error_logs
