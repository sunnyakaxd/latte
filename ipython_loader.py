print('Loading gevent patches')
from gevent import monkey
monkey.patch_all()
from latte.commands.utils import patch_all
patch_all()
import frappe
import latte
from os import environ
latte.init(site=environ['site'])
latte.connect()
frappe.local.flags.request_id = frappe.local.flags.task_id = 'bench-console'
frappe.local.lang = frappe.db.get_default("lang")
frappe.local.flags.ipython = True
frappe.set_user('Administrator')
print(f'Loaded site {frappe.local.site}')
