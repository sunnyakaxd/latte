# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class StorageAdapterSettings(Document):
	__CACHE__ = {}

	@staticmethod
	def get_adapter_by_name(adapter_type):
		return frappe.get_cached_doc(f'Storage Adapter {adapter_type}')

	@staticmethod
	def get_default_adapter_name():
		return frappe.db.get_single_value('Storage Adapter Settings', 'default_adapter') or 'File'

	@staticmethod
	def get_default_adapter():
		return StorageAdapterSettings.get_adapter_by_name(StorageAdapterSettings.get_default_adapter_name())

	def get_adapter_for_dt(self, dt):
		dt_adapter = [row.adapter for row in self.doctype_wise_adapters if row.ref_doctype == dt]
		if dt_adapter:
			return StorageAdapterSettings.get_adapter_by_name(dt_adapter[0])
		return StorageAdapterSettings.get_default_adapter()

	def validate(self):
		adapters = {row.adapter for row in self.doctype_wise_adapters}
		adapters.add(self.default_adapter)
		for adapter_type in adapters:
			adapter = self.get_adapter_by_name(adapter_type)
			if hasattr(adapter, 'validate_settings'):
				adapter.validate_settings()

