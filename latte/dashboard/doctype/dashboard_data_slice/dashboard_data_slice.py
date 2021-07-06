# -*- coding: utf-8 -*-
# Copyright (c) 2019, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import os
import latte
from six import string_types
import json
from frappe.utils import cstr
from frappe.modules.utils import get_module_path
from frappe.model.document import Document
from frappe.desk.query_report import get_report_doc, get_prepared_report_result
from latte.monkey_patches.frappe.desk.query_report import generate_report_result
from frappe.desk.reportview import compress, execute
from latte.dashboard.doctype.dashboard_configuration.dashboard_configuration import make_json
from frappe.modules.export_file import export_to_files

class DashboardDataSlice(Document):
	def before_save(self):
		self.make_standard()

	def validate(self):
		if frappe.local.conf.developer_mode:
			"""Validate only in dev mode"""
			self.standard_everything()
			self.validating_report_in_multiple_data_sources()

	def standard_everything(self):
		'''
		Makes sure Reports linked are all standard in developer mode
		'''
		if frappe.get_conf().developer_mode and self.data_source == "Report":
			is_report_standard = frappe.db.get_value('Report', self.report, ['is_standard'])
			if is_report_standard != "Yes":
				frappe.throw(f"Linked report {frappe.bold(self.report)} is not standard. Cannot Save.")

	def validating_report_in_multiple_data_sources(self):
		'''
		Reports linked through multiple data sources should also be standard.
		'''
		if self.multiple_ds:
			sources = [ row.report for row in self.dashboard_datasource if row.data_source == "Report"]
			if sources:
				error = ''
				for report in sources:
					standard = frappe.db.get_value('Report', report, ['is_standard'])
					if standard != "Yes":
						error += f'Report {frappe.bold(report)} is not standard. Cannot Save. \n'
				if len(error):
					frappe.throw(error)

	def on_update(self):
		if self.module and frappe.local.conf.developer_mode and not frappe.flags.in_migrate:
			export_to_files(record_list=[[self.doctype, self.name]],
				record_module=self.module, create_init=True)
		# If Developer, continue to make/update JSON for this Data slice
		# if frappe.get_conf().developer_mode:
		# 	self.make_data_slice_json()

	def make_standard(self):
		if frappe.get_conf().developer_mode:
			self.is_standard = "Yes"

	def make_data_slice_json(self):
		self.is_standard = True
		docstring = self.as_dict()
		module = self.module
		folder_path = os.path.join(get_module_path(module), f'{frappe.scrub(self.doctype)}')
		make_json(docstring, self.name, module, folder_path)


	def execute(self, data_source_name=None, filters=None):
		# TODO - Fix would be needed to not trigger multiple same reports for the one rendered on the Dashboard.
		# Also, Filters need to be streamlined. Processing happens on the front end.
		qry_filters = frappe._dict()
		frappe.local.flags.log_identity = f'{self.doctype}|{self.name}'
		if filters:
			if isinstance(filters, string_types):
				filters = json.loads(filters)
			for filter_row in self.filter:
				try:
					qry_filters.update({
						filter_row.mapped_filter_field: filters[filter_row.filter_data_slice]
					})
				except KeyError:
					pass
		try:
			if self.filter_parser:
				exec(self.filter_parser, {
					'frappe': frappe,
					'filters': qry_filters,
				})

			data_source, method, query, report = None, None, None, None
			if data_source_name or self.multiple_ds:
				ds = list(filter(lambda x: x.data_source_name == data_source_name, self.dashboard_datasource))
				if len(ds) > 0:
					data_source = ds[0].data_source
					method = ds[0].method
					query = ds[0].query
					report = ds[0].report


			if (data_source or self.data_source) == 'Method':
				return data_mapper(
					"method",
					frappe.call((method or self.method), qry_filters),
					"Success"
				)

			elif (data_source or self.data_source)  == 'Report':
				report = get_report_doc(report or self.report)
				if report.report_type == 'Report Builder':
					report_json = json.loads(report.json)
					vargs = frappe._dict(
						doctype=report.ref_doctype,
						filters=qry_filters or []
					)

					_columns = report_json.get('fields') or report_json.get('columns')

					if _columns:
						vargs['fields'] = [f'`tab{rf[1]}`.`{rf[0]}`' for rf in _columns]

					return data_mapper(
						"report_builder",
						compress(execute(**vargs), args=vargs),
						"Success"
					)

				if report.prepared_report and not report.disable_prepared_report:
					filters=qry_filters
					if filters:
						if isinstance(filters, string_types):
							filters = json.loads(filters)

						dn = filters.get("prepared_report_name")
						filters.pop("prepared_report_name", None)
					else:
						dn = ""

					return data_mapper(
						"report",
						get_prepared_report_result(report, filters=qry_filters, dn=dn, user=frappe.session.user),
						"Success"
					)

				return data_mapper(
					"report",
					generate_report_result(report=report, filters=qry_filters or []),
					"Success"
				)
			elif (data_source or self.data_source)  == "Query":
				return data_mapper(
					"query",
					generate_query_result(query or self.query, filters=qry_filters or []),
					"Success"
				)
		except frappe.exceptions.PermissionError as p:
			frappe.errprint(frappe.get_traceback())
			return (None, 'Permission Error')
		except Exception as e:
			frappe.errprint(frappe.get_traceback())
			return (None, 'Exception')
		return None, None


# TODO - This function needs to be moved to a place other than this
# Fetches meta for Reports
@frappe.whitelist()
def generate_report_meta(report_name):
	report = get_report_doc(report_name)
	report_res = generate_report_result(report=report)
	return report_res.get('columns')

@latte.read_only(replica_priority=0)
def generate_query_result(sql, filters=None, user=None):
	status = None
	if not user:
		user = frappe.session.user
	if not filters:
		filters = []

	if filters and isinstance(filters, string_types):
		filters = json.loads(filters)
	columns, result, message = [], [], None
	if sql:
		query_template = frappe.render_template(sql, {
			'filters': filters,
		}).replace('\\n', ' ').strip()
		if not query_template.lower().startswith("select") and not query_template.lower().startswith("with"):
			status = "error"
			frappe.msgprint(_("Query must be a SELECT OR WITH"), raise_exception=True)
		result = [list(t) for t in frappe.db.sql(query_template, filters)]
		columns = [cstr(c[0]) for c in frappe.db.get_description()]

	return {
		"result": result,
		"columns": columns,
		"message": message,
		"status": status
	}

def data_mapper(data_source, data, status):
	mapper = {
		"report_builder": {
			"columns": "keys",
			"result": "values"
		},
		"method": {
			"columns": "columns",
			"result": "result"
		},
		"report": {
			"columns": "columns",
			"result": "result"
		},
		"query": {
			"columns": "columns",
			"result": "result"
		}
	}

	return (
		{
			"columns": data[mapper[data_source]["columns"]],
			"result": data[mapper[data_source]["result"]],
		},
		status
	)
