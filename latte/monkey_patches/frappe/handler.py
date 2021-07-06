import frappe.handler
from latte.file_storage.file import uploadfile
frappe.handler.uploadfile = uploadfile
from latte.utils.file_patcher import patch

patch('from frappe.handler import uploadfile', 'uploadfile', uploadfile)