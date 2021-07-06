# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from frappe import _
import frappe
from latte.file_storage import file

def do_nothing(*_, **__):
    pass

frappe.core.doctype.file.file.File = file.File
frappe.core.doctype.file.file.make_home_folder = do_nothing
