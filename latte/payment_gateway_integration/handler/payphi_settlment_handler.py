
from __future__ import unicode_literals
import time

import json
import frappe
from frappe.utils import cint
from frappe import local

from latte.utils.logger import get_logger
from latte.utils.caching import cache_in_mem



def handle_settlement(message):
	'''
	Function to handle settlement advice response of PayPhi Integration
	{
		"Header": {
		"DocType": "PayPhi Payment Update Log",
		"Document ID": "41686f91d0",
		"Event": "on_update",
		"Origin": "doha-synapse-spine-client",
		"Timestamp": "2021-04-08 17:17:41.723086",
		"Topic": "events.topic.payphi_settlement",
		"sha256": "ff126ead374b3e0e5430821e212fdf9ec84fbadbebcfc84fa8078e6eea3abac7"
		},
		"Payload": {
		"creation": "2021-04-08 17:17:41.715694",
		"docstatus": 0,
		"doctype": "PayPhi Payment Update Log",
		"idx": 0,
		"modified": "2021-04-08 17:17:41.715694",
		"modified_by": "Guest",
		"name": "41686f91d0",
		"owner": "Guest",
		"parent": None,
		"parentfield": None,
		"parenttype": None,
		"payphi_request_docname": "8784180691B",
		"handler":""
		"response": "{'aggregatorID': 'A_00001', 'merchantId': 'P_000XX', 'settlementID': 'P0009220210323604', 'settlementDate': '20210323', 'paymentMode': 'UPI', 'paymentSubInstType': '', 'txnChannel': 'WEB', 'merchantTxnNo': '8784180691B', 'txnCharges': '0.00', 'txnAmount': '260.00', 'serviceTax': '0.00', 'invoiceNos': '87841691', 'settledAmount': '260.00', 'settlementAccount': '337405000XX', 'settlementAccountIFSC': 'ICIC0000074', 'cmd': 'payphi_api_service.handle_settlement_advice'}"
		},
		"Retry": []
		}
	'''
	response_payload = message['Payload'].get('response')
	settlement_response = json.loads(response_payload.replace("\'", "\""))

	txn_no = message['Payload'].get('payphi_request_docname')
	settlement_id = settlement_response.get('settlementID')
	settlement_date = settlement_response.get('settlementDate')

	logger = get_logger(index_name='payphi_settlement')
	if txn_no and not frappe.db.exists('PayPhi Payment Request', txn_no):
		logger.error(f'PayPhi Request Doc {txn_no} is not present.')
		return

	logger.error(f'PayPhi Request Doc {txn_no} is present.')
	payphi_request_doc = frappe.get_doc('PayPhi Payment Request', txn_no)

	if payphi_request_doc.payment_status == 'Payment Failed':
		logger.error('Payment Request {0} is already in failed state.'.format(payphi_request_doc.name))
		return 'Ignored By Handler', None, None

	for payment_state in payphi_request_doc.payment_state:
		if (
			payment_state.update_for == 'Settlement Advice'
			and payment_state.merchant_txn_no
			and payment_state.unique_id
			and payment_state.payload
		):
			logger.error(f'Settlement Advice already present for {txn_no}.')
			return 'Ignored By Handler', None, None

	payphi_request_doc.payment_status = "Payment Settlement Advice Received"
	payphi_request_doc.append('payment_state', {
		'update_for':'Settlement Advice',
		'merchant_txn_no':txn_no,
		'unique_id': settlement_id,
		'payload': f'{settlement_response}',
		'update_time': frappe.utils.now_datetime(),
	})

	payphi_request_doc.submit()
	return 'Processed', payphi_request_doc.doctype, payphi_request_doc.name