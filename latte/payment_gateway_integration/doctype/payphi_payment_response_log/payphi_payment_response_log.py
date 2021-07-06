# -*- coding: utf-8 -*-
# Copyright (c) 2021, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

from latte.json import loads


class PayPhiPaymentResponseLog(Document):
	# def after_insert(self):
	# 	if self.response and self.payphi_request_docname:
	# 		self.process_transaction_response()
	def on_update(self):
		frappe.utils.background_jobs.enqueue(
			process_transaction_response_wrapper,
			response_log = self
		)

	def process_transaction_response(self):
		if not self.response:
			return
		#json acceptable string
		response = self.response.replace("'", "\"")

		args = loads(response)
		payphi_controller = frappe.get_doc("PayPhi Settings", "PayPhi Settings")
		success = payphi_controller.validate_transaction_response(args.get('responseCode'))
		request_doc = frappe.get_doc('PayPhi Payment Request', args.get('merchantTxnNo'))
		request_doc.remote_txn_id = args.get('txnID')
		if request_doc.docstatus == 0:
			if success==1:
				request_doc.payment_status = "Payment Transacted" if not request_doc.payment_status else request_doc.payment_status
				request_doc.response_message = f'{args}'
				request_doc.received_hash_key = args.get("secureHash")
				request_doc.transaction_date = frappe.utils.nowdate()
				response_controller = payphi_controller.get_custom_handler(args.get('merchantId'))
				self.error_log = response_controller.handle_response(request_doc)
				if not self.error_log:
					request_doc.save()
					self.db_set('status', 'Processed')
				else:
					# request_doc.payment_status = "Payment Failed"
					self.db_set('error_log', self.error_log)
					self.db_set('status','Failed')
					request_doc.save()
			elif success == 0:
				request_doc.payment_status = "Payment Failed"
				request_doc.response_message = f'{args}'
				request_doc.save()
			elif success == 2:
				request_doc.payment_status = "Payment Request Initiated"
				request_doc.response_message = f'{args}'
				request_doc.save()

			frappe.db.commit()

def process_transaction_response_wrapper(response_log):
	response_log.process_transaction_response()

@frappe.whitelist()
def retry(doc):
	doc = loads(doc)
	frappe.local.db.set_value(doc.get('doctype'), doc.get('name'), 'error_log', '')
	frappe.local.db.set_value(doc.get('doctype'), doc.get('name'), 'status', '')
	frappe.db.commit()
	doc.pop('__onload')
	doc = PayPhiPaymentResponseLog(doc)
	doc.on_update()
	frappe.msgprint('Enqueued for retry')
