
from __future__ import unicode_literals
import time

import json
import frappe
from frappe.utils import cint
from frappe import local

from latte.utils.logger import get_logger
from latte.utils.caching import cache_in_mem



def handle_payment_advice(message):
	'''
	Function to handle Payment advice response of PayPhi Integration
	{
	"secureHash":"f2b13f56fb78357a0e0e3f2edd71679a7e0467b2b74cba23f1659953292c02a2",
	"amount":"5000.00",
	"paymentSubInstType":"Phicom Test bank",
	"respDescription":"Transaction successful",
	"paymentMode":"NB",
	"merchantId":"T_05001",
	"paymentID":"88741815958",
	"merchantTxnNo":"IER-ADR-00056",
	"aggregatorID":"J_00157",
	"paymentDateTime":"20210210135115",
	"txnID":"T002272266726",
	"responseCode":"0000",
	"cmd":"latte.payment_gateway_integration.web_form.payphi_payment.payphi_payment.payphi_payment_response"
	}
	'''
	response_payload = message['Payload'].get('response')
	payment_response = json.loads(response_payload.replace("\'", "\""))

	txn_no = message['Payload'].get('payphi_request_docname')
	payment_id = payment_response.get('paymentID')
	payment_date = frappe.utils.nowdate()

	logger = get_logger(index_name='payphi_settlement')
	if txn_no and not frappe.db.exists('PayPhi Payment Request', txn_no):
		logger.error(f'PayPhi Request Doc {txn_no} is not present.')
		return 'Ignored By Handler', None, None

	logger.error(f'PayPhi Request Doc {txn_no} is present for payment advice.')
	payphi_request_doc = frappe.get_doc('PayPhi Payment Request', txn_no)

	if payphi_request_doc.payment_status == 'Payment Failed':
		logger.error('Payment Request {0} is already in Failed state.'.format(payphi_request_doc.name))
		return 'Ignored By Handler', None, None

	for payment_state in payphi_request_doc.payment_state:
		if (
			payment_state.update_for == 'Payment Advice'
			and payment_state.merchant_txn_no
			and payment_state.unique_id
			and payment_state.payload
		):
			logger.error(f'Payment Advice already present for {txn_no}.')
			return 'Ignored By Handler', None, None

	payphi_request_doc.payment_status = "Payment Advice Received"
	payphi_request_doc.append('payment_state', {
		'update_for':'Payment Advice',
		'merchant_txn_no':txn_no,
		'unique_id': payment_id,
		'payload': f'{payment_response}',
		'update_time': frappe.utils.now_datetime(),
	})

	payphi_request_doc.save(ignore_permissions=True)
	return 'Processed', payphi_request_doc.doctype, payphi_request_doc.name