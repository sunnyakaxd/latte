# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class DocTypeMeta(Document):
	def on_update(self):
		from latte.utils.caching import invalidate
		invalidate(f'meta|{self.name}')
