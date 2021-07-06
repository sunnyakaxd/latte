# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json, os
from frappe import _
from frappe.model.document import Document
from frappe.core.doctype.role.role import get_emails_from_role
from frappe.utils import validate_email_add, nowdate, parse_val, is_html
from frappe.utils.jinja import validate_template
from frappe.modules.utils import export_module_json, get_doc_module
from frappe.utils.background_jobs import enqueue
from six import string_types
from frappe.integrations.doctype.slack_webhook_url.slack_webhook_url import send_slack_message
from frappe.core.doctype.sms_settings.sms_settings import send_sms
from latte.reminder_alert_and_notification.whatsapp import send_whatsapp
# from latte.reminder_alert_and_notification.ulterius import send_ulterius, send_ulterius_request
from datetime import datetime
import pymysql
from pymysql.constants import ER
from frappe import local


class Broadcast(Document):
	@staticmethod
	def get_channel(channel):
		return frappe.get_attr(frappe.get_hooks('broadcast_channels')[channel][0])

	def onload(self):
		'''load message'''
		if self.is_standard:
			self.message = self.get_template()

	def autoname(self):
		if not self.name:
			self.name = self.subject

	def validate(self):
		if self.subject:
			validate_template(self.subject)
		if self.message:
			validate_template(self.message)

		if self.event in ("Days Before", "Days After") and not self.date_changed:
			frappe.throw(_("Please specify which date field must be checked"))

		if self.event=="Value Change" and not self.value_changed:
			frappe.throw(_("Please specify which value field must be checked"))

		self.validate_forbidden_types()
		self.validate_condition()
		self.validate_standard()

	def on_update(self):
		if self.scheduler_event:
			# delete the previous linked scheduler event
			scheduler_event=self.scheduler_event
			local.db.set_value("Broadcast", self.name, "scheduler_event", "")
			frappe.delete_doc("Scheduler Event", scheduler_event, force=True)

		if (self.schedule_notification==1):
			self.event = ""
			if self.frequency == "Hourly":
				cron_string = "0 * * * *"
			elif self.frequency == "Daily":
				cron_string = f"0 {self.notification_time} * * *"
			elif self.frequency == "Weekly":
				weekday = {"SUN":0,"MON":1,"TUE":2,"WED":3,"THU":4,"FRI":5,"SAT":7}
				cron_string=f"0 {self.notification_time} * * {weekday[self.weekday]}"
			elif self.frequency == "Monthly":
				cron_string = f"0 {self.notification_time} {self.notification_date} * *"
			elif self.frequency == "Specific Date":
				specific_date = datetime.strptime(self.specific_date,"%Y-%m-%d")
				cron_string = f"0 {self.notification_time} {specific_date.day} {specific_date.month} *"
			else:
				raise ValueError(f'Frequency type {self.frequency} not supported')

			scheduler_event = frappe.get_doc({
				'doctype': "Scheduler Event",
				"event_type": "Cron",
				"event": cron_string,
				"handler": f"latte.reminder_alert_and_notification.ulterius.execute_scheduled_broadcast('{self.name}')",
				"ref_doctype": self.doctype,
				"ref_docname": self.name
			})
			scheduler_event.insert(ignore_permissions=True)
			self.db_set("scheduler_event", scheduler_event.name)
			if not self.document_type and not self.event:
				current_date = frappe.utils.now_datetime()
				valid_till = datetime.strptime(self.valid_till, "%Y-%m-%d %H:%M:%S")
				if valid_till >= current_date:
					self.send(None)

		path = export_module_json(self, self.is_standard, self.module)
		if path:
			# js
			if not os.path.exists(path + '.md') and not os.path.exists(path + '.html'):
				with open(path + '.md', 'w') as f:
					f.write(self.message)

			# py
			if not os.path.exists(path + '.py'):
				with open(path + '.py', 'w') as f:
					f.write("""from __future__ import unicode_literals
import frappe

def get_context(context):
	# do your magic here
	pass
""")

	def validate_standard(self):
		if self.is_standard and not frappe.conf.developer_mode:
			frappe.throw(_('Cannot edit Standard Broadcast. To edit, please disable this and duplicate it'))

	def validate_condition(self):
		if self.document_type:
			temp_doc = frappe.new_doc(self.document_type)
			if self.condition:
				try:
					frappe.safe_eval(self.condition, None, get_context(temp_doc))
				except:
					frappe.msgprint("The Condition is invalid")
					raise

	def validate_forbidden_types(self):
		forbidden_document_types = ("Email Queue",)
		if self.document_type and (
			self.document_type in forbidden_document_types
			or frappe.get_meta(self.document_type).istable
		):
			frappe.throw(_("Cannot set Broadcast on Document Type {0}").format(self.document_type))

	def get_documents_for_today(self):
		'''get list of documents that will be triggered today'''
		docs = []

		diff_days = self.days_in_advance
		if self.event == "Days After":
			diff_days = -diff_days
		for name in local.db.sql_list(f"""
			select
				name
			from
				`tab{self.document_type}`
			where
				DATE(`{self.date_changed}`) = ADDDATE(DATE(%(today)s) , INTERVAL %(diff_days)s DAY)
		""", {
			'today': nowdate(),
			'diff_days': diff_days or 0
		}):
			doc = frappe.get_doc(self.document_type, name)

			if self.condition and not frappe.safe_eval(self.condition, None, get_context(doc)):
				continue

			docs.append(doc)
		return docs

	def send(self, doc=None):
		'''Build recipients and send Notification'''

		context = get_context(doc)
		context = {"doc": doc, "alert": self, "comments": None}
		if doc and doc.get("_comments"):
			context["comments"] = json.loads(doc.get("_comments"))

		if self.is_standard:
			self.load_standard_properties(context)

		frappe.utils.background_jobs.enqueue(
			Broadcast.get_channel(self.channel).send,
			enqueue_after_commit=True,
			doc=doc,
			context=context,
			self=self
		)

		if self.set_property_after_alert:
			local.db.set_value(doc.doctype, doc.name, self.set_property_after_alert,
				self.property_value, update_modified = False)
			doc.set(self.set_property_after_alert, self.property_value)

	def send_a_slack_msg(self, doc, context):
			send_slack_message(
				webhook_url=self.slack_webhook_url,
				message=frappe.render_template(self.message, context),
				reference_doctype = doc.doctype,
				reference_name = doc.name)

	def send_a_sms(self, doc, context):
		recipients, cc, bcc = self.get_list_of_recipients(doc, context)
		recipients =  [row.strip() for row in (recipients + cc + bcc) if (row or '').strip()]
		message = frappe.render_template(self.message, context)
		send_sms(recipients, message)

	def send_a_whatsapp(self, doc, context):
		recipients, cc, bcc = self.get_list_of_recipients(doc, context)
		recipients =  [row.strip() for row in (recipients + cc + bcc) if (row or '').strip()]
		message = frappe.render_template(self.message, context)
		attachment = self.get_attachment(doc)
		mobile_no = recipients[0]
		chat_room = local.db.get_value('Chat Room', filters={
			'from_mobile_no': ['in', [mobile_no, f'91{mobile_no}']],
		})
		if chat_room:
			if attachment:
				print_format = attachment[0].get('print_format')
				attachment = doc.attach_print(print_format)
				content = {
					"path": attachment.file_url,
					"caption": doc.doctype,
					"name": f'{doc.name}.pdf',
					"template_name": "materialrequest",
				}
				frappe.get_doc({
					'doctype': "Chat Message",
					'room_type': "Group",
					'sender_name': frappe.session.user,
					'type': "File",
					'room': chat_room,
					'user': 'Administrator',
					'content': json.dumps(content),
				}).insert(ignore_permissions=True)

			else:
				frappe.get_doc({
					'doctype': 'Chat Message',
					'sender_name': frappe.session.user,
					'room': chat_room,
					'room_type': 'Group',
					'type': 'Content',
					'user': frappe.session.user,
					'content': message,
				}).insert(ignore_permissions=True)
		else:
			send_whatsapp(recipients=recipients,message=message)


	# def send_ulterius_notification(self,doc,context):
	# 	receivers,cc=self.get_list_of_receivers(context)
	# 	receivers =  [row.strip() for row in (receivers + cc) if (row or '').strip()]
	# 	message = frappe.render_template(self.message, context)
	# 	send_ulterius(recipients=receivers,message=message,doc=doc,broadcast=self)

	# def send_a_firebase_msg(self, doc, context):
	# 	recipients, cc, bcc = self.get_list_of_recipients(doc, context)
	# 	recipients = [recipient for recipient in (
	# 		recipients + cc + bcc) if recipient]
	# 	sender = None

	# 	message = frappe.render_template(self.message, context)
	# 	send_firebase_message(cc, data=json.loads(message))

	def get_list_of_receivers(self,context):
		receivers=[]
		cc=[]
		for receiver in self.receivers:
			if receiver.role:
				emails = get_emails_from_role(receiver.role)
				for email in emails:
					receivers = receivers + email.split("\n")
			if receiver.receivers and "{" in receiver.receivers:
				receiver.receivers = frappe.render_template(receiver.receivers, context)

			if receiver.receivers:
				receiver.receivers = receiver.receivers.replace(",", "\n")
				cc = cc + receiver.receivers.split("\n")
		if not receivers and not cc:
			return None, None
		return list(set(receivers)), list(set(cc))


	def get_list_of_recipients(self, doc, context):
		recipients = []
		cc = []
		bcc = []
		for recipient in self.recipients:
			if recipient.condition:
				if not frappe.safe_eval(recipient.condition, None, context):
					continue
			if recipient.email_by_document_field:
				email_ids_value = doc.get(recipient.email_by_document_field)
				if validate_email_add(email_ids_value):
					email_ids = email_ids_value.replace(",", "\n")
					recipients = recipients + email_ids.split("\n")

			if recipient.cc and "{" in recipient.cc:
				recipient.cc = frappe.render_template(recipient.cc, context)

			if recipient.cc:
				recipient.cc = recipient.cc.replace(",", "\n")
				cc = cc + recipient.cc.split("\n")

			if recipient.bcc and "{" in recipient.bcc:
				recipient.bcc = frappe.render_template(recipient.bcc, context)

			if recipient.bcc:
				recipient.bcc = recipient.bcc.replace(",", "\n")
				bcc = bcc + recipient.bcc.split("\n")

			# For sending emails to specified role
			if recipient.email_by_role:
				emails = get_emails_from_role(recipient.email_by_role)

				for email in emails:
					recipients = recipients + email.split("\n")

		if not recipients and not cc and not bcc:
			return None, None, None
		return list(set(recipients)), list(set(cc)), list(set(bcc))

	def get_attachment(self, doc):
		""" check print settings are attach the pdf """
		if not self.attach_print:
			return None

		print_settings = frappe.get_doc("Print Settings", "Print Settings")
		if (doc.docstatus == 0 and not print_settings.allow_print_for_draft) or \
			(doc.docstatus == 2 and not print_settings.allow_print_for_cancelled):

			# ignoring attachment as draft and cancelled documents are not allowed to print
			status = "Draft" if doc.docstatus == 0 else "Cancelled"
			frappe.throw(_("""Not allowed to attach {0} document,
				please enable Allow Print For {0} in Print Settings""".format(status)),
				title=_("Error in Broadcast"))
		else:
			return [{
				"print_format_attachment": 1,
				"doctype": doc.doctype,
				"name": doc.name,
				"print_format": self.print_format,
				"print_letterhead": print_settings.with_letterhead,
				"lang": local.db.get_value('Print Format', self.print_format, 'default_print_language')
					if self.print_format else 'en'
			}]

	def get_template(self):
		module = get_doc_module(self.module, self.doctype, self.name)

		def load_template(extn):
			template = ''
			template_path = os.path.join(os.path.dirname(module.__file__),
				frappe.scrub(self.name) + extn)
			if os.path.exists(template_path):
				with open(template_path, 'r') as f:
					template = f.read()
			return template

		return load_template('.html') or load_template('.md')

	def load_standard_properties(self, context):
		'''load templates and run get_context'''
		module = get_doc_module(self.module, self.doctype, self.name)
		if module:
			if hasattr(module, 'get_context'):
				out = module.get_context(context)
				if out: context.update(out)

		self.message = self.get_template()

		# if not is_html(self.message):
		# 	self.message = frappe.utils.md_to_html(self.message)

@frappe.whitelist()
def get_channel_list():
	return list(frappe.get_hooks('broadcast_channels'))

@frappe.whitelist()
def get_documents_for_today(notification):
	notification = frappe.get_doc('Broadcast', notification)
	notification.check_permission('read')
	return [d.name for d in notification.get_documents_for_today()]

def trigger_daily_alerts():
	trigger_notifications(None, "daily")

def trigger_notifications(doc, method=None):
	if frappe.flags.in_import or frappe.flags.in_patch:
		# don't send notifications while syncing or patching
		return

	if method == "daily":
		for alert in local.db.sql_list(f"""select name from `tabBroadcast`
			where event in ('Days Before', 'Days After') and enabled = 1 and valid_till >= %(today)s""",{
			'today': nowdate()
		}):
			alert = frappe.get_doc("Broadcast", alert)
			for doc in alert.get_documents_for_today():
				broadcast_evaluate_alert(doc, alert, alert.event)
				local.db.commit()

def broadcast_evaluate_alert(doc, alert, event):
	from jinja2 import TemplateError
	try:
		if isinstance(alert, string_types):
			alert = frappe.get_doc("Broadcast", alert)

		context = get_context(doc)

		if alert.condition:
			if not frappe.safe_eval(alert.condition, None, context):
				return

		if event=="Value Change" and not doc.is_new():
			try:
				prev_val = doc.get_doc_before_save().get(alert.value_changed)
			except pymysql.InternalError as e:
				if e.args[0]== ER.BAD_FIELD_ERROR:
					alert.db_set('enabled', 0)
					frappe.log_error('Broadcast {0} has been disabled due to missing field'.format(alert.name))
					return
				raise

			if (doc.get(alert.value_changed) == prev_val):
				return # value not changed

		if event != "Value Change" and not doc.is_new():
			# reload the doc for the latest values & comments,
			# except for validate type event.
			doc = frappe.get_doc(doc.doctype, doc.name)
		alert.send(doc)
	except TemplateError:
		frappe.throw(_("Error while evaluating Broadcast {0}. Please fix your template.").format(alert))
	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(), title=str(e))
		frappe.throw(_("Error in Broadcast"))

def get_context(doc):
	return {"doc": doc, "nowdate": nowdate, "frappe.utils": frappe.utils}

def execute_broadcast(doc,method):
	broadcast_alerts=None
	current_date = frappe.utils.now_datetime()
	if broadcast_alerts==None:
		broadcast_alerts = frappe.get_all('Broadcast', fields=['name', 'event', 'method'],
		filters=[["valid_till", ">=", current_date], ['enabled','=',1],['document_type','=',doc.doctype]])
		for alert in broadcast_alerts:
			broadcast_evaluate_alert(doc, alert.name, alert.event)


