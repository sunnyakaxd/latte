import frappe
from frappe.email import email_body
import os

def inline_style_in_html(html):
	''' Convert email.css and html to inline-styled html
	'''
	from premailer import Premailer

	apps = frappe.get_installed_apps()

	css_files = []
	for app in apps:
		path = 'assets/{0}/css/email.css'.format(app)
		if os.path.exists(os.path.abspath(path)):
			css_files.append(path)

	p = Premailer(
		html=html,
		external_styles=css_files,
		strip_important=False,
		allow_loading_external_files=True,
	)

	return p.transform()

email_body.inline_style_in_html = inline_style_in_html
