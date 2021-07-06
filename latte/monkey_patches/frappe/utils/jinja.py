import frappe.utils.jinja
from latte.json import loads, dumps
from latte.monkey_patches.frappe.desk.query_report import generate_report_result
import pyqrcode
from frappe import local
from base64 import b64decode
from frappe import throw

old_get_jenv_env = frappe.utils.jinja.get_allowed_functions_for_jenv


def generate_report_result_sql_list(report, filters=None, user=None , column_name = None, should_add_total_row=True):
	data = generate_report_result(report, filters, user, should_add_total_row)
	columns = data['columns']
	result = data['result']

	col_index = 0
	for index in range(len(columns)):
		if columns[index] == column_name :
			col_index = index

	final_result = []

	if len(result) == 0:
		return ('','')
	elif len(result) == 1:
		return ('',result[0][col_index])
	else:
		for index in range(len(result)):
			final_result.append(result[index][col_index])

	return tuple(final_result)

def get_qrcode(inputstring, scale=1):
	'''
		Returns image tag of printable QR code as passed in b64 string

		:param: inputstring
		-------------
			base 64 string

		:param: scale
		-------------
			Default: 1
			Can be used for proportioning
	'''

	qr_code = pyqrcode.create(inputstring)
	qr_code_as_str = qr_code.png_as_base64_str(scale=scale)
	html_img = f'''<img src="data:image/svg;base64,{qr_code_as_str}">'''
	return html_img

def get_allowed_functions_for_jenv():
	out = old_get_jenv_env()
	out['frappe']['loads'] = loads
	out['frappe']['get_cached_doc'] = frappe.get_cached_doc
	out['frappe']['get_cached_value'] = frappe.get_cached_value
	out['frappe']['read_only_sql'] = lambda *args, **kwargs: frappe.db.read_only_sql(*args, **kwargs)
	out['frappe']['get_report_data_as_sql_list'] = generate_report_result_sql_list
	out['frappe']['conf'] = frappe.local.conf
	out['frappe']['get_qrcode'] = get_qrcode
	out['frappe']['b64decode'] = b64decode
	out['frappe']['throw'] = throw
	return out

frappe.utils.jinja.get_allowed_functions_for_jenv = get_allowed_functions_for_jenv