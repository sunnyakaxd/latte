# -*- coding: utf-8 -*-
# Copyright (c) 2019, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import os
from frappe.model.document import Document
from frappe.modules.utils import get_module_path
from latte.dashboard.doctype.dashboard_configuration.dashboard_configuration import make_json
from frappe.modules.export_file import export_to_files

class DashboardTheme(Document):
	def before_save(self):
		self.make_standard()

	def on_update(self):
		if frappe.get_conf().developer_mode and self.module and not frappe.flags.in_migrate:
			export_to_files(record_list=[[self.doctype, self.name]], record_module=self.module, create_init=True)

	def make_standard(self):
		if frappe.get_conf().developer_mode:
			self.is_standard = "Yes"