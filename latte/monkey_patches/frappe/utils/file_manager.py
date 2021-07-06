import frappe.utils.file_manager
from latte.file_storage.file import File

def get_file(fname):
	"""Returns [`file_name`, `content`] for given file name `fname`"""

	file_doc = File.find_by_file_url(fname) or File.find_by_file_name(fname)
	return [file_doc.file_name, file_doc.get_data()]

frappe.utils.file_manager.get_file = get_file