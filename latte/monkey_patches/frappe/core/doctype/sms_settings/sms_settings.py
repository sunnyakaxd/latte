import frappe
from frappe.core.doctype.sms_settings import sms_settings
from frappe.core.doctype.sms_settings.sms_settings import validate_receiver_nos
from six import string_types
from latte.latte_core.doctype.permission.permission import Permission


def send_via_gateway(arg):
	ss = frappe.get_doc('SMS Settings', 'SMS Settings')
	headers = get_headers(ss)

	args = {ss.message_parameter: arg.get('message')}
	for d in ss.get("parameters"):
		if not d.header:
			args[d.parameter] = d.value

	success_list = []
	for d in arg.get('receiver_list'):
		args[ss.receiver_parameter] = d
		status = send_request(ss.sms_gateway_url, args, headers, ss.use_post)

		if 200 <= status < 300:
			success_list.append(d)

	if len(success_list) > 0:
		args.update(arg)
		create_sms_log(args, success_list)
		if arg.get('success_msg'):
			frappe.msgprint("SMS sent to following numbers: {0}".format("\n" + "\n".join(success_list)))

def get_headers(sms_settings=None):
	if not sms_settings:
		sms_settings = frappe.get_doc('SMS Settings', 'SMS Settings')

	headers={'Accept': "text/plain, text/html, */*"}
	for d in sms_settings.get("parameters"):
		if d.header == 1:
			headers.update({d.parameter: d.value})

	return headers

def send_request(gateway_url, params, headers=None, use_post=False):
	import requests

	if not headers:
		headers = get_headers()

	if use_post:
		response = requests.post(gateway_url, headers=headers, data=params)
	else:
		response = requests.get(gateway_url, headers=headers, params=params)
	response.raise_for_status()
	return response.status_code

def create_sms_log(args, sent_to):
	sl = frappe.new_doc('SMS Log')
	sl.sent_on = frappe.utils.nowdate()
	sl.message = args['message'].decode('utf-8')
	sl.no_of_requested_sms = len(args['receiver_list'])
	sl.requested_numbers = "\n".join(args['receiver_list'])
	sl.no_of_sent_sms = len(sent_to)
	sl.sent_to = "\n".join(sent_to)
	sl.flags.ignore_permissions = True
	sl.for_doctype = args.get('for_doctype')
	sl.for_docname = args.get('for_docname')
	sl.for_notification = args.get('for_notification')
	sl.save()


@frappe.whitelist()
def send_sms(receiver_list, msg, sender_name = '', success_msg = True, for_docname=None, for_doctype=None, for_notification=None):
	import json
	if isinstance(receiver_list, string_types):
		receiver_list = json.loads(receiver_list)
		if not isinstance(receiver_list, list):
			receiver_list = [receiver_list]

	receiver_list = validate_receiver_nos(receiver_list)

	arg = {
		'receiver_list'		: receiver_list,
		'message'			: frappe.safe_decode(msg).encode('utf-8'),
		'success_msg'		: success_msg,
		'for_docname'		: for_docname,
		'for_notification'	: for_notification,
		'for_doctype'		: for_doctype,
	}

	if frappe.db.get_value('SMS Settings', None, 'sms_gateway_url'):
		send_via_gateway(arg)
	else:
		frappe.msgprint("Please Update SMS Settings")

sms_settings.send_sms = send_sms
