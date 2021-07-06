import frappe
import subprocess
from urllib.parse import unquote
def get_pdf_data(doctype, names, print_format, no_letterhead=1):
	html = ''.join(frappe.get_print(doctype, i, print_format, no_letterhead=no_letterhead)
		for i in names
	)

	flags = '--print-media-type \
	--images \
	--encoding UTF-8 \
	--quiet \
	--margin-right 15mm \
	--margin-left 15mm \
	--page-size A4 \
	- -'
	pipe = subprocess.Popen(
		[f'wkhtmltopdf {flags}'],
		stdout=subprocess.PIPE,
		stdin=subprocess.PIPE,
		shell=True,
	)
	output, error = pipe.communicate(input=html.encode('utf-8'))
	if pipe.returncode:
		raise Exception(f'Subprocess call failed({pipe.returncode}) with error', error)
	return output

@frappe.whitelist(allow_guest=True)
def download_pdf(doctype, name, format):
	frappe.response['filecontent'] = get_pdf_data(doctype, [name], format)
	frappe.response['type'] = 'pdf'
	frappe.response['filename'] = 'download.pdf'

def override_deskpermission(fn):
	'''
	This function will allow guest users to access api
	'''
	def innerfn(**kwargs):
		frappe.session.user = 'customer@elastic.run'
		response = fn(**kwargs)
		frappe.session.user= 'Guest'
		return response
	return innerfn

@frappe.whitelist(allow_guest=True)
@override_deskpermission
def download_print(**kwargs):
	'''
	Accepts kw parameters
	{'token': 'toke_value', 'format': 'print_format_name'}
	'''
	from withrun_erpnext.withrun_erpnext.doctype.auth_token.auth_token import get_decoded_content
	if not kwargs.get("token"):
		frappe.throw('Token Missing')
	data = get_decoded_content(unquote(kwargs.get('token')), is_expiry_check=True, return_references=True)
	if not data:
		frappe.throw('Token Expired')
	frappe.response['filecontent'] = get_pdf_data(data.get("reference_doctype"), [data.get("reference_name")], unquote(kwargs.get("format")))
	frappe.response['type'] = 'pdf'
	frappe.response['filename'] = f'{data.get("reference_doctype")}-{data.get("reference_name")}.pdf'

@frappe.whitelist(allow_guest=True)
@override_deskpermission
def convert_html_to_pdf(**kwargs):
	html = kwargs.get('html')
	frappe.response.filename = f'catalogue-{frappe.utils.today()}.pdf'
	flags = '--print-media-type \
	--images \
	--encoding UTF-8 \
	--quiet \
	--margin-right 10mm \
	--margin-left 10mm \
	--page-size A4 \
	- -'

	process = subprocess.Popen(
		[f'wkhtmltopdf {flags}'],
		stdout=subprocess.PIPE,
		stdin=subprocess.PIPE,
		shell=True,
	)
	output, _ = process.communicate(input=html.encode('utf-8'))
	frappe.response.filecontent = output
	frappe.response.type = "download"
	

