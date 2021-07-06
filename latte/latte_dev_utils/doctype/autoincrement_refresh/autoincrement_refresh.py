# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from latte.utils.background.job import background

class AutoincrementRefresh(Document):
	def before_save(self):
		self.sequence_name = frappe.db.escape('__auto_increment_fixer__' + frappe.scrub(self.ref_doctype))
		self.status = 'Pending'
		if not self.current_sequence:
			self.current_sequence = 1
		self.running = 0
		self.next_not_cached_value = 1

	def before_submit(self):
		self.before_save()

	def on_submit(self):
		frappe.db.sql(f'''
			create or replace sequence {self.sequence_name}
			cache {self.block_size}
			start with {self.current_sequence}
		''')
		# refresh_for(self.name)

	def on_cancel(self):
		frappe.db.sql(f'drop sequence if exists {self.sequence_name}')

@frappe.whitelist()
def reset(name):
	doc = frappe.get_doc('Autoincrement Refresh', name)
	doc.on_cancel()
	doc.docstatus = 0
	doc.status = ''
	doc.current_sequence = doc.cycle_count = doc.running = 0
	doc.before_save()
	doc.db_update()

def get_hooks():
	if not frappe.db.get_value('Autoincrement Refresh', filters={
		'status': 'Pending',
		'docstatus': 1,
	}):
		return {}
	return {
		'scheduler_events': {
			'cron': {
				'* * * * *': 'latte.latte_dev_utils.doctype.autoincrement_refresh.autoincrement_refresh.refresh_for_all',
			}
		}
	}

def refresh_for_all():
	for row in frappe.get_all('Autoincrement Refresh', filters={
		'status': 'Pending',
		'docstatus': 1,
		'running': 0,
	}):
		refresh_for(row.name)

@background()
def refresh_for(name):
	runner = lock_and_get_runner(name)
	if not runner:
		return

	if runner.status != 'Pending' or runner.docstatus != 1 or runner.running:
		return

	cycle_count = runner.cycle_count
	current_sequence = runner.current_sequence
	frappe.db.set_value('Autoincrement Refresh', name, 'running', 1)
	frappe.db.commit()

	runner = lock_and_get_runner(name)
	doctype = frappe.db.escape(runner.ref_doctype)

	if cycle_count != runner.cycle_count:
		frappe.db.set_value('Autoincrement Refresh', name, 'status', f'Failed/Mismatch Cycle {cycle_count}/{runner.cycle_count}')
		return

	elif current_sequence != runner.current_sequence:
		frappe.db.set_value('Autoincrement Refresh', name, 'status', f'Failed/Mismatch sequence {current_sequence}/{runner.current_sequence}')
		return

	max_num = frappe.db.sql(f'select max(name) from `tab{doctype}`')[0][0]
	if current_sequence >= max_num:
		return lock_table_and_complete(runner, doctype, max_num)

	next_not_cached_value = frappe.db.sql(f'''
		select next_not_cached_value from {runner.sequence_name}
	''')[0][0]

	if current_sequence != next_not_cached_value:
		frappe.db.set_value('Autoincrement Refresh', name, 'status', f'Failed/Mismatch next_value {current_sequence}/{next_not_cached_value}')
		return

	frappe.db.execute(f'''
		update
			`tab{doctype}`
		set
			name = (select next value for {runner.sequence_name})
		where
			name >= %(current_sequence)s
		order by
			name
		limit
			%(block_size)s
	''', runner)
	frappe.db.set_value('Autoincrement Refresh', name, 'running', 0)
	frappe.db.set_value('Autoincrement Refresh', name, 'cycle_count', cycle_count + 1)
	frappe.db.set_value('Autoincrement Refresh', name, 'current_sequence', current_sequence + runner.block_size)
	next_not_cached_value = frappe.db.sql(f'''
		select next_not_cached_value from {runner.sequence_name}
	''')[0][0]
	frappe.db.set_value('Autoincrement Refresh', name, 'next_not_cached_value', next_not_cached_value)

def lock_table_and_complete(runner, doctype, max_num):
	frappe.db.sql(f'drop sequence if exists {runner.sequence_name}')
	frappe.db.sql(f'create or replace sequence {runner.sequence_name}_commit start {max_num + 1} cache 0')
	frappe.db.sql(f'''
		lock tables
			`tab{doctype}` write,
			{runner.sequence_name}_commit write,
			`tabAutoincrement Refresh` write
		''')
	frappe.db.sql(f'''
		update
			`tab{doctype}`
		set
			name = (select next value for {runner.sequence_name}_commit)
		where
			name > {max_num}
		order by
			name
	''')
	frappe.db.set_value('Autoincrement Refresh', runner.name, 'status', 'Completed')
	new_max_num = frappe.db.sql(f'select max(name) from `tab{doctype}`')[0][0]
	frappe.db.sql(f'alter table `tab{doctype}` auto_increment = {new_max_num}')
	frappe.db.sql(f'drop sequence {runner.sequence_name}_commit')

def lock_and_get_runner(name):
	runner = frappe.db.sql('''
		select
			name,
			ref_doctype,
			status,
			docstatus,
			current_sequence,
			block_size,
			running,
			cycle_count,
			sequence_name
		from
			`tabAutoincrement Refresh`
		where
			name = %(name)s
		for update
	''', {
		'name': name,
	}, as_dict=True)

	runner = runner and runner[0]
	return runner