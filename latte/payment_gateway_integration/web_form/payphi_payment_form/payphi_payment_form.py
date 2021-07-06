from __future__ import unicode_literals

import frappe
from frappe.utils import flt
import latte
from latte.payment_gateway_integration.doctype.payphi_payment_response_log.payphi_payment_response_log import process_transaction_response_wrapper
import json

'''
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

def get_context(context):
	# do your magic here
	pass

#====================================CALLBACK HANDLER============================================

@frappe.whitelist(allow_guest=True)
def payphi_payment_response(**kwargs):
	#ToDo - Response Page Receipt if successfull and enqueue the process transaction method
	args = kwargs
	payphi_controller = frappe.get_doc("PayPhi Settings", "PayPhi Settings")
	response = payphi_controller.validate_transaction_response(args.get('responseCode'))
	response_log = create_response_log(args)
	redirect(response, payphi_controller, response_log.name)

def	redirect(response, payphi_controller, response_log):
	route_to = [ f"/{payphi_controller.payment_unsuccessful_route}",
		f"/{payphi_controller.payment_successful_route}?name={response_log}",
		f"/{payphi_controller.payment_requested_route}",
	]
	frappe.local.response["type"] = "redirect"
	# response_page =  f"/{payphi_controller.payment_unsuccessful_route}"
	# if response == 1:
	# 	response_page = f"/{payphi_controller.payment_successful_route}?name={response_log}"
	frappe.local.response["location"] = route_to[response]

def create_response_log(args):
	# make a response log
	response_log = frappe.get_doc({
		'doctype':'PayPhi Payment Response Log',
		'response': f'{args}',
		'payphi_request_docname':args.get('merchantTxnNo'),
		'total_payment': flt(args.get('amount')),
		'status':'Ignored',
	})
	response_log.insert(ignore_permissions=True)
	frappe.db.commit()
	return response_log

#============================STORING HMAC API======================================
@frappe.whitelist(allow_guest=True)
def store_hmac(**kwargs):
	log_id = kwargs.get("txnID")
	hmac_result = kwargs.get("hmacResult")

	if log_id and hmac_result:
		frappe.db.set_value("PayPhi Payment Request", log_id, "hash_key", hmac_result)
		frappe.db.commit()