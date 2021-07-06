from frappe.utils.xlsxutils import load_workbook
import frappe.utils.xlsxutils
from latte.file_storage.file import File

def read_xlsx_file_from_attached_file(file_id=None, fcontent=None):
	if file_id:
		file_doc = File.find_by_file_url(file_id) or File.find_by_file_name(file_id)
		stream = file_doc.get_data_stream()
	elif fcontent:
		from io import BytesIO
		stream = BytesIO(fcontent)
	else:
		return

	rows = []
	try:
		wb1 = load_workbook(filename=stream, read_only=True, data_only=True)
		ws1 = wb1.active
		for row in ws1.iter_rows():
			tmp_list = []
			for cell in row:
				tmp_list.append(cell.value)
			rows.append(tmp_list)
		return rows
	finally:
		hasattr(stream, 'close') and stream.close()


frappe.utils.xlsxutils.read_xlsx_file_from_attached_file = read_xlsx_file_from_attached_file