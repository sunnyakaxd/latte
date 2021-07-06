import re
from frappe.model.meta import Meta, doctype_table_fields, load_doctype_from_file
import frappe
from frappe.utils import cint
from latte.business_process.powerflow.powerflow import Powerflow
from latte.business_process.constants import POWERFFLOW_CURRENT_STATE_FIELD
from frappe import local
from latte import migrating

old_init = Meta.__init__
old_process = Meta.process
old_get_valid_columns = Meta.get_valid_columns

def __init__(self, doctype):
	old_init(self, doctype)
	self.__field_type_map = {}
	self.table_fieldnames = [d.fieldname for d in self.get_fields_for_type('Table')]

	try:
		dt_meta = local.db.get_value('DocType Meta', self.name, (
			'cachable',
			'cache_timeout',
			'cache_in_memory',
		), as_dict=True)
	except:
		if not migrating():
			raise
		dt_meta = frappe._dict()

	self.not_cachable = not not (dt_meta and not dt_meta.cachable)
	self.cachable = not not (dt_meta.cachable if dt_meta else 0)
	self.memory_cachable = not not (dt_meta.cache_in_memory if dt_meta else 0)
	self.cache_timeout = (dt_meta.cache_timeout if dt_meta else 0) or None

def get_fields_for_type(self, fieldtype):
	try:
		return self.__field_type_map[fieldtype]
	except KeyError:
		fieldmap = self.__field_type_map[fieldtype] = [df for df in self.fields if df.fieldtype == fieldtype]
		return fieldmap

def get_link_fields(self):
	try:
		return self._link_fields
	except AttributeError:
		self._link_fields = self.get_fields_for_type('Link')
		return self._link_fields

writeable_fields = [
	'Attach',
	'Attach Image',
	'Barcode',
	'Check',
	'Code',
	'Color',
	'Currency',
	'Data',
	'Date',
	'Datetime',
	'Dynamic Link',
	'Float',
	'Geolocation',
	'HTML Editor',
	'Int',
	'Link',
	'Long Text',
	'Multi Select',
	'Password',
	'Percent',
	'Read Only',
	'Select',
	'Small Text',
	'Text',
	'Text Editor',
	'Time',
	'Signature',
	'LinkMultiSelect'
]

common_fields = [
	'creation',
	'modified',
	'modified_by',
	'owner',
	'docstatus',
	'parent',
	'parentfield',
	'parenttype',
	'idx',
	# '_comments',
	# '_assign',
	# '_user_tags',
]

def get_all_writable_fields(self):
	try:
		return self.__writable_fields, common_fields
	except AttributeError:
		self.__writable_fields = [
			field for field_type in writeable_fields
			for field in self.get_fields_for_type(field_type)
			if field.fieldname not in ('name', POWERFFLOW_CURRENT_STATE_FIELD)
		]
		return self.__writable_fields, common_fields

def get_table_fields(self):
	try:
		return self._table_fields
	except AttributeError:
		if self.name != "DocType":
			self._table_fields = self.get_fields_for_type('Table')
		else:
			self._table_fields = doctype_table_fields
		return self._table_fields

def apply_property_setters(self):
	property_setters = local.db.sql("""
		select
			*
		from
			`tabProperty Setter`
		where
			doc_type=%s
		""", (self.name,), as_dict=1)

	if not property_setters: return

	integer_docfield_properties = [d.fieldname for d in frappe.get_meta('DocField').fields
		if d.fieldtype in ('Int', 'Check')]

	for ps in property_setters:
		if ps.doctype_or_field=='DocType':
			if ps.property_type in ('Int', 'Check'):
				ps.value = cint(ps.value)

			setattr(self, ps.property, ps.value)
		else:
			docfield = self.get_field(ps.field_name)
			if not docfield:
				continue

			if ps.property in integer_docfield_properties:
				ps.value = cint(ps.value)

			setattr(docfield, ps.property, ps.value)

def get_select_fields(self):
	try:
		return self.__select_fields
	except AttributeError:
		self.__select_fields = [
			df for df in self.fields if df.fieldtype == 'Select'
			and df.options not in ("[Select]", "Loading...",)
		]
		return self.__select_fields

def process(self):
	old_process(self)
	if Powerflow.is_enabled_for(self.name):
		self.extend("fields",[frappe._dict(fieldtype='Data', fieldname=POWERFFLOW_CURRENT_STATE_FIELD, label='Document State', permlevel = 0, hidden =1)])

def get_valid_columns(self):
	valid_columns = old_get_valid_columns(self)
	if valid_columns:
		if POWERFFLOW_CURRENT_STATE_FIELD in valid_columns: valid_columns.remove(POWERFFLOW_CURRENT_STATE_FIELD)
	return valid_columns

def get_fields_with_regex_pattern(self):
	try:
		return self.__regex_pattern_fields
	except AttributeError:
		self.__regex_pattern_fields = [field for field in self.fields if getattr(field, 'regex_pattern', None)]
		return self.__regex_pattern_fields

def get_auto_incr_fields(self):
	try:
		return self.__auto_incr_fields
	except AttributeError:
		self.__auto_incr_fields = [
			field
			for field in self.get_table_fields()
			if frappe.get_meta(field.options).autoname == 'auto_increment'
		]
		return self.__auto_incr_fields

def load_from_db(self, for_update=False):
	try:
		super(Meta, self).load_from_db(for_update=for_update)
	except frappe.DoesNotExistError:
		if self.doctype=="DocType" and self.name in self.special_doctypes:
			self.__dict__.update(load_doctype_from_file(self.name))
		else:
			raise

def get_new_doc_defaults(self):
	try:
		return self.__new_doc_defaults
	except AttributeError:
		self.__new_doc_defaults = frappe.new_doc(self.name, as_dict=True)
		return self.__new_doc_defaults

Meta.__init__ = __init__
Meta.get_new_doc_defaults = get_new_doc_defaults
Meta.get_all_writable_fields = get_all_writable_fields
Meta.get_fields_for_type = get_fields_for_type
Meta.get_table_fields = get_table_fields
Meta.apply_property_setters = apply_property_setters
Meta.process = process
Meta.get_valid_columns = get_valid_columns
Meta.get_fields_with_regex_pattern = get_fields_with_regex_pattern
Meta.get_auto_incr_fields = get_auto_incr_fields
Meta.load_from_db = load_from_db
