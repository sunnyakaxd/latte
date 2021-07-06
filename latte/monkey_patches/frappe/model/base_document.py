import frappe
import datetime
from frappe.model.base_document import BaseDocument, set_new_name, set_encrypted_password, default_fields
from frappe.utils import cint, cstr, now, flt, compare
from frappe import _
from latte.model.document import core_doctypes_list
from six import string_types
from frappe.utils.file_manager import extract_images_from_doc
from frappe import local

def db_insert(self):
	while not db_insert_wrapped(self).name:
		pass

	if self.flags.reset_children_parent:
		for row in self.get_all_children():
			row.parent = self.name

def db_insert_wrapped(self):
	"""INSERT the document (with valid columns) in the database."""

	if not self.creation:
		self.creation = self.modified = now()
		self.created_by = self.modified_by = local.session.user

	if (self.meta.autoname or '').lower() != 'auto_increment':
		if not self.name:
			# name will be set by document class in most cases
			set_new_name(self)
		d = self.get_valid_dict(convert_dates_to_str=True)
	else:
		d = self.get_valid_dict(convert_dates_to_str=True)
		d.pop('name', None)

	try:
		local.db.sql(f"""
			insert into `tab{self.doctype}`
				({", ".join(f"`{c}`" for c in d)})
			values
				({", ".join(["%s"] * len(d))})
		""", list(d.values()))
	except Exception as e:
		err_code, err = e.args[0], cstr(e.args[1])
		if err_code != 1062:
			raise

		if "PRIMARY" in err:
			if self.meta.autoname == "hash" or self.flags.retry_on_duplicate_insert:
				# hash collision? try again
				self.name = None
				self.flags.reset_children_parent = True
				return self

			raise frappe.DuplicateEntryError(self.doctype, self.name, e)

		elif "Duplicate" in err:
			# unique constraint
			self.show_unique_validation_message(e)
		else:
			raise

	if (self.meta.autoname or '').lower() == 'auto_increment':
		self.name = f'{local.db.sql("select last_insert_id()")[0][0]}'
		self.flags.reset_children_parent = True

	if not self.name:
		frappe.throw('Auto increment failed')

	self.set("__islocal", False)
	return self

BaseDocument.db_insert = db_insert

def db_update(self):
	if self.get("__islocal") or not self.name:
		return self.db_insert()

	doc_before_save = self.get_doc_before_save(raise_error=True)

	# d = self.get_valid_dict(convert_dates_to_str=True)
	fields, common_fields = self.meta.get_all_writable_fields()
	# don't update name, as case might've been changed
	# name = d['name']
	# del d['name']

	# columns = list(d)
	values = {}

	for field in fields:
		if (value := getattr(self, field.fieldname)) != getattr(doc_before_save, field.fieldname):
			values[field.fieldname] = get_value(field, value)

	for field in common_fields:
		if (value := getattr(self, field)) != getattr(doc_before_save, field):
			values[field] = str(value)

	if values:
		values['name'] = self.name
	else:
		return

	try:
		local.db.sql(f"""
			update
				`tab{self.doctype}`
			set
				{','.join(
					f'`{fieldname}` = %({fieldname})s'
					for fieldname in values if fieldname != 'name'
				)}
			where
				name = %(name)s
		""", values)
	except Exception as e:
		if e.args[0]==1062 and "Duplicate" in cstr(e.args[1]):
			self.show_unique_validation_message(e)
		else:
			raise

	self.name = str(self.name)

old_db_update = BaseDocument.db_update
def simple_db_update(self):
	retval = old_db_update(self)
	self.name = str(self.name)
	return retval
# BaseDocument.db_update = simple_db_update

def get_value(df, value):
	if df.fieldtype=="Check":
		if value is None:
			value = 0
		else:
			value = int(not not cint(value))

	elif df.fieldtype=="Int" and not isinstance(value, int):
		value = cint(value)

	elif df.fieldtype in ("Currency", "Float", "Percent") and not isinstance(value, float):
		value = flt(value)

	elif df.fieldtype in ("Datetime", "Date", "Time") and value=="":
		value = None

	elif df.get("unique") and cstr(value).strip()=="":
		# unique empty field should be set to None
		value = None

	elif df.fieldtype in ("Data", "Link", "Select", "Dynamic Link", "Color") and value is None:
		value = ''

	elif isinstance(value, list) and df.fieldtype != 'Table':
		frappe.throw(f'Value for {df.label} cannot be a list')

	elif isinstance(value, (datetime.datetime, datetime.time, datetime.timedelta)):
		value = str(value)

	return value

BaseDocument.db_update = db_update

def get_valid_dict(self, sanitize=True, convert_dates_to_str=False):
	d = frappe._dict()
	for fieldname in self.meta.get_valid_columns():
		d[fieldname] = self.get(fieldname)

		# if no need for sanitization and value is None, continue
		if not sanitize and d[fieldname] is None:
			continue

		df = self.meta.get_field(fieldname)
		if df:
			if df.fieldtype=="Check":
				if d[fieldname]==None:
					d[fieldname] = 0

				elif (not isinstance(d[fieldname], int) or d[fieldname] > 1):
					d[fieldname] = 1 if cint(d[fieldname]) else 0

			elif df.fieldtype=="Int" and not isinstance(d[fieldname], int):
				d[fieldname] = cint(d[fieldname])

			elif df.fieldtype in ("Currency", "Float", "Percent") and not isinstance(d[fieldname], float):
				d[fieldname] = flt(d[fieldname])

			elif df.fieldtype in ("Datetime", "Date", "Time") and d[fieldname]=="":
				d[fieldname] = None

			elif df.get("unique") and cstr(d[fieldname]).strip()=="":
				# unique empty field should be set to None
				d[fieldname] = None

			elif df.fieldtype in ("Data", "Link", "Select", "Dynamic Link") and d[fieldname] is None:
				d[fieldname] = ''

			if isinstance(d[fieldname], list) and df.fieldtype != 'Table':
				frappe.throw(_('Value for {0} cannot be a list').format(_(df.label)))

			if convert_dates_to_str and isinstance(d[fieldname], (datetime.datetime, datetime.time, datetime.timedelta)):
				d[fieldname] = str(d[fieldname])

	return d

BaseDocument.get_valid_dict = get_valid_dict

def get(self, key=None, filters=None, limit=None, default=None):
	if key:
		if isinstance(key, dict):
			return _filter(self.get_all_children(), key, limit=limit)
		if filters:
			if isinstance(filters, dict):
				value = _filter(self.__dict__.get(key, []), filters, limit=limit)
			else:
				default = filters
				filters = None
				value = getattr(self, key, default)
		else:
			value = getattr(self, key, default)

		if value is None and key not in self.ignore_in_getter \
			and key in self.meta.table_fieldnames:
			self.set(key, [])
			value = getattr(self, key, None)

		return value
	else:
		return self.__dict__

def _filter(data, filters, limit=None):
	"""pass filters as:
		{"key": "val", "key": ["!=", "val"],
		"key": ["in", "val"], "key": ["not in", "val"], "key": "^val",
		"key" : True (exists), "key": False (does not exist) }"""

	out, _filters = [], {}

	if not data:
		return out

	# setup filters as tuples
	if filters:
		# import traceback
		# traceback.print_stack()
		for f in filters:
			fval = filters[f]

			if not isinstance(fval, (tuple, list)):
				if fval is True:
					fval = ("not None", fval)
				elif fval is False:
					fval = ("None", fval)
				elif isinstance(fval, string_types) and fval.startswith("^"):
					fval = ("^", fval[1:])
				else:
					fval = ("=", fval)

			_filters[f] = fval

	for d in data:
		add = True
		for f, fval in _filters.items():
			if not compare(getattr(d, f, None), fval[0], fval[1]):
				add = False
				break

		if add:
			out.append(d)
			if limit and (len(out)-1)==limit:
				break

	return out

def _save_passwords(self):
	'''Save password field values in __Auth table'''
	if self.flags.ignore_save_passwords is True:
		return

	for df in self.meta.get_fields_for_type('Password'):
		if self.flags.ignore_save_passwords and df.fieldname in self.flags.ignore_save_passwords: continue
		new_password = self.get(df.fieldname)
		if new_password and not self.is_dummy_password(new_password):
			# is not a dummy password like '*****'
			set_encrypted_password(self.doctype, self.name, new_password, df.fieldname)

			# set dummy password like '*****'
			self.set(df.fieldname, '*'*len(new_password))

def _extract_images_from_text_editor(self):
	if self.doctype != "DocType":
		for df in self.meta.get_fields_for_type('Text Editor'):
			extract_images_from_doc(self, df.fieldname)

def get_msg(df, docname, idx=None):
	return f'{df.label}: {docname}' if idx is None else f"Row #{idx}: {df.label}: {docname}"

def get_invalid_links(self, is_submittable=False, with_message=True):
	'''Returns list of invalid links and also updates fetch values if not set'''
	invalid_links = []
	cancelled_links = []

	for df in (self.meta.get_link_fields() + self.meta.get_fields_for_type("Dynamic Link")):
		docname = getattr(self, df.fieldname, None)

		if not docname:
			continue

		if df.fieldtype=="Link":
			doctype = df.options
			if not doctype:
				frappe.throw(_("Options not set for link field {0}").format(df.fieldname))
		else:
			doctype = getattr(self, df.options)
			if not doctype:
				frappe.throw(_("{0} must be set first").format(self.meta.get_label(df.options)))

		# MySQL is case insensitive. Preserve case of the original docname in the Link Field.

		# get a map of values ot fetch along with this link query
		# that are mapped as link_fieldname.source_fieldname in Options of
		# Readonly or Data or Text type fields

		fields_to_fetch = [
			_df for _df in self.meta.get_fields_to_fetch(df.fieldname)
			if
				not _df.get('fetch_if_empty')
				or (_df.get('fetch_if_empty') and not self.get(_df.fieldname))
		]

		if not fields_to_fetch:
			# cache a single value type
			values = frappe._dict(name=local.db.get_value(doctype, docname,
				'name', cache=True))
		else:
			values_to_fetch = ['name'] + [_df.fetch_from.split('.')[-1]
				for _df in fields_to_fetch]

			# don't cache if fetching other values too
			values = local.db.get_value(doctype, docname,
				values_to_fetch, as_dict=True)

		if frappe.get_meta(doctype).issingle:
			values.name = doctype

		if values:
			setattr(self, df.fieldname, values.name)

			for _df in fields_to_fetch:
				if self.is_new() or self.docstatus != 1 or _df.allow_on_submit:
					setattr(self, _df.fieldname, values[_df.fetch_from.split('.')[-1]])

			if not values.name:
				invalid_links.append((
					df.fieldname,
					docname,
					with_message and get_msg(df, docname, self.idx),
					doctype,
				))

			elif (df.fieldname != "amended_from"
				and (is_submittable or self.meta.is_submittable) and frappe.get_meta(doctype).is_submittable
				and cint(local.db.get_value(doctype, docname, "docstatus"))==2):

				cancelled_links.append((
					df.fieldname,
					docname,
					with_message and get_msg(df, docname, self.idx),
					doctype,
				))

	return invalid_links, cancelled_links

def init_valid_columns(self):
	for key in default_fields:
		if key not in self.__dict__:
			self.__dict__[key] = None

		if key in ("idx", "docstatus") and self.__dict__[key] is None:
			self.__dict__[key] = 0

	for key in self.get_valid_columns():
		if key not in self.__dict__:
			self.__dict__[key] = None

	if self.doctype not in core_doctypes_list:
		for field in self.meta.get_table_fields():
			self.get(field.fieldname)

BaseDocument.init_valid_columns = init_valid_columns
BaseDocument.get_invalid_links = get_invalid_links
BaseDocument._extract_images_from_text_editor = _extract_images_from_text_editor
BaseDocument.get = get
BaseDocument._save_passwords = _save_passwords
