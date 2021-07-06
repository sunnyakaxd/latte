# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.modules.export_file import export_to_files
from latte.utils.logger import get_logger


class SchedulerEvent(Document):

	def validate(self):
		if not self.disabled:
			if self.is_standard:
				if not self.module:
					frappe.throw("Module is mandatory for standard documents")

			if self.event_type == 'Doctype':
				if not self.ref_doctype:
					frappe.throw("Doctype is mandatory for 'Doctype' events.")

			if self.event_type == 'Custom':
				if not self.event_group:
					frappe.throw("Event Group is mandatory for 'Custom' events.")

			if not self.event:
				frappe.throw(f"Event is mandatory for '{self.event_type}' events.")

			if not self.handler:
				frappe.throw(f"Handler is mandatory for '{self.event_type}' events.")

	def on_update(self):
		self.invalidate_hooks()

	def on_trash(self):
		self.invalidate_hooks()

	def invalidate_hooks(self):
		from latte.utils.caching import invalidate
		invalidate('hooks')


def get_hooks():
	db_scheduler_events = frappe.get_all("Scheduler Event", filters = {
		"disabled": 0
	}, fields=[
		'event_type',
		'event',
		'handler',
		'ref_doctype',
		'ref_docname',
	])

	cron_map = {}

	for scheduled_event in db_scheduler_events:
		try:
			cron_map[scheduled_event['event']].append(scheduled_event['handler'])
		except KeyError:
			cron_map[scheduled_event['event']] = [scheduled_event['handler']]

	return {
		'scheduler_events': {
			'cron': cron_map,
		}
	}
