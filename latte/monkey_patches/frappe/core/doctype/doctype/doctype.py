import frappe
from frappe.utils import cint
from pymysql.err import InternalError, OperationalError
from frappe.core.doctype.doctype import doctype
from frappe.core.doctype.doctype.doctype import (
	DocType,
	ER,
	validate_column_name,
	validate_column_length,
	no_value_fields,
	_,
	re,
	InvalidFieldNameError,
	default_fields,
	copy
)

old_validate_series = DocType.validate_series
def validate_series(self):
	if self.autoname == 'auto_increment':
		return
	else:
		return old_validate_series(self)

DocType.validate_series = validate_series

def validate_fields(meta):
	"""Validate doctype fields. Checks

	1. There are no illegal characters in fieldnames
	2. If fieldnames are unique.
	3. Validate column length.
	4. Fields that do have database columns are not mandatory.
	5. `Link` and `Table` options are valid.
	6. **Hidden** and **Mandatory** are not set simultaneously.
	7. `Check` type field has default as 0 or 1.
	8. `Dynamic Links` are correctly defined.
	9. Precision is set in numeric fields and is between 1 & 6.
	10. Fold is not at the end (if set).
	11. `search_fields` are valid.
	12. `title_field` and title field pattern are valid.
	13. `unique` check is only valid for Data, Link and Read Only fieldtypes.
	14. `unique` cannot be checked if there exist non-unique values.

	:param meta: `frappe.model.meta.Meta` object to check."""
	def check_illegal_characters(fieldname):
		validate_column_name(fieldname)

	def check_unique_fieldname(fieldname):
		duplicates = list(filter(None, map(lambda df: df.fieldname==fieldname and str(df.idx) or None, fields)))
		if len(duplicates) > 1:
			frappe.throw(_("Fieldname {0} appears multiple times in rows {1}").format(fieldname, ", ".join(duplicates)))

	def check_fieldname_length(fieldname):
		validate_column_length(fieldname)

	def check_illegal_mandatory(d):
		if (d.fieldtype in no_value_fields) and d.fieldtype!="Table" and d.reqd:
			frappe.throw(_("Field {0} of type {1} cannot be mandatory").format(d.label, d.fieldtype))

	def check_link_table_options(d):
		if d.fieldtype in ("Link", "Table"):
			if not d.options:
				frappe.throw(_("Options required for Link or Table type field {0} in row {1}").format(d.label, d.idx))
			if d.options=="[Select]" or d.options==d.parent:
				return
			if d.options != d.parent:
				options = frappe.db.get_value("DocType", d.options, "name")
				if not options:
					frappe.throw(_("Options must be a valid DocType for field {0} in row {1}").format(d.label, d.idx))
				elif not (options == d.options):
					frappe.throw(_("Options {0} must be the same as doctype name {1} for the field {2}")
						.format(d.options, options, d.label))
				else:
					# fix case
					d.options = options

	def check_hidden_and_mandatory(d):
		if d.hidden and d.reqd and not d.default:
			frappe.throw(_("Field {0} in row {1} cannot be hidden and mandatory without default").format(d.label, d.idx))

	def check_width(d):
		if d.fieldtype == "Currency" and cint(d.width) < 100:
			frappe.throw(_("Max width for type Currency is 100px in row {0}").format(d.idx))

	def check_in_list_view(d):
		if d.in_list_view and (d.fieldtype in not_allowed_in_list_view):
			frappe.throw(_("'In List View' not allowed for type {0} in row {1}").format(d.fieldtype, d.idx))

	def check_in_global_search(d):
		if d.in_global_search and d.fieldtype in no_value_fields:
			frappe.throw(_("'In Global Search' not allowed for type {0} in row {1}")
				.format(d.fieldtype, d.idx))

	def check_dynamic_link_options(d):
		if d.fieldtype=="Dynamic Link":
			doctype_pointer = list(filter(lambda df: df.fieldname==d.options, fields))
			if not doctype_pointer or (doctype_pointer[0].fieldtype not in ("Link", "Select")) \
				or (doctype_pointer[0].fieldtype=="Link" and doctype_pointer[0].options!="DocType"):
				frappe.throw(_("Options 'Dynamic Link' type of field must point to another Link Field with options as 'DocType'"))

	def check_illegal_default(d):
		if d.fieldtype == "Check" and d.default and d.default not in ('0', '1'):
			frappe.throw(_("Default for 'Check' type of field must be either '0' or '1'"))
		if d.fieldtype == "Select" and d.default and (d.default not in d.options.split("\n")):
			frappe.throw(_("Default for {0} must be an option").format(d.fieldname))

	def check_precision(d):
		if d.fieldtype in ("Currency", "Float", "Percent") and d.precision is not None and not (1 <= cint(d.precision) <= 6):
			frappe.throw(_("Precision should be between 1 and 6"))

	def check_unique_and_text(d):
		if meta.issingle:
			d.unique = 0
			d.search_index = 0

		if getattr(d, "unique", False):
			if d.fieldtype not in ("Data", "Link", "Read Only"):
				frappe.throw(_("Fieldtype {0} for {1} cannot be unique").format(d.fieldtype, d.label))

			if not d.get("__islocal"):
				try:
					has_non_unique_values = frappe.db.sql("""select `{fieldname}`, count(*)
						from `tab{doctype}` where ifnull({fieldname}, '') != ''
						group by `{fieldname}` having count(*) > 1 limit 1""".format(
						doctype=d.parent, fieldname=d.fieldname))

				except (InternalError, OperationalError) as e:
					if e.args and e.args[0] == ER.BAD_FIELD_ERROR:
						# ignore if missing column, else raise
						# this happens in case of Custom Field
						pass
					else:
						raise

				else:
					# else of try block
					if has_non_unique_values and has_non_unique_values[0][0]:
						frappe.throw(_("Field '{0}' cannot be set as Unique as it has non-unique values").format(d.label))

		if d.search_index and d.fieldtype in ("Text", "Long Text", "Small Text", "Code", "Text Editor"):
			frappe.throw(_("Fieldtype {0} for {1} cannot be indexed").format(d.fieldtype, d.label))

	def check_fold(fields):
		fold_exists = False
		for i, f in enumerate(fields):
			if f.fieldtype=="Fold":
				if fold_exists:
					frappe.throw(_("There can be only one Fold in a form"))
				fold_exists = True
				if i < len(fields)-1:
					nxt = fields[i+1]
					if nxt.fieldtype != "Section Break":
						frappe.throw(_("Fold must come before a Section Break"))
				else:
					frappe.throw(_("Fold can not be at the end of the form"))

	def check_search_fields(meta, fields):
		"""Throw exception if `search_fields` don't contain valid fields."""
		if not meta.search_fields:
			return

		# No value fields should not be included in search field
		search_fields = [field.strip() for field in (meta.search_fields or "").split(",")]
		fieldtype_mapper = { field.fieldname: field.fieldtype \
			for field in filter(lambda field: field.fieldname in search_fields, fields) }

		for fieldname in search_fields:
			fieldname = fieldname.strip()
			if (fieldtype_mapper.get(fieldname) in no_value_fields) or \
				(fieldname not in fieldname_list):
				frappe.throw(_("Search field {0} is not valid").format(fieldname))

	def check_title_field(meta):
		"""Throw exception if `title_field` isn't a valid fieldname."""
		if not meta.get("title_field"):
			return

		if meta.title_field not in fieldname_list:
			frappe.throw(_("Title field must be a valid fieldname"), InvalidFieldNameError)

		def _validate_title_field_pattern(pattern):
			if not pattern:
				return

			for fieldname in re.findall("{(.*?)}", pattern, re.UNICODE):
				if fieldname.startswith("{"):
					# edge case when double curlies are used for escape
					continue

				if fieldname not in fieldname_list:
					frappe.throw(_("{{{0}}} is not a valid fieldname pattern. It should be {{field_name}}.").format(fieldname),
						InvalidFieldNameError)

		df = meta.get("fields", filters={"fieldname": meta.title_field})[0]
		if df:
			_validate_title_field_pattern(df.options)
			_validate_title_field_pattern(df.default)

	def check_image_field(meta):
		'''check image_field exists and is of type "Attach Image"'''
		if not meta.image_field:
			return

		df = meta.get("fields", {"fieldname": meta.image_field})
		if not df:
			frappe.throw(_("Image field must be a valid fieldname"), InvalidFieldNameError)
		if df[0].fieldtype != 'Attach Image':
			frappe.throw(_("Image field must be of type Attach Image"), InvalidFieldNameError)

	def check_is_published_field(meta):
		if not meta.is_published_field:
			return

		if meta.is_published_field not in fieldname_list:
			frappe.throw(_("Is Published Field must be a valid fieldname"), InvalidFieldNameError)

	def check_timeline_field(meta):
		if not meta.timeline_field:
			return

		if meta.timeline_field not in fieldname_list:
			frappe.throw(_("Timeline field must be a valid fieldname"), InvalidFieldNameError)

		df = meta.get("fields", {"fieldname": meta.timeline_field})[0]
		if df.fieldtype not in ("Link", "Dynamic Link"):
			frappe.throw(_("Timeline field must be a Link or Dynamic Link"), InvalidFieldNameError)

	def check_sort_field(meta):
		'''Validate that sort_field(s) is a valid field'''
		if meta.sort_field:
			sort_fields = [meta.sort_field]
			if ','  in meta.sort_field:
				sort_fields = [d.split()[0] for d in meta.sort_field.split(',')]

			for fieldname in sort_fields:
				if not fieldname in fieldname_list + list(default_fields):
					frappe.throw(_("Sort field {0} must be a valid fieldname").format(fieldname),
						InvalidFieldNameError)

	def check_illegal_depends_on_conditions(docfield):
		''' assignment operation should not be allowed in the depends on condition.'''
		depends_on_fields = ["depends_on", "collapsible_depends_on"]
		for field in depends_on_fields:
			depends_on = docfield.get(field, None)
			if depends_on and ("=" in depends_on) and \
				re.match("""[\w\.:_]+\s*={1}\s*[\w\.@'"]+""", depends_on):
				frappe.throw(_("Invalid {0} condition").format(frappe.unscrub(field)), frappe.ValidationError)

	def scrub_options_in_select(field):
		"""Strip options for whitespaces"""

		if field.fieldtype == "Select" and field.options is not None:
			options_list = []
			for i, option in enumerate(field.options.split("\n")):
				_option = option.strip()
				if i==0 or _option:
					options_list.append(_option)
			field.options = '\n'.join(options_list)

	def scrub_fetch_from(field):
		if hasattr(field, 'fetch_from') and getattr(field, 'fetch_from'):
			field.fetch_from = field.fetch_from.strip('\n').strip()

	fields = meta.get("fields")
	fieldname_list = [d.fieldname for d in fields]

	not_allowed_in_list_view = list(copy.copy(no_value_fields))
	not_allowed_in_list_view.append("Attach Image")
	if meta.istable:
		not_allowed_in_list_view.remove('Button')

	for d in fields:
		if not d.permlevel: d.permlevel = 0
		if d.fieldtype != "Table": d.allow_bulk_edit = 0
		if d.fieldtype == "Barcode": d.ignore_xss_filter = 1
		if not d.fieldname:
			d.fieldname = d.fieldname.lower()

		check_illegal_characters(d.fieldname)
		check_unique_fieldname(d.fieldname)
		check_fieldname_length(d.fieldname)
		check_illegal_mandatory(d)
		check_link_table_options(d)
		check_dynamic_link_options(d)
		check_hidden_and_mandatory(d)
		check_in_list_view(d)
		check_in_global_search(d)
		check_illegal_default(d)
		check_unique_and_text(d)
		check_illegal_depends_on_conditions(d)
		scrub_options_in_select(d)
		scrub_fetch_from(d)

	check_fold(fields)
	check_search_fields(meta, fields)
	check_title_field(meta)
	check_timeline_field(meta)
	check_is_published_field(meta)
	check_sort_field(meta)
	check_image_field(meta)

doctype.validate_fields = validate_fields