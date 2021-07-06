import inspect
import frappe
import os

from frappe import _
from frappe.modules import scrub, get_module_path
from frappe.utils import cint, get_html_format, cstr, get_url_to_form
from frappe.model.utils import render_include
from frappe.translate import send_translations
import frappe.desk.reportview
import frappe.desk.query_report
from six import string_types
from frappe.utils.file_manager import get_file
from frappe.utils import gzip_decompress
from latte.database_utils.connection_pool import DBShieldException, PatchedDatabase
import importlib.util
import pandas as pd
from frappe.desk.query_report import (
	get_report_module_dotted_path,
	get_report_doc,
	add_total_row
)
import latte
from latte.utils.blacklisting import watch_blacklist
from latte.utils.caching import cache_me_if_you_can
from latte.utils.logger import get_logger
from latte.json import loads
from json import dumps
from frappe import local
from frappe.utils.jinja import get_jenv_customization

def get_caching_scope_and_expiry(report, filters=None, *_, **__):
	if isinstance(report, str):
		report = frappe.get_cached_doc('Report', report)

	if report.caching_scope == 'Global':
		return (report.name + '|' + str(filters), report.cache_expiry or 360,)

	return (report.name + '|' + frappe.session.user + '|' + str(filters) + '|' + str(report.modified), report.cache_expiry or 360)

def get_acceptable_lag(report, *_, **__):
	if isinstance(report, str):
		report = frappe.get_cached_doc('Report', report)
	return report.acceptable_data_lag or 120

def get_replica_priority(report, filters=None, *_, **__):
	if isinstance(report, str):
		report = frappe.get_cached_doc('Report', report)

	return frappe.utils.cint(report.replica_priority)

@latte.read_only(
	key=get_acceptable_lag,
	replica_priority=get_replica_priority
)
@cache_me_if_you_can(key=get_caching_scope_and_expiry)
def generate_report_result(report, filters=None, user=None , should_add_total_row=True):
	if not user:
		user = frappe.session.user
	if not filters:
		filters = []
	if isinstance(report, string_types):
		report = frappe.get_cached_doc('Report', report)

	if report.datasource:
		get_jenv_customization("filters")
		local.append_statement_to_query = ''
		datasource = frappe.get_cached_doc("Datasource", report.datasource)
		ds_db = PatchedDatabase(
			host=datasource.host,
			port=datasource.port,
			user=datasource.user,
			password=datasource.password,
			db_name=datasource.database_name,
		)

		try :
			return generate_report_result_wrapped(report, filters, user , should_add_total_row, ds_db=ds_db)
		finally:
			ds_db.close()

	return generate_report_result_wrapped(report, filters, user , should_add_total_row, ds_db=local.db)

@watch_blacklist(
	key=lambda report, filters, *_, **__: f'{report.name}|{str(filters)}',
	get_timeout=lambda report, *_, **__: report.timeout,
	exclude=lambda report, *_, **__: (
		(report.prepared_report and not report.disable_prepared_report)
		or (not report.timeout)
	),
)
def generate_report_result_wrapped(report, filters=None, user=None , should_add_total_row=True, ds_db=None):

	status = None

	if filters and isinstance(filters, string_types):
		filters = loads(filters)
	columns, result, message, chart, data_to_be_printed = [], [], None, None, None

	local.flags.log_identity = f'{report.doctype}|{report.name}'

	if report.report_type == "Query Report":
		if not report.query:
			status = "error"
			frappe.msgprint(_("Must specify a Query to run"), raise_exception=True)

		if isinstance(filters, dict) and filters.get('__blank_run'):
			frappe.session.user = filters.get('__user')

		query_template = frappe.render_template(report.query, {
			'filters': filters,
		}).replace('\\n', ' ').strip()

		if not query_template.lower().startswith("select") and not query_template.lower().startswith("with"):
			status = "error"
			frappe.msgprint(_("Query must be a SELECT OR WITH"), raise_exception=True)

		if isinstance(filters, dict) and filters.get('__blank_run'):
			frappe.msgprint(
				local.db.mogrify(query_template, filters)\
				.replace('\n', '<br>')\
				.replace('\t', '&#9;')\
				.replace(' ', '&nbsp;')\
			)
			frappe.throw('Blank')

		result = [list(t) for t in ds_db.sql(query_template, filters)]

		columns = [cstr(c[0]) for c in ds_db.get_description()]
	elif report.report_type == "Jupyter Report":
		attached_files = frappe.get_all('File', filters={
				'attached_to_doctype': "Report",
				'attached_to_name': report.name,
				'file_name': ['like', '%.py'],
			},
			fields=['name','file_name','file_url'],
		)

		if not attached_files:
			frappe.throw("File attachment necessary for notebook type report")

		execute_file = attached_files[0]

		if execute_file["file_url"].startswith("/"):
			file_url = execute_file["file_url"][1:]
		else:
			file_url = execute_file["file_url"]

		spec = importlib.util.spec_from_file_location("notebook_report", f"{local.site}/public/{file_url}")
		report_executor = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(report_executor)
		dataframe_output = report_executor.execute(filters)
		columns, result = dataframe_output.columns.tolist(), [value.tolist() for value in dataframe_output.values]
	else:
		module = report.module or local.db.get_value("DocType", report.ref_doctype, "module")
		if report.is_standard == "Yes":
			method_name = get_report_module_dotted_path(module, report.name) + ".execute"
			execute = frappe.get_attr(method_name)
			try:
				accepts_ds_db = execute.__accepts_ds_db
			except AttributeError:
				accepts_ds_db = execute.__accepts_ds_db = 'ds_db' in inspect.getfullargspec(execute).args

			if accepts_ds_db:
				res = execute(frappe._dict(filters), ds_db=ds_db)
			else:
				res = execute(frappe._dict(filters))

			columns, result = res[0], res[1]
			if len(res) > 2:
				message = res[2]
			if len(res) > 3:
				chart = res[3]
			if len(res) > 4:
				data_to_be_printed = res[4]

	if result and report.pivot_index and report.pivot_column and report.pivot_cell:
		df = pd.DataFrame.from_records(result, columns=columns)

		aggfunc = report.aggregate_function
		df = df.pivot_table(index=report.pivot_index, columns=report.pivot_column, values=report.pivot_cell, aggfunc=aggfunc)
		df.fillna(0, inplace=True)
		df[report.pivot_index] = df.index
		columns = df.columns.tolist()
		columns = columns[-1: ] + columns[:-1]

		if report.column_order:
			column_order = report.column_order.split(",")
			column_order.extend([column for column in columns[1:] if column not in column_order])
			columns[1:] = column_order

		df = df.reindex(columns=columns)
		df.fillna(0, inplace=True)
		columns = df.columns.tolist()
		result = df.values.tolist()

	if should_add_total_row and cint(report.add_total_row) and result:
		result = list(result)
		result = add_total_row(result, columns)

	return {
		"result": result,
		"columns": columns,
		"message": message,
		"chart": chart,
		"data_to_be_printed": data_to_be_printed,
		"status": status,
		"execution_time": frappe.cache().hget('report_execution_time', report.name) or 0
	}

@frappe.whitelist()
def get_script(report_name):
	report = get_report_doc(report_name)

	module = report.module or local.db.get_value("DocType", report.ref_doctype, "module")
	module_path = get_module_path(module)
	report_folder = os.path.join(module_path, "report", scrub(report.name))
	script_path = os.path.join(report_folder, scrub(report.name) + ".js")
	print_path = os.path.join(report_folder, scrub(report.name) + ".html")

	script = None
	if os.path.exists(script_path):
		with open(script_path, "r") as f:
			script = f.read()

	html_format = get_html_format(print_path)

	if not script and report.javascript:
		script = report.javascript

	if not script and report.report_type == "Jupyter Report":
		attached_files =frappe.get_all(
			'File',
			filters=[
				['File', 'attached_to_doctype', '=', "Report"],
				['File', 'attached_to_name', '=', report_name]],
			fields=['name','file_name','file_url'])
		filter_config_file = None
		for f in attached_files:
			if f["file_name"].endswith(".js"):
				filter_config_file = f
				break
		if filter_config_file:
			if filter_config_file["file_url"].startswith("/"):
				file_url = filter_config_file["file_url"][1:]
			else:
				file_url = filter_config_file["file_url"]
			with open(local.site + "/public/" + file_url) as fc:
				script = "frappe.query_reports['%s'] = {" % report_name  + fc.read() + "}"

	if not script:
		script = "frappe.query_reports['%s']={}" % report_name

	# load translations
	if frappe.lang != "en":
		send_translations(frappe.get_lang_dict("report", report_name))

	return {
		"script": render_include(script),
		"html_format": html_format,
		"execution_time": frappe.cache().hget('report_execution_time', report_name) or 0
	}

def get_prepared_report_result(report, filters, dn="", user=None):
	latest_report_data = {}
	doc = None
	if dn:
		# Get specified dn
		doc = frappe.get_doc("Prepared Report", dn)
	else:
		# Only look for completed prepared reports with given filters.
		doc_list = frappe.get_all("Prepared Report", filters={
			"status": "Completed",
			"filters": dumps(filters, sort_keys=True),
			"owner": user,
		})
		if doc_list:
			# Get latest
			doc = frappe.get_doc("Prepared Report", doc_list[0])

	if doc:
		try:
			# Prepared Report data is stored in a GZip compressed JSON file
			attached_file_name = local.db.get_value("File", {
				"attached_to_doctype": doc.doctype,
				"attached_to_name": doc.name,
			}, "name")
			compressed_content = get_file(attached_file_name)[1]
			uncompressed_content = gzip_decompress(compressed_content)
			data = loads(uncompressed_content)
			if data:
				latest_report_data = {
					"columns": loads(doc.columns) if doc.columns else data[0],
					"result": data
				}
		except Exception:
			get_logger(index_name='unexpected_error').error(frappe.get_traceback())
			frappe.utils.background_jobs.enqueue(
				frappe.delete_doc,
				doctype="Prepared Report",
				name=doc.name,
			)
			doc = None

	latest_report_data.update({
		"prepared_report": True,
		"doc": doc
	})

	return latest_report_data

@frappe.whitelist()
def background_enqueue_run(report_name, filters=None, user=None):
	"""run reports in background"""
	if not user:
		user = frappe.session.user
	report = get_report_doc(report_name)

	track_instance = \
		frappe.get_doc({
			"doctype": "Prepared Report",
			"report_name": report_name,
			"filters": dumps(loads(filters), sort_keys=True),
			"ref_report_doctype": report_name,
			"report_type": report.report_type,
			"query": report.query,
			"module": report.module,
		})
	track_instance.insert(ignore_permissions=True)
	local.db.commit()
	return {
		"name": track_instance.name,
		"redirect_url": get_url_to_form("Prepared Report", track_instance.name)
	}

frappe.desk.query_report.background_enqueue_run = background_enqueue_run
frappe.desk.query_report.get_prepared_report_result = get_prepared_report_result
frappe.desk.query_report.get_script = get_script
frappe.desk.query_report.generate_report_result = generate_report_result
