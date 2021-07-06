# -*- coding: utf-8 -*-
# Copyright (c) 2021, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class MerchantIntegrationPlan(Document):

	def handle_response(self, request_doc):
		error = None
		try:
			if self.response_handler:
				func = frappe.get_attr(self.response_handler)
				func(request_doc)
		except Exception as exc:
			frappe.local.db.rollback()
			error = frappe.log_error(title=f"Payphi {self.response_handler} Error".format(), message={
				'traceback': frappe.get_traceback(),
				'message_id': request_doc.name,
				'exception': exc
			}).name
		return error