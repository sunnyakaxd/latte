# -*- coding: utf-8 -*-
# Copyright (c) 2021, ElasticRun and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import hmac
import hashlib
import base64

import frappe
from frappe.model.document import Document

from frappe.utils import get_url, call_hook_method, cint, get_timestamp, get_request_session, cstr

from frappe.integrations.utils import (make_get_request, create_payment_gateway)

controller_doctype = "PayPhi Payment Controller"
controller_fields = ["merchant_id", "response_handler"]
payment_request_doctype = "PayPhi Payment Request"
request_fields_map = {'merchant_id':'merchantID', 'aggregator_id':'aggregatorID', 'amount':'txnAmount',
					'name':'merchantTxnID', 'return_url':'returnURL', 'api_param':'apiparam', 'generated_hash_key':'code',
					'formatted_txn_datetime':'txnDate'}

field_map_for_hash = {
	'aggregatorID':'aggregator_id',
	'amount':'amount',
	'currencyCode':'356',
	'merchantID':'merchant_id',
	'merchantTxnNo':'name',
	'payType':'0',
	'returnURL':'return_url',
	'transactionType':'SALE',
	'txnDate':'formatted_txn_datetime',
}

gateway = "PayPhi"

class PayPhiSettings(Document):
	supported_currencies = ["INR"]
	payment_successful_responses = ["000","0000"]
	payment_in_processing_response = ["R1000"]

	def validate(self):

		# if not self.aggregator_id:
		# 	frappe.throw('Please mention PayPhi Aggregator ID.')
		if not self.payphi_form_link:
			frappe.throw('Please mention PayPhi HTML path to proceed.')
		self.validate_payphi_credentials()
		create_payment_gateway('PayPhi')
		call_hook_method('payment_gateway_enabled', gateway=gateway)
		frappe.db.set_value('Payment Gateway', gateway, 'gateway_settings', self.name)

	# def on_update(self):
	# 	controllers = frappe.get_all(controller_doctype, fields=controller_fields)
	# 	self.update_controllers(controllers)

	# def update_controllers(self, controllers=[]):
	# 	count = 0
	# 	if not controllers:
	# 		for controller in self.plan:
	# 			self.create_controller(controller)

	# 			count += 1
	# 		frappe.msgprint(f"{count} PayPhi controllers created.")
	# 	else:
	# 		plans = self.plan[:]
	# 		for cl in controllers:
	# 			for c in plans:
	# 				if c.merchant_id == cl.merchant_id:
	# 					doc = frappe.get_doc(controller_doctype, cl.name)
	# 					doc.response_handler = c.response_handler or self.response_handler
	# 					doc.save()
	# 					plans.remove(c)
	# 		if plans:
	# 			for plan in plans:
	# 				self.create_controller(plan)
	# 				count += 1
	# 			frappe.msgprint(f"{count} PayPhi controllers created.")

	# def create_controller(self, controller):
	# 	doc_args = {"doctype": controller_doctype}
	# 	for fields in controller_fields:
	# 		doc_args[fields] = controller.get(fields)
	# 	doc = frappe.get_doc(doc_args)
	# 	doc.insert(ignore_permissions=True)

	def validate_payphi_credentials(self):
		#check validation of Aggregator ID
		pass

	def validate_transaction_response(self, response):
		if response in self.payment_in_processing_response:
			return 2
		if response not in self.payment_successful_responses:
			return 0
		return 1

	def validate_transaction_currency(self, currency):
		if currency not in self.supported_currencies:
			frappe.throw(f"Please select another payment method. PayPhi does not support transactions in currency '{currency}'")

	def get_custom_handler(self, merchant_id):
		for handler in self.plan:
			if handler.merchant_id == merchant_id:
				return handler

	#redirect URL method
	def get_payment_url(self, **kwargs):
		request_doc = frappe.get_doc(payment_request_doctype, kwargs.get('reference_docname'))
		request_headers = {request_fields_map[key]:val for key,val in request_doc.get().items() if key in request_fields_map}
		# request_headers['txnDate'] = request_doc.transaction_date.strftime("%Y%m%d%H%M%S")
		request_parameters_str, _ = add_parameters_to_request(request_headers)
		redirect_url = self.payphi_form_link + '?' + request_parameters_str
		if request_doc.expired:
			frappe.throw('Cannot proceed, this payment link is expired.')
		request_doc.db_set('expired', 1)
		return get_url(redirect_url)

	def merchant_id_exists(self, merchant_id):
		for mid in self.plan:
			if mid.merchant_id == merchant_id:
				return mid.merchant_id
		frappe.throw('Merchant ID is invalid.')

	def create_payment_request(self, ref_dt, ref_dn, amount, merchant_id):
		#todo - merchant ID logic
		self.merchant_id_exists(merchant_id)
		doc = frappe.get_doc({
			'doctype':payment_request_doctype,
			'reference_doctype':ref_dt,
			'reference_docname':ref_dn,
			'amount':amount,
			'merchant_id': merchant_id,
			'aggregator_id':self.aggregator_id or '',
			'gateway':gateway,
			'return_url':self.return_url,
			'api_param': self.post_api,
			'transaction_date':frappe.utils.now_datetime(),
			'formatted_txn_datetime':frappe.utils.now_datetime().strftime("%Y%m%d%H%M%S")
		})
		doc.insert(ignore_permissions=True)
		doc.db_set('generated_hash_key', self.calculate_secure_hash(doc))
		frappe.msgprint(f'PayPhi payment request created <b><a href = "/desk#Form/{payment_request_doctype}/{doc.name}" target="_blank">{doc.name}</a></b>')
		return doc

	def calculate_secure_hash(self, doc):
		ordered_keys = sorted(field_map_for_hash.keys())
		hash_string = ''
		for key in ordered_keys:
			if field_map_for_hash.get(key) in request_fields_map:
				hash_string += str(doc.get(field_map_for_hash[key]))
			else:
				hash_string += str(field_map_for_hash[key])
		encoded_string = hash_string.encode('utf_8')
		key = self.hash_key.encode('utf_8')
		h = hmac.new( key, encoded_string, hashlib.sha256 ).hexdigest()
		print(hash_string)
		return h

def add_parameters_to_request(parameters):
	route_string = ""
	delimeter = ''
	if isinstance(parameters, dict):
		for key in parameters:
			route_string += delimeter + key + "=" + cstr(parameters[key])
			delimeter = '&'
	return (route_string, delimeter)
