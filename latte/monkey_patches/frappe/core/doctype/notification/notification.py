import frappe
import json
import requests

from six import string_types
from frappe.utils.background_jobs import enqueue
from frappe.utils import nowdate, parse_val
from frappe.email.doctype.notification import notification
from frappe.core.doctype.sms_settings.sms_settings import validate_receiver_nos

from latte.monkey_patches.frappe.core.doctype.sms_settings.sms_settings import send_sms
from latte.json import dumps



def send(self, doc):
	'''Build recipients and send Notification'''

	context = get_context(doc)
	context = {"doc": doc, "alert": self, "comments": None}
	if doc.get("_comments"):
		context["comments"] = json.loads(doc.get("_comments"))

	if self.is_standard:
		self.load_standard_properties(context)

	if self.channel == 'Email':
		frappe.enqueue(
			self.send_an_email,
			queue='long',
			timeout=300,
			enqueue_after_commit=True,
			doc=doc,
			context=context,
		)

	if self.channel == 'Slack':
		self.send_a_slack_msg(doc, context)

	if self.channel == 'SMS':
		total_sent = len(frappe.db.get_all('SMS Log', {
			'for_docname': doc.name,
			'for_doctype': doc.doctype,
			'for_notification': self.name,
		}))
		if self.max_retries and total_sent >= self.max_retries:
			return

		frappe.enqueue(
			self.send_a_sms,
			queue='long',
			timeout=300,
			enqueue_after_commit=True,
			doc = doc,
			context = context,
		)

	if self.channel == "WhatsApp":
		self.send_a_whatsapp(doc,context)

	if self.set_property_after_alert:
		frappe.db.set_value(doc.doctype, doc.name, self.set_property_after_alert,
			self.property_value, update_modified = False)
		doc.set(self.set_property_after_alert, self.property_value)

def get_context(doc):
	return {"doc": doc, "nowdate": nowdate, "frappe.utils": frappe.utils, "flt":frappe.utils.flt}

def evaluate_alert_patched(doc, alert, event):
	from jinja2 import TemplateError
	try:
		if isinstance(alert, string_types):
			alert = frappe.get_doc("Notification", alert)

		context = get_context(doc)

		if alert.condition:
			if alert.is_doc_attribute:
				if not frappe.safe_eval(f'doc.{alert.condition}()', None, context):
					return
			else:
				if not frappe.safe_eval(alert.condition, None, context):
					return

		if event=="Value Change" and not doc.is_new():
			try:
				db_value = frappe.db.get_value(doc.doctype, doc.name, alert.value_changed)
			except pymysql.InternalError as e:
				if e.args[0]== ER.BAD_FIELD_ERROR:
					alert.db_set('enabled', 0)
					frappe.log_error('Notification {0} has been disabled due to missing field'.format(alert.name))
					return

			db_value = parse_val(db_value)
			if (doc.get(alert.value_changed) == db_value) or \
				(not db_value and not doc.get(alert.value_changed)):

				return # value not changed

		if event != "Value Change" and not doc.is_new():
			# reload the doc for the latest values & comments,
			# except for validate type event.
			doc = frappe.get_doc(doc.doctype, doc.name)
		alert.send(doc)
	except TemplateError:
		frappe.throw("Error while evaluating Notification {0}. Please fix your template.".format(alert))
	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(), title=str(e))
		frappe.throw("Error in Notification")

def send_a_sms(self, doc, context):
	from latte.utils.logger import get_logger

	recipients, cc, bcc = self.get_list_of_recipients(doc, context)
	recipients =  [row.strip() for row in (recipients + cc + bcc) if (row or '').strip()]
	message = frappe.render_template(self.message, context)
	total_sent = len(frappe.db.get_all('SMS Log', {
		'for_docname': doc.name,
		'for_doctype': doc.doctype,
		'for_notification': self.name,
	}))
	logger = get_logger(index_name='Send SMS')
	if self.max_retries and total_sent >= self.max_retries:
		logger.debug('SMS Limit exceeded for {0} for alert {1}'.format(doc.name, self.name))
		return
	send_sms(recipients, message, for_docname=doc.name, for_doctype=doc.doctype, for_notification=self.name)

def validate_condition(self):
	from frappe.model.base_document import get_controller
	temp_doc = frappe.new_doc(self.document_type)
	if self.condition:
		try:
			frappe.safe_eval(self.condition, None, get_context(temp_doc))
		except Exception:
			try:
				if self.is_doc_attribute and hasattr(get_controller(self.document_type), self.condition):
					return
			except Exception:
				pass
			frappe.throw("The Condition class method or attribute '{0}' is invalid".format(self.condition))

def send_whatsapp(recipient_list, url, message=None, filedata=None, filename=None, template_name=None, template_params=None, params_header=None):

	for recipient in recipient_list:
		if template_name:
			params_header = params_header or "Default"
			if filedata:
				json_message = {
					"Header": {
						"auth": "94f82bd6e1dab59:cd989119c7914cf",
						"service_id": "Synapse:Whatsapp",
						"service_type": "sync",
						"service_version": "1.0",
						"api_name": "send_media_template",
						"account_name": "Withrun",
					},
					"Payload": {
						"filename": filename,
						"filedata": filedata,
						"template_name": template_name,
						"params_header": params_header,
						"params": template_params,
						"customer_number": f"+91{recipient}",
					}
				}
			else:
				json_message = {
					"Header": {
						"auth": "94f82bd6e1dab59:cd989119c7914cf",
						"service_id": "Synapse:Whatsapp",
						"service_type": "sync",
						"service_version": "1.0",
						"api_name": "send_text_template",
						"account_name": "Withrun",
					},
					"Payload": {
						"customer_number": f"+91{recipient}",
						"template_name": template_name,
						"params": template_params,
						"lang_code": 'en',
					}
				}
			print(json_message)
		else:
			if filedata:
				json_message = {
					"Header": {
						"auth": "94f82bd6e1dab59:cd989119c7914cf",
						"service_id": "Synapse:Whatsapp",
						"service_type": "sync",
						"service_version": "1.0",
						"api_name": "send_media_message",
						"account_name": "Withrun",
					},
					"Payload": {
						"filename": filename,
						"filedata": filedata,
						"body": message,
						"customer_number": f"+91{recipient}",
					}
				}

			else:
				json_message = {
					"Header": {
						"auth": "94f82bd6e1dab59:cd989119c7914cf",
						"service_id": "Synapse:Whatsapp",
						"service_type": "sync",
						"service_version": "1.0",
						"api_name": "send_text_message",
						"account_name": "Withrun",
					},
					"Payload": {
						"customer_number": f"+91{recipient}",
						"body": message,
						"lang_code": 'en',
					}
				}

		response_status = requests.post(url, data = dumps(json_message), headers=params_header)
		return response_status, dumps(json_message)

def create_whatsapp_log(reference_notification, reference_doctype, reference_docname, mobile_number, template_name, log, response_status):
	doc = frappe.get_doc({
		'doctype':'WhatsApp Log',
		'reference_notification': reference_notification,
		'reference_doctype': reference_doctype,
		'reference_docname': reference_docname,
		'response': f'{response_status.json()}',
		'message_content': log,
		'template_name':template_name,
		'user_mobile_number':mobile_number,
	}).insert(ignore_permissions=True)


def extract_params_for_notification(notification, doc, context):
	ordered_params = sorted(notification.params, key=lambda x:x.idx)
	order_params = [frappe.render_template(param.param_value, context) for param in ordered_params]
	param_string = ','.join(f'"{param}"' for param in order_params)
	return param_string

def send_a_whatsapp(self, doc, context):
	recipients, cc, bcc = self.get_list_of_recipients(doc, context)
	recipients =  [row.strip() for row in (recipients + cc + bcc) if (row or '').strip()]

	recipient_list = validate_receiver_nos(recipients)
	template_param_string = extract_params_for_notification(self, doc, context)
	headers = {'content-type': 'application/json'}

	url = self.api_url
	message = frappe.render_template(self.message, context)
	if not self.template_name:
		attachment = self.get_attachment(doc)
	mobile_no = recipients[0]
	response_status, log = send_whatsapp(recipients, url, message=message,
		template_params=template_param_string, template_name=self.template_name, params_header=headers)
	create_whatsapp_log(self.name, doc.doctype, doc.name, mobile_no, self.template_name, log, response_status)

# Notification, get_context, evaluate_alert
notification.Notification.send = send
notification.Notification.send_a_sms = send_a_sms
notification.Notification.validate_condition = validate_condition
notification.evaluate_alert = evaluate_alert_patched
notification.Notification.send_a_whatsapp = send_a_whatsapp