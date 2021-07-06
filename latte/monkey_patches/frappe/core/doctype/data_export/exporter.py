import frappe
import latte
from frappe.utils import formatdate, format_datetime
from frappe.core.doctype.data_export.exporter import DataExporter
from frappe.core.doctype.data_export.exporter import export_data

def add_data_row(self, rows, dt, parentfield, doc, rowidx):
	d = doc.copy()
	meta = frappe.get_meta(dt)
	if self.all_doctypes:
		d.name = f'"{d.name}"'

	if len(rows) < rowidx + 1:
		rows.append([""] * (len(self.columns) + 1))
	row = rows[rowidx]

	_column_start_end = self.column_start_end.get((dt, parentfield))

	if _column_start_end:
		for i, c in enumerate(self.columns[_column_start_end.start:_column_start_end.end]):
			df = meta.get_field(c)
			fieldtype = df.fieldtype if df else "Data"
			value = d.get(c, "")
			if value:
				if fieldtype == "Date":
					value = formatdate(value)
				elif fieldtype == "Datetime":
					value = format_datetime(value)

			row[_column_start_end.start + i + 1] = value

DataExporter.add_data_row = add_data_row

@frappe.whitelist()
@latte.read_only()
def read_only_export_data(doctype=None, parent_doctype=None, all_doctypes=True, with_data=False,
		select_columns=None, file_type='CSV', template=False, filters=None):
	export_data(
		doctype=doctype,
		parent_doctype=parent_doctype,
		all_doctypes=all_doctypes,
		with_data=with_data,
		select_columns=select_columns,
		file_type=file_type,
		template=template,
		filters=filters
	)