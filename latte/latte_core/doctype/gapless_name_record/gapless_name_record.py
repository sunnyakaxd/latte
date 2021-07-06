# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from latte.utils.indexing import create_index

class GaplessNameRecord(Document):
	pass

def on_doctype_update():
	create_index('tabGapless Name Record', ['naming_series', 'status', 'generated_name'])