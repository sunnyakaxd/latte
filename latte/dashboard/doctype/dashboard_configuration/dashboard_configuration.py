# -*- coding: utf-8 -*-
# Copyright (c) 2019, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import os
import json
from frappe.model.document import Document
from frappe.modules.utils import get_module_path
from frappe.modules.export_file import export_to_files

class DashboardConfiguration(Document):
	def add_roles(self):
		"""
		Ensures that linked report to this dashboard is not missing any permissions that exist in dashboard.
		"""
		data_slices = [ row.dashboard_data_slice for row in self.dashboard_data_slices ]
		dashboard_role = set(row.role for row in self.role_permission)
		for data_slice in data_slices:
			try:
				ds_doc = frappe.get_doc('Dashboard Data Slice', data_slice)
			except frappe.DoesNotExistError:
				continue

			if ds_doc.data_source == "Report" and frappe.db.get_value('Report', ds_doc.report):
				report_roles = frappe.db.sql_list('''select distinct role from `tabHas Role` where parent = %(report)s ''', {
					'report': ds_doc.report,
				})
				report_roles = set(report_roles)
				roles_to_be_added = list(dashboard_role.difference(report_roles))
				if roles_to_be_added:
					# add missing roles in report
					report_doc = frappe.get_doc('Report', ds_doc.report)
					for role in roles_to_be_added:
						report_doc.append('roles', {
							'role': role
						})

	def standard_everything(self):
		"""
		Validation to check if all slices/reports/themes that are linked are standard
		"""
		# Check if theme is standard
		if self.dashboard_theme and frappe.db.get_value('Dashboard Theme', self.dashboard_theme, ['is_standard']) != "Yes":
			frappe.throw('Linked Theme is not standard. Make it standard and then save.')

		# Check for linked slices and reports
		slices = [ row.dashboard_data_slice for row in self.dashboard_data_slices ]
		error = ''
		for slice in slices:
			ds_doc = frappe.get_doc('Dashboard Data Slice', slice)
			if ds_doc.is_standard != "Yes":
				frappe.throw(f'{ds_doc.data_slice_name} is not standard. Please make it standard and then save.')
			if ds_doc and ds_doc.get('data_source') and ds_doc.data_source == "Report":
				if frappe.db.get_value('Report', ds_doc.report, ['is_standard']) != "Yes":
					error += f'Report {ds_doc.report} is not standard. Make it standard and then save.'
		if len(error):
			frappe.throw(error)

	def make_dashboard_json(self):
		"""
		Creates JSON
		"""
		self.is_standard = True
		docstring = self.as_dict()
		module = self.module
		folder_path = os.path.join(get_module_path(module), f'{frappe.scrub(self.doctype)}')
		# folder_path.replace('apps/latte/latte/dashboard', 'apps/withrun_erpnext/withrun_erpnext/withrun_erpnext')
		make_json(docstring, self.name, module, folder_path)

	def validate(self):
		if frappe.local.conf.developer_mode:
			"""Validate only in dev mode"""
			self.standard_everything()

	def before_save(self):
		self.add_roles()
		if frappe.local.conf.developer_mode:
			self.is_standard == "Yes"

	def on_update(self):
		if self.is_standard == "Yes" and self.module and frappe.local.conf.developer_mode and not frappe.flags.in_migrate:
			export_to_files(record_list=[[self.doctype, self.name]],
				record_module=self.module, create_init=True)


def make_json(docstring, docname, module, folder_path):
	'''
	Saves a JSON file for a given docname at given path
	'''
	if not os.path.exists(folder_path):
		os.makedirs(folder_path)

	path = os.path.join(folder_path, frappe.scrub(docname)+ '.json')
	with open(path, 'w') as f:
		f.write(json.dumps(docstring, indent=4))
	frappe.msgprint(f'JSON Made for {docname}. Can be found at {folder_path}')


# TODO - Legacy Code
@frappe.whitelist()
def is_project_created(proj_temp):
	from erpnow.project.utils.project import get_context

	if isinstance(proj_temp, str):
		proj_temp = frappe.get_doc("Project Template", proj_temp)

	project_context = get_context(proj_temp, {})

	if not project_context.get('name') :
		frappe.throw("Need Name in the Project Template")

	project = frappe.db.sql("""
		select
			name
			,status
		from
			tabProject
		where
			DATE(expected_start_date) >= CURDATE()
			and DATE(expected_end_date) <= CURDATE()
			and name = %(name)s
	""",{
		'name':project_context['name']
		},
	 as_dict=1)

	if project and project[0]["status"] in ("Completed","Force Closed"):
		return -1

	if project:
		return 1

	return 0

@frappe.whitelist()
def create_project(proj_temp):
	from erpnow.project.utils.project import create_project_from_template

	project_name = create_project_from_template(proj_temp)

	return project_name

@frappe.whitelist()
def get_task_progress(proj_temp):
	from erpnow.project.utils.project import create_project_from_template, get_project_tasks

	project_name = create_project_from_template(proj_temp)

	project_doc = frappe.get_doc("Project", project_name)

	task_list = get_project_tasks(project_doc.name)

	return {
		"task_list":task_list
	}

@frappe.whitelist()
def close_project(proj_temp):
	from erpnow.project.utils.project import create_project_from_template, get_project_tasks

	project_name = create_project_from_template(proj_temp)

	project_doc = frappe.get_doc("Project", project_name)

	project_doc.status = 'Completed'
	project_doc.save(ignore_permissions=True)

	project_doc = frappe.get_doc("Project", project_name)

	task_list = get_project_tasks(project_doc.name)

	if project_doc.status in ('Completed','Force Closed'):
		return {
			"status":"Closed",
			"task_list":task_list
		}

	return {
			"status":"Open",
			"task_list":task_list
		}
# TODO - Legacy Code