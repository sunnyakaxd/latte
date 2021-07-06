import re
import frappe
import frappe.model.document
import frappe.model.base_document

from frappe.model.document import Document
from frappe.utils import cstr

from latte.file_storage.file import File
from latte.model.document import get_controller
from latte.business_process.powerflow.powerflow import Powerflow
from latte.utils.printing import get_pdf_data
from latte.file_storage.file import upload_from_data
from latte.business_process.powerflow_exceptions import PowerflowNotFoundException
from frappe.model.naming import set_new_name
from frappe import local
from pymysql.err import OperationalError
from latte.utils.caching import cache_in_mem
from latte import migrating

def cancel(self, ignore_permissions=False, communication_log=None):
	self.docstatus = 2
	self.save(ignore_permissions=self.flags.ignore_permissions or ignore_permissions)
	if communication_log:
		frappe.get_doc({
			'doctype': 'Communication',
			'reference_name': self.name,
			'reference_doctype': self.doctype,
			'communication_type': 'Comment',
			'comment_type': 'Cancelled',
			'content': communication_log,
		}).insert(ignore_permissions=True)

def copy_attachments_from_amended_from(self):
	'''Copy attachments from `amended_from`'''
	File.copy_attachments_from(
		self.doctype,
		self.amended_from,
		self.doctype,
		self.name,
	)

old_validate_links = Document._validate_links

def _validate_links(self):
	self.run_method('before_link_validation')
	return old_validate_links(self)


def run_before_save_methods(self):
	"""Run standard methods before  `INSERT` or `UPDATE`. Standard Methods are:

	- `validate`, `before_save` for **Save**.
	- `validate`, `before_submit` for **Submit**.
	- `before_cancel` for **Cancel**
	- `before_update_after_submit` for **Update after Submit**

	Will also update title_field if set"""

	self.load_doc_before_save()
	self.reset_seen()

	if self._action=="save":
		if not self.flags.ignore_validate:
			self.run_method("before_validate")
			self.validate_regex_pattern()
			self.run_method("validate")
		self.run_method("before_save")
	elif self._action=="submit":
		if not self.flags.ignore_validate:
			self.run_method("before_validate")
			self.validate_regex_pattern()
			self.run_method("validate")
		self.run_method("before_submit")
	elif self._action=="cancel":
		self.run_method("before_cancel")
	elif self._action=="update_after_submit":
		self.run_method("before_update_after_submit")

	else:
		self.run_method(f"before_{self._action}")

	self.set_title_field()

def validate_regex_pattern(self):
	''' Validate data in the field is as per the regex pattern set'''

	for field in self.meta.get_fields_with_regex_pattern():
		try:
			value = getattr(self, field.fieldname)
			regex_pattern = re.compile(field.regex_pattern)
			if not regex_pattern.match(value):
				frappe.throw(f'Invalid {field.label} - "{value}".')
		except re.error as e:
			frappe.throw(f'Please contact tech support to correct the Regular Expression Pattern for field ({field.label}). Error - ({e})', re.error)


def run_post_save_methods(self):
	"""Run standard methods after `INSERT` or `UPDATE`. Standard Methods are:

	- `on_update` for **Save**.
	- `on_update`, `on_submit` for **Submit**.
	- `on_cancel` for **Cancel**
	- `update_after_submit` for **Update after Submit**"""
	if self._action=="save":
		self.run_method("on_update")
	elif self._action=="submit":
		self.run_method("on_update")
		self.run_method("on_submit")
	elif self._action=="cancel":
		self.run_method("on_cancel")
		self.check_no_back_links_exist()
	elif self._action=="update_after_submit":
		self.run_method("on_update_after_submit")

	else:
		self.run_method(f"on_{self._action}")

	self.run_method('on_change')

	self.update_timeline_doc()
	self.clear_cache()
	self.notify_update()

	if getattr(self.meta, 'track_changes', False) and self._doc_before_save and not self.flags.ignore_version:
		self.save_version()

	if (self.doctype, self.name) in frappe.flags.currently_saving:
		frappe.flags.currently_saving.remove((self.doctype, self.name))

	self.latest = None


def get_all_children(self, parenttype=None):
	"""Returns all children documents from **Table** type field in a list."""
	ret = []
	for df in self.meta.get_table_fields():
		if parenttype:
			if df.options == parenttype:
				return self.get(df.fieldname)

		value = getattr(self, df.fieldname, None)

		if isinstance(value, list):
			ret.extend(value)

	return ret

def get_powerflow(self):
	powerflow_status = Powerflow.get_workflow(self)
	if powerflow_status:
		return Powerflow(powerflow_status=powerflow_status)

def initialize_workflow(self):
	try:
		powerflow_status = frappe.get_doc({
			'doctype': "Powerflow Status",
			'ref_doctype': self.doctype,
			'ref_docname': self.name
		})
		powerflow = Powerflow(powerflow_status= powerflow_status)
		powerflow.start(self)
	except PowerflowNotFoundException:
		pass

def update_docstatus(self, docstatus):
	if self.docstatus != docstatus:
		self.docstatus = docstatus
		self.save(ignore_permissions=True)

def update_status(self, status, status_field_name="status"):
	self.db_set(status_field_name, status)
	self.run_method("on_status_change")

def attach_print(self, print_format, no_letterhead=1):
	return upload_from_data(
		self.doctype,
		self.name,
		is_private=1,
		file_name=f'{self.name}.pdf',
		filedata=get_pdf_data(self.doctype, [self.name], print_format, no_letterhead=no_letterhead)
	)

def patched_set_new_name(self, force=False):
	"""Calls `frappe.naming.se_new_name` for parent and child docs."""
	if self.flags.name_set and not force:
		return

	if self.meta.autoname != "auto_increment":
		set_new_name(self)
	else:
		self.name = '0'

	# set name for children
	for d in self.get_all_children():
		set_new_name(d)

	self.flags.name_set = True

def get_doc_before_save(self, raise_error=False):
	if not self.name:
		return

	if not getattr(self, '_doc_before_save', None):
		try:
			self._doc_before_save = frappe.get_doc(self.doctype, self.name, __for_update=True)
		except frappe.DoesNotExistError:
			if raise_error:
				raise

			self._doc_before_save = None
			frappe.clear_last_message()

	return self._doc_before_save

def submit(self):
	self.run_method("attach_workflow")
	if self.flags.ignore_submit:
		return
	else:
		self._submit()

def check_if_latest(self):
	"""Checks if `modified` timestamp provided by document being updated is same as the
	`modified` timestamp in the database. If there is a different, the document has been
	updated in the database after the current copy was read. Will throw an error if
	timestamps don't match.

	Will also validate document transitions (Save > Submit > Cancel) calling
	`self.check_docstatus_transition`."""
	conflict = False
	self._action = "save"
	if not self.get('__islocal'):
		if self.meta.issingle:
			modified = frappe.db.sql('''select value from tabSingles
				where doctype=%s and field='modified' for update nowait''', self.doctype)
			modified = modified and modified[0][0]
			if modified and modified != cstr(self._original_modified):
				conflict = True
		else:
			try:
				tmp = frappe.db.sql(f"""select modified, docstatus from `tab{self.doctype}`
					where name = %s for update nowait""", self.name, as_dict=True)
			except OperationalError as e:
				if e.args[0] == 1205:
					frappe.throw(f'Another transaction is trying to save "{self.doctype}" "{self.name}". Kindly retry after some time.')
				raise

			if not tmp:
				frappe.throw("Record does not exist")
			else:
				tmp = tmp[0]

			modified = cstr(tmp.modified)

			if modified and modified != cstr(self._original_modified):
				conflict = True

			self.check_docstatus_transition(tmp.docstatus)

		if conflict:
			frappe.msgprint(f"Error: Document has been modified after you have opened it \
				({modified}, {self.modified}) \
				Please refresh to get the latest document.",
				raise_exception=frappe.TimestampMismatchError
			)
	else:
		self.check_docstatus_transition(0)

def load_from_db(self, for_update=False):
	"""Load document and children from database and create properties
	from fields"""
	wait_on_locks = local.conf.wait_on_locks
	if not getattr(self, "_metaclass", False) and self.meta.issingle:
		single_doc = local.db.get_singles_dict(self.doctype)
		if not single_doc:
			single_doc = frappe.new_doc(self.doctype).as_dict()
			single_doc["name"] = self.doctype
			del single_doc["__islocal"]

		super(Document, self).__init__(single_doc)
		self.init_valid_columns()
		self._fix_numeric_types()

	else:
		d = frappe.db.sql(f'''
			select
				dt.*,
				cast(name as char) as name
			from
				`tab{self.doctype}` dt
			where
				name = %(name)s
			{
				f"for update {'' if wait_on_locks else 'nowait'}"
				if for_update else ""
			}
		''', {
			'name': self.name,
		}, as_dict=True)
		if not d:
			frappe.throw(f"{self.doctype} {self.name} not found", frappe.DoesNotExistError)

		super(Document, self).__init__(d[0])

	if self.name=="DocType" and self.doctype=="DocType":
		from frappe.model.meta import doctype_table_fields
		table_fields = doctype_table_fields
	else:
		table_fields = self.meta.get_table_fields()

	for df in table_fields:
		children = local.db.sql(f'''
			select
				dt.*,
				cast(name as char) as name
			from
				`tab{df.options}` dt
			where
				parent = %(parent)s
				and parenttype = %(parenttype)s
				and parentfield = %(parentfield)s
			order by idx
			{
				f"for update {'' if wait_on_locks else 'nowait'}"
				if for_update else ""
			}
		''', {
			"parent": f"{self.name}",
			"parenttype": self.doctype,
			"parentfield": df.fieldname,
		}, as_dict=True)
		if children:
			self.set(df.fieldname, children)
		else:
			self.set(df.fieldname, [])

	# sometimes __setup__ can depend on child values, hence calling again at the end
	if hasattr(self, "__setup__"):
		self.__setup__()

def __init__(self, *args, __for_update=False, **kwargs):
	"""Constructor.

	:param arg1: DocType name as string or document **dict**
	:param arg2: Document name, if `arg1` is DocType name.

	If DocType name and document name are passed, the object will load
	all values (including child documents) from the database.
	"""
	self.doctype = self.name = None
	self._default_new_docs = {}
	self.flags = frappe._dict()

	if args and args[0] and isinstance(args[0], str):
		# first arugment is doctype
		if len(args)==1:
			# single
			self.doctype = self.name = args[0]
		else:
			self.doctype = args[0]
			if isinstance(args[1], dict):
				# filter
				self.name = frappe.db.get_value(args[0], args[1], "name")
				if self.name is None:
					frappe.throw(f"{args[0]} {args[1]} not found", frappe.DoesNotExistError)
			else:
				self.name = args[1]

		self.load_from_db(for_update=__for_update)
		return

	if args and args[0] and isinstance(args[0], dict):
		# first argument is a dict
		kwargs = args[0]

	if kwargs:
		# init base document
		super(Document, self).__init__(kwargs)
		self.init_valid_columns()

	else:
		# incorrect arguments. let's not proceed.
		raise ValueError('Illegal arguments')

old_notify_update = Document.notify_update

@cache_in_mem(timeout=360)
def get_no_updates_for():
	try:
		return {
			row.disabled_doctype for row in
			frappe.get_cached_doc('SocketIO Settings').disable_list_updates_for
		}
	except Exception as e:
		return set()

def notify_update(self):
	if local.conf.dont_notify_doc_updates:
		return

	if self.doctype not in get_no_updates_for():
		old_notify_update(self)

@property
def meta(self):
	if not (retval_meta := getattr(self, '_meta', None)):
		retval_meta = self._meta = frappe.get_meta(self.doctype)
	return retval_meta

def __getstate__(self):
	self._meta = None
	return self.__dict__

def _set_defaults(self):
	if frappe.flags.in_import:
		return

	self.update_if_missing(self.meta.get_new_doc_defaults())

	# children
	for df in self.meta.get_table_fields():
		if (value := self.get(df.fieldname)) and isinstance(value, list):
			new_doc = frappe.get_meta(df.options).get_new_doc_defaults()
			for d in value:
				d.update_if_missing(new_doc)

Document.meta = meta
Document._set_defaults = _set_defaults
Document.__getstate__ = __getstate__
Document.notify_update = notify_update
Document.__init__ = __init__
Document.load_from_db = load_from_db
Document.run_before_save_methods = run_before_save_methods
Document.run_post_save_methods = run_post_save_methods
Document.validate_regex_pattern = validate_regex_pattern
Document.copy_attachments_from_amended_from = copy_attachments_from_amended_from
Document._validate_links = _validate_links
Document.update_status = update_status
Document.get_doc_before_save = get_doc_before_save
Document.set_new_name = patched_set_new_name
Document.attach_print = attach_print
Document.get_workflow = get_powerflow
Document.initialize_workflow = initialize_workflow
Document.update_docstatus = update_docstatus
Document.get_all_children = get_all_children
from latte.model.hook_registry import run_method
Document.run_method = run_method
Document.check_if_latest = check_if_latest
Document.run_trigger = run_method
frappe.model.document.get_controller = get_controller
frappe.model.base_document.get_controller = get_controller
Document.cancel = cancel
Document.submit = submit
