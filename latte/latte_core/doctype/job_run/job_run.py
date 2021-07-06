# -*- coding: utf-8 -*-
# Copyright (c) 2019, ElasticRun and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from latte.utils.indexing import create_index

class JobRun(Document):
	def db_insert(self):
		self.run_date = frappe.utils.nowdate()
		super().db_insert()

def on_doctype_update():
	create_index('tabJob Run', ['method', 'run_date'])
	create_index('tabJob Run', ['parent'])

def remove_old_logs():
	frappe.db.sql('delete from `tabJob Run` where modified <= %(today)s - interval 4 day', {
		'today': frappe.utils.nowdate(),
	})
	frappe.db.commit()
