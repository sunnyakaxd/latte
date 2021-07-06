import json
import datetime
from time import perf_counter
import latte
from six import string_types
import frappe
from frappe.desk.reportview import get_form_params, compress, execute
from frappe.desk.query_report import (
	run,
	get_prepared_report_result,
	get_report_doc,
	get_columns_dict
)
from latte.database_utils.connection_pool import DBShieldException
from latte.monkey_patches.frappe.desk.query_report import generate_report_result
from latte.utils.logger import get_logger
from latte.utils.blacklisting import watch_blacklist
from latte.utils.caching import cache_me_if_you_can
from frappe import local

@cache_me_if_you_can(expiry=36000)
def table_big_enough(doctype):
	return frappe.db.sql('''SELECT IFNULL(table_rows,0) as row
					 FROM information_schema.tables
					 WHERE table_name = %(doctype)s
					 ''', {
		'doctype': f'tab{doctype}',
	}, as_dict=1)[0]['row'] > (local.conf.listview_table_tolerance or 50000)

@frappe.whitelist()
@latte.read_only()
@watch_blacklist(
	key=lambda *_, **kw: f"{kw.get('doctype')}|{kw.get('filters')}",
	get_timeout=lambda *_, **__: (local.conf.listview_timeout or 120),
)
def patched_get(*args, **kwargs):
	doctype = kwargs.get('doctype')
	filters = kwargs.get('filters')
	local.flags.log_identity = f'listview|{doctype}'
	if isinstance(filters, string_types):
		filters = json.loads(filters)

	if (doctype not in (local.conf.ignore_dt_filters or ['User'])) \
		and table_big_enough(doctype) and not validate_like(filters):
		return

	local.form_dict.filters = filters
	if filters:
		try:
			local.flags.sheild = local.conf.enable_shield
			response = get()
		except DBShieldException:
			get_index_list(doctype, filters)

	response = get()
	if isinstance(response, dict) and response.get('keys', [''])[0] == 'name' and response.get('values'):
		for value in response.get('values'):
			value[0] = str(value[0])

	return response

def get():
	args = get_form_params()
	args.pop('data', None)
	data = compress(execute(**args), args = args)

	return data

def validate_like(filters):
	acceptable_date_range = local.conf.modified_range_limit or 15
	like_present = False
	modified_present = False
	is_date_range_safe = False

	d1 = d2 = None
	for item in filters:
		if item[-2] == 'like':
			if item[-3] == 'name':
				item[-1] = item[-1].lstrip('%')
				return True

			like_present = True

		if item[-3] == 'modified':
			modified_present = True
			if item[-2].lower() == 'between':
				d1 = datetime.datetime.strptime(item[-1][0], '%Y-%m-%d')
				d2 = datetime.datetime.strptime(item[-1][1], '%Y-%m-%d')
			elif item[-2] in ('>', '>='):
				d1 = datetime.datetime.strptime(item[-1], '%Y-%m-%d')
				d2 = frappe.utils.now_datetime()

	if not like_present:
		return True

	is_date_range_safe = d1 and d2 and (((d2 - d1).days + 1) < (acceptable_date_range))

	if like_present and not (modified_present and is_date_range_safe):
		frappe.msgprint(
			f'Please also set "Last Updated On" upto any {acceptable_date_range} days interval with your filter')
	else:
		return True

@frappe.whitelist()
def patched_run(report_name, filters=None, user=None):
	report = get_report_doc(report_name)
	if not user:
		user = frappe.session.user
	if not frappe.has_permission(report.ref_doctype, "report"):
		frappe.msgprint("Must have report permission to access this report.",
						raise_exception=True)

	result = None

	start = perf_counter()
	if report.prepared_report and not report.disable_prepared_report:
		if filters:
			if isinstance(filters, string_types):
				filters = json.loads(filters)

			dn = filters.get("prepared_report_name")
			filters.pop("prepared_report_name", None)
		else:
			dn = ""
		result = get_prepared_report_result(report, filters, dn, user)
	else:
		result = generate_report_result(report, filters, user)

	result["add_total_row"] = report.add_total_row
	log_info = {
		'filters': filters,
		'report_name': report_name,
		'result_length': len(result.get('result') or []),
		'turnaround_time': perf_counter() - start,
	}
	get_logger(index_name='report-access-log').info(log_info)

	return result


def get_index_list(table_doctype, filters):

	doctype_filter = {}

	for doctype, field, comparator, value in filters:
		doctype_filter.setdefault(doctype, set()).add(field)
	doctype_indices = {
		doctype: get_index_meta(doctype) for doctype in doctype_filter
	}
	doctype_indices[table_doctype] = get_index_meta(table_doctype)
	html = convert_json_to_html(doctype_indices)
	print("HTML", html)
	frappe.msgprint(html)
	frappe.throw('Without index query')


def get_index_meta(doctype):
	import pandas as pd

	table = f'tab{doctype}'

	if not frappe.db._conn:
		frappe.db.connect()

	indexed_columns = pd.read_sql(f'''
		SELECT
			column_name,
			index_name,
			seq_in_index,
			cardinality
		from
			information_schema.statistics
		where
			table_schema = '{frappe.conf.db_name}'
			and table_name = '{table}'
	''', con=frappe.db._conn)

	index_cardinalities = indexed_columns.pivot(
		index='index_name',
		columns='seq_in_index',
		values=['column_name', 'cardinality'],
	)

	primary_cardinality = index_cardinalities.loc['PRIMARY']['cardinality'][1]
	row_scans = primary_cardinality / index_cardinalities.cardinality
	max_index_length = indexed_columns.seq_in_index.max()
	allowed_indices = []

	for index in row_scans.index:
		index_row = ()
		index_cols = index_cardinalities.column_name.loc[index]
		append = False
		for i in range(1, max_index_length + 1):
			scanned_rows = row_scans.loc[index].loc[i]
			if scanned_rows < 10000:
				index_row += (index_cols.loc[i],)
				append = True
				break
			else:
				index_row += (index_cols.loc[i],)

		if append:
			allowed_indices.append(index_row)

	allowed_indices = list(set(allowed_indices))
	index_meta = {
		'allowed_indices': allowed_indices,
		'primary_cardinality': primary_cardinality,
	}
	return index_meta


def validate_index(table_doctype, filters):
	return

	doctype_filter = {}
	for doctype, field, comparator, value in filters:
		if comparator != '=' and comparator == 'like':
			if str(value or '').startswith('%'):
				continue
		else:
			doctype_filter.setdefault(doctype, set()).add(field)
	doctype_indices = {
		doctype: get_index_meta(doctype) for doctype in doctype_filter
	}

	doctype_indices[table_doctype] = get_index_meta(table_doctype)
	for doctype, filter_set in doctype_filter.items():

		for index_row in doctype_indices[doctype]['allowed_indices']:
			print("SET ", set(index_row), filter_set)
			if set(index_row) <= filter_set:
				return
			else:
				if doctype_indices[table_doctype]['primary_cardinality'] < 10000:
					return
		frappe.msgprint(frappe.as_json(doctype_indices))
		frappe.throw('Without index query')


def convert_json_to_html(json_string):
	print("STRING", json_string)
	html_string = '''
	Please use Any One of the <b>Following Combination</b> for filtering out the data <br>
	<table class="table table-bordered table-striped">'''
	for doctype in json_string:
		html_string = html_string + '<tr><th> ' + doctype + '</th></tr>'
		print("doc", json_string[doctype]["allowed_indices"])
		for val in json_string[doctype]["allowed_indices"]:
			comp_html = '<tr><td>'
			for var in val:
				comp_html = comp_html + \
					frappe.get_meta(doctype).get_label(str(var)) + ',  '
			comp_html = comp_html + '</tr></td>'
			html_string = html_string + comp_html
	html_string = html_string + ' </table>'
	return html_string


@frappe.whitelist()
@frappe.read_only()
def export_query():
	"""export from query reports"""
	data = frappe._dict(local.form_dict)

	del data["cmd"]
	if "csrf_token" in data:
		del data["csrf_token"]

	if isinstance(data.get("filters"), string_types):
		filters = json.loads(data["filters"])
	if isinstance(data.get("report_name"), string_types):
		report_name = data["report_name"]
	if isinstance(data.get("file_format_type"), string_types):
		file_format_type = data["file_format_type"]
	if isinstance(data.get("visible_idx"), string_types):
		visible_idx = json.loads(data.get("visible_idx"))
	else:
		visible_idx = None

	if file_format_type == "Excel":
		data = run(report_name, filters)
		data = frappe._dict(data)
		columns = get_columns_dict(data.columns)

		from frappe.utils.xlsxutils import make_xlsx
		xlsx_data = build_xlsx_data(columns, data, visible_idx)
		xlsx_file = make_xlsx(xlsx_data, "Query Report")

		frappe.response['filename'] = report_name + '.xlsx'
		frappe.response['filecontent'] = xlsx_file.getvalue()
		frappe.response['type'] = 'binary'


def build_xlsx_data(columns, data, visible_idx):
	result = [[]]

	# add column headings
	for idx in range(len(data.columns)):
		result[0].append(columns[idx]["label"])

	# build table from dict
	if isinstance(data.result[0], dict):
		for i, row in enumerate(data.result):
			# only rows which are visible in the report
			if row and (i in visible_idx):
				row_list = []
				for idx in range(len(data.columns)):
					row_list.append(
						row.get(columns[idx]["fieldname"], row.get(columns[idx]["label"], "")))
				result.append(row_list)
			elif not row:
				result.append([])
	else:
		result = result + \
			[d for i, d in enumerate(data.result) if (i in visible_idx)]

	return result
