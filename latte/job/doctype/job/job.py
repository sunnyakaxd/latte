# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from latte.utils.background.job import background
from latte.utils.background.job import SUCCESS
from latte.utils.background.job import FAILURE
from latte.job.background_jobs.job_fixer import Helper
from latte.job.enums.job_status import Job_status


class Job(Document):

	@background(identity= lambda self: self.name)
	def execute(self):
		self.lock_for_update()
		doc = frappe.get_doc(self.ref_doctype, self.ref_docname)
		getattr(doc, self.method)(doc, __job__=False)

	def update_status(self,status):
		super().update_status(status)
		if status in { Job_status.SUCCESS.value, Job_status.FAILURE.value}:
			self.db_set("ended_on", frappe.utils.now_datetime())
		if status == Job_status.PROCESSING.value:
			self.increment_retries()
		frappe.db.commit()

	def increment_retries(self):
		self.db_set("retry_count", self.retry_count+1)

	def add_job_run_as_child(self, job_run_doc):
		job_run_doc.parent = self.name
		job_run_doc.parenttype = self.doctype
		job_run_doc.parentfield = "job_run"
		job_run_doc.db_update()

	def get_job_status_from_job_run_status(self, job_run_status):
		if job_run_status == SUCCESS:
			return Job_status.SUCCESS.value
		else:
			if self.retry_count >= self.max_retries:
				return Job_status.FAILURE.value
			else:
				return Job_status.PENDING.value

	def lock_for_update(self):
		sql_query_to_lock = "SELECT name FROM `tabJob` where name=%(name)s FOR UPDATE NOWAIT"
		frappe.db.sql(sql_query_to_lock, {
			'name': self.name,
		})

	@staticmethod
	def update_job_status(job_run_doc):
		job_run_status = job_run_doc.db_get("status")
		if job_run_status in [SUCCESS, FAILURE] and job_run_doc.ident:
			if frappe.db.exists("Job", job_run_doc.ident):
				job = frappe.get_doc("Job", job_run_doc.ident)
				job.update_status(job.get_job_status_from_job_run_status(job_run_status))
				job.add_job_run_as_child(job_run_doc)

@frappe.whitelist()
def retry(name):
	frappe.only_for('System Manager')
	frappe.get_doc('Job', name).execute()

def update_job_on_job_run_status_change(doc, event):
	Job.update_job_status(doc)

def on_doctype_update():
	frappe.db.add_index("Job", ["ref_doctype", "ref_docname"])
