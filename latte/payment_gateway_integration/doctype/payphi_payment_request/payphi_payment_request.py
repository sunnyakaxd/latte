# -*- coding: utf-8 -*-
# Copyright (c) 2021, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, requests
from frappe.model.document import Document
from latte.latte_core.naming.autoname import lockless_autoname
from latte.utils.logger import get_logger
from latte.json import dumps, loads

class PayPhiPaymentRequest(Document):
	def autoname(self):

		prefix = frappe.get_value('Merchant Integration Plan', {'parent':'PayPhi Settings'}, 'merchant_id')
		self.naming_series = f'{prefix}-############'
		return lockless_autoname(self)

	def on_update(self):
		self.remote_txn_id = self.set_remote_txn_id()
		app_merchant_id = frappe.get_value('Merchant Integration Plan', {'parent':'PayPhi Settings'}, 'merchant_id')
		if not app_merchant_id:
			logger = get_logger(index_name='PayPhi Merchant ID')
			logger.error('Merchant ID not present.')
			return
		settlement_advice_processor, payment_advice_processor = frappe.db.get_value('Merchant Integration Plan', {
		'parent':'PayPhi Settings',
		'merchant_id':app_merchant_id
		}, ['settlement_advice_processor', 'payment_advice_processor'])
		if not (settlement_advice_processor and payment_advice_processor):
			logger = get_logger(index_name='payphi_post_processors_not_found')
			logger.error('Advice processors not present.')
			return
		processor = payment_advice_processor
		for state in self.payment_state:
			try:
				if state.update_for != 'Payment Advice':
					processor = settlement_advice_processor
				func = frappe.get_attr(processor)
				args = self.as_dict()
				args.update({'for':state.update_for, 'unique_id': state.unique_id})
				func(args)
			except Exception as exc:
				error = frappe.log_error(title=f"Payphi {state.update_for} Error".format(), message={
					'traceback': frappe.get_traceback(),
					'message_id': state.unique_id,
					'exception': exc
				}).name
				raise Exception(f'{frappe.get_traceback()}')

	def before_save(self):
		self.create_payment_link()
		self.recreate_request()

	def create_payment_link(self):
		self.payment_url = f'{frappe.conf.site_url}/payphi-payment-form?name={self.name}'

	def recreate_request(self):
		if self.payment_status == 'Payment Failed':
			controller = frappe.get_doc("PayPhi Settings","PayPhi Settings")
			duplicate_doc = frappe.copy_doc(self)
			duplicate_doc.expired = 0
			duplicate_doc.payment_url = ''
			duplicate_doc.payment_state = []
			duplicate_doc.payment_status = ''
			duplicate_doc.response_message = ''
			duplicate_doc.transaction_date = frappe.utils.now_datetime()
			duplicate_doc.remote_txn_id = ''
			duplicate_doc.formatted_txn_datetime = frappe.utils.now_datetime().strftime("%Y%m%d%H%M%S")
			duplicate_doc.insert(ignore_permissions=True)
			duplicate_doc.db_set('generated_hash_key',controller.calculate_secure_hash(duplicate_doc))

	def set_remote_txn_id(self):
		if not self.remote_txn_id and self.payment_state:
			payload = eval(self.payment_state[0].payload)
			self.remote_txn_id = payload.get('txnID')

@frappe.whitelist()
def get_latest_txn_status(merchant_txn_no, original_txn_no, merchant_id, aggregator_id=None):
	'''
	{
	"txnRespDescription":"Transaction successful",
	"secureHash":"2419eccd353a928eae214ada89f5e8b07608c786dc7b35372d406ec4ac646773",
	"amount":"20.00",
	"txnResponseCode":"0000",
	"txnAuthID":"115516648685",
	"respDescription":"Request processed successfully",
	"paymentMode":"UPI",
	"responseCode":"000",
	"txnStatus":"SUC",
	"merchantId":"P_30233",
	"merchantTxnNo":"T500013372187",
	"paymentDateTime":"20210604164524",
	"txnID":"T500013372187"
	}
	'''

	TRANSACTION_TYPE = 'STATUS'
	logger = get_logger(index_name='transaction_status_payphi')

	if not (merchant_txn_no and original_txn_no and merchant_id):
		logger.error('Parameters invalid.')
		frappe.msgprint('Parameters not valid.')
		return

	request_payload = {
		'merchantTxnNo': merchant_txn_no,
		'originalTxnNo': original_txn_no,
		'transactionType': TRANSACTION_TYPE,
		'merchantID': merchant_id,
	}
	if aggregator_id:
		request_payload.update({
			'aggregatorID':aggregator_id
		})
	headers = {
		'content-type':'application/x-www-form-urlencoded'
	}

	status_api_url = frappe.get_single('PayPhi Settings').transaction_status_api

	payload = '&'.join(f'{key}={request_payload[key]}'for key in request_payload)

	if not status_api_url:
		logger.error('No Transaction API url configured.')
		frappe.msgprint('No Transaction API url configured.')
		return

	response = requests.post(status_api_url, data=payload, headers=headers)

	if response.status_code >= 400:
		logger.error(f'Response returned code {response.status_code} from PayPhi')
		return

	response = loads(response.text)
	frappe.db.set_value('PayPhi Payment Request', merchant_txn_no, 'latest_transaction_status', response.get('respDescription'))
	frappe.db.commit()