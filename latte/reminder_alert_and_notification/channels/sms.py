import frappe
from frappe.model.document import Document
import requests
from latte.reminder_alert_and_notification.channels.abc import ChannelABC,abstractmethod


class SmsChannel(ChannelABC):
	def send(self, doc, context):
		receivers, cc = self.get_list_of_receivers(context)
		message = frappe.render_template(self.message, context)
		receivers = receivers + cc
		for receiver in receivers:
			try:
				phone_no = frappe.get_value("User", receiver, "mobile_no")
			except:
				continue
			send_sms(message, phone_no)

def send_sms(msg, phone_no):
	'''Send sms to user.'''

	if not phone_no:
		return False
	ss = frappe.get_doc('SMS Settings', 'SMS Settings')
	if not ss.sms_gateway_url:
		return False
	args = {
		ss.message_parameter: msg
	}
	for d in ss.get("parameters"):
		args[d.parameter] = d.value
	args[ss.receiver_parameter] = phone_no
	sms_args = {
		'params': args,
		'gateway_url': ss.sms_gateway_url,
		'use_post': ss.use_post
	}
	frappe.utils.background_jobs.enqueue(method=_send_request, queue='short', timeout=300, event=None,
		is_async=True, job_name=None, now=False, **sms_args)
	return True

def _send_request(gateway_url, params, headers=None, use_post=False):
	import requests

	if not headers:
		from frappe.core.doctype.sms_settings.sms_settings import get_headers
		headers = get_headers()

	if use_post:
		response = requests.post(gateway_url, headers=headers, data=params)
	else:
		response = requests.get(gateway_url, headers=headers, params=params)

	response.raise_for_status()
	frappe.get_doc({
		'doctype': 'SMS Log',
		'sent_on': frappe.utils.nowdate(),
		'message': params.get('message'),
		'sent_to': params.get('to')
	}).insert(ignore_permissions=True)
	return response.status_code

