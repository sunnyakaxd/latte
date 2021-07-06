# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
import pandas as pd
from frappe.model.document import Document
from frappe.core.doctype.sms_settings.sms_settings import validate_receiver_nos
from frappe.core.doctype.sms_settings.sms_settings import send_sms
from latte.file_storage.doctype.attachment.attachment import Attachment
from base64 import b64encode
from latte.json import dumps

class BulkNotification(Document):

	def before_submit(self):
		if not self.recipient_column:
			frappe.throw("Please Enter Recipient Column Name.")
		if self.channel == "Email" and not self.subject:
			frappe.throw("Please Enter Subject for the Email.")
		if self.attach_media and not self.attachment:
			frappe.throw("Please upload a media attachment.")	
		self.initiate_alerts()
		self.map_status()

	def on_submit(self):
		data = self.show_data()
		frappe.msgprint(data)

	def get_data(self):
		attachment_doc = Attachment.find_by_file_url(self.upload_data)
		df = pd.read_excel(attachment_doc.get_data_stream())
		return df

	def initiate_alerts(self):
		df = self.get_data()
		i = 0
		self.total = len(df)
		self.failed_queue = []
		while (i< len(df)):
			recipients = []
			recipients.append(str(df.iloc[i][self.recipient_column]))
			message = frappe.render_template(self.message,{'doc':df.iloc[i]})
			subject = frappe.render_template(self.subject,{'doc':df.iloc[i]})
			self.row = i
			self.send_alerts(recipients,message,subject)
			i = i + 1

	def show_data(self):
		data_to_show = ""
		header = '''
		<b>SMS Alerts Intitated.</b>
		<table class="table table-bordered table-striped">
		<tr>
			<th>Total Notifications</th>
			<th>Successfull</th>
			<th>Failed</th>
		</tr>
		'''
		data_to_show = data_to_show + '''
				<tr>
					<td>{total_alerts}</td>
					<td bgcolor="#00FF00">{successful_alerts}</td>
					<td bgcolor="#FF0000">{failed_alerts}</td>
				</tr>
			'''.format(
				total_alerts= self.total,
				successful_alerts= self.total - len(self.failed_queue),
				failed_alerts=len(self.failed_queue)
			)

		data_to_show = header + data_to_show + '''
			</table>
		'''
		return data_to_show

	def map_status(self):
		self.initiation_details = self.map_initiation_log()
		if len(self.failed_queue) == 0:
			self.initiation_status = "Successful"
		elif self.total == len(self.failed_queue):
			self.initiation_status = "Failed"
		else:
			self.initiation_status = "Partially Successful"

	def map_initiation_log(self):
		failed_data = ""
		header = '''
		<b>Failed Alerts</b>
		<table class="table table-bordered table-striped">
		<tr>
			<th>Row Number</th>
			<th>Recipient</th>
		</tr>
		'''
		for rec in self.failed_queue:
			failed_data = failed_data + '''
					<tr>
						<td>{row}</td>
						<td>{recipient}</td>
					</tr>
				'''.format(
					row= list(rec.keys())[0],
					recipient= list(rec.values())[0],
				)

		failed_data = header + failed_data + '''
			</table>
		'''
		return failed_data

	def validate_email_id(self,email_id):
		if "@" and "." in email_id:
			return email_id
		else:
			self.failed_queue.append({(self.row + 1):email_id})

	def validate_mobile_number(self,mobile_no):
		mobile_no = validate_receiver_nos(mobile_no)[0]
		if "." in mobile_no:
			mobile_no = mobile_no.split(".")[0]
		if mobile_no.startswith("+91"):
			mobile_no = mobile_no[3:]
		if mobile_no.startswith("91"):
			mobile_no = mobile_no[2:]
		if mobile_no.startswith("+091"):
			mobile_no = mobile_no[4:]
		if len(mobile_no) == 10 and mobile_no.isdigit():
			return [mobile_no]
		else:
			self.failed_queue.append({(self.row + 1):mobile_no})

	def send_alerts(self,recipients,message,subject):
		if self.channel == "Email":
			reciepient = self.validate_email_id(recipients[0])
			if reciepient:
				send_email(recipients,message,subject)
		elif self.channel == "SMS":
			reciepient = self.validate_mobile_number(recipients)
			if reciepient:
				send_a_sms(reciepient,message)
		elif self.channel == "WhatsApp":
			reciepient = self.validate_mobile_number(recipients)
			if reciepient:
				if self.attachment:
					media_doc = Attachment.find_by_file_url(self.upload_data)
					filedata = b64encode(media_doc.get_data()).decode('utf-8')
					template_name = self.media_template
					filename = "Attachment"
					send_whatsapp_wrapped(
						recipients=reciepient,
						message=message,
						filename=filename,
						filedata=filedata,
						template_name=template_name
					)					
				else:	
					send_whatsapp_wrapped(reciepient,message)

def send_a_sms(recipients,message):
	frappe.utils.background_jobs.enqueue(
		send_sms,
		queue='short',
		timeout=300,
		enqueue_after_commit=True,
		receiver_list=recipients,
		msg=message
	)

def send_email(recipients,message,subject):
	frappe.utils.background_jobs.enqueue(
		frappe.sendmail,
		queue='short',
		timeout=300,
		enqueue_after_commit=True,
		recipients=recipients,
		message=message,
		subject=subject
	)

def send_whatsapp_wrapped(recipients,message,filedata=None,filename=None,template_name=None):
	frappe.utils.background_jobs.enqueue(
		send_whatsapp,
		queue='short',
		timeout=300,
		enqueue_after_commit=True,
		recipient=recipients[0],
		message=message,
		filename=filename,
		filedata=filedata,
		template_name=template_name
	)

def send_whatsapp(recipient,message,filedata=None,filename=None,template_name=None):
	if filedata:
		params_header = "Default"
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
				"params": message,
				"customer_number": f"+91{recipient}"
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

	url = "https://synapse.elasticrun.in/api/method/synapse.execute_api"
	result = requests.post(url, data = dumps(json_message))
	return result
