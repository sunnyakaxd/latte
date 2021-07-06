import frappe
from six import string_types
from frappe.model.db_query import DatabaseQuery
from frappe.model.db_query import (
	get_filter,
	get_datetime,
	get_time,
	getdate,
	datetime,
	flt,
	string_types,
	add_to_date,
	cint,
	copy,
	json
)

@frappe.whitelist()
def get_list(doctype, *args, data=None, **kwargs):
	'''wrapper for DatabaseQuery'''
	kwargs.pop('cmd', None)
	kwargs.pop('ignore_permissions', None)
	parent = kwargs.pop('parent', None)

	# If doctype is child table
	if 0 and frappe.is_table(doctype):
		frappe.flags.error_message = 'Cannot get list by child table'
		raise frappe.PermissionError(doctype)

	return PatchedDatabaseQuery(doctype).execute(None, *args, **kwargs)

old_prepare_filter_condition = DatabaseQuery.prepare_filter_condition

class PatchedDatabaseQuery(DatabaseQuery):
	def build_and_run(self):
		self.build_query()
		return self.run()

	def run(self, query=None):
		self.__result = frappe.db.sql(
			query or self.__query,
			self.ctx,
			as_dict=not self.as_list,
			debug=self.debug,
			update=self.update,
		)
		return self.__result

	def post_process(self):
		if self.with_comment_count and not self.as_list and self.doctype:
			self.add_comment_count(self.__result)

		if self.save_user_settings:
			self.update_user_settings()

	def build_query(self):
		self.ctx = {}
		args = self.prepare_args()
		args.limit = self.add_limit()

		if args.conditions:
			args.conditions = "where " + args.conditions

		if self.distinct:
			args.fields = 'distinct ' + args.fields
		self.__query = """select %(fields)s from %(tables)s %(conditions)s
			%(group_by)s %(order_by)s %(limit)s""" % args
		return self.__query

	def initialise(self, query=None, fields=None, filters=None, or_filters=None,
		docstatus=None, group_by=None, order_by=None, limit_start=False,
		limit_page_length=None, as_list=False, with_childnames=False, debug=False,
		ignore_permissions=False, user=None, with_comment_count=False,
		join='left join', distinct=False, start=None, page_length=None, limit=None,
		ignore_ifnull=False, save_user_settings=False, save_user_settings_fields=False,
		update=None, add_total_row=None, user_settings=None, reference_doctype=None, strict=None):
		if not ignore_permissions and not frappe.has_permission(self.doctype, "read", user=user):
			frappe.flags.error_message = f'Insufficient Permission for {frappe.bold(self.doctype)}'
			raise frappe.PermissionError(self.doctype)

		# filters and fields swappable
		# its hard to remember what comes first
		if (isinstance(fields, dict)
			or (isinstance(fields, list) and fields and isinstance(fields[0], list))):
			# if fields is given as dict/list of list, its probably filters
			filters, fields = fields, filters

		elif fields and isinstance(filters, list) \
			and len(filters) > 1 and isinstance(filters[0], string_types):
			# if `filters` is a list of strings, its probably fields
			filters, fields = fields, filters

		if fields:
			self.fields = fields
		else:
			self.fields =  ["`tab{0}`.`name`".format(self.doctype)]

		if start: limit_start = start
		if page_length: limit_page_length = page_length
		if limit: limit_page_length = limit

		self.query = query
		self.filters = filters or []
		self.or_filters = or_filters or []
		self.docstatus = docstatus or []
		self.group_by = group_by
		self.order_by = order_by
		self.limit_start = 0 if (limit_start is False) else cint(limit_start)
		self.limit_page_length = cint(limit_page_length) if limit_page_length else None
		self.with_childnames = with_childnames
		self.debug = debug
		self.join = join
		self.distinct = distinct
		self.as_list = as_list
		self.ignore_ifnull = ignore_ifnull
		self.flags.ignore_permissions = ignore_permissions
		self.user = user or frappe.session.user
		self.update = update
		self.user_settings_fields = copy.deepcopy(self.fields)
		self.with_comment_count = with_comment_count
		self.save_user_settings = save_user_settings
		self.save_user_settings_fields = save_user_settings_fields
		self.strict = strict
		# for contextual user permission check
		# to determine which user permission is applicable on link field of specific doctype
		self.reference_doctype = reference_doctype or self.doctype

		if user_settings:
			self.user_settings = json.loads(user_settings)

	def prepare_filter_condition(self, f):
		"""Returns a filter condition in the format:

				ifnull(`tabDocType`.`fieldname`, fallback) operator "value"
		"""

		if getattr(self, 'ctx', None) is None:
			return old_prepare_filter_condition(self, f)

		f = get_filter(self.doctype, f)

		tname = f'`tab{f.doctype}`'
		if not tname in self.tables:
			self.append_table(tname)

		if 'ifnull(' in f.fieldname:
			column_name = f.fieldname
		else:
			column_name = f'{tname}.{f.fieldname}'

		value_holder = f'__ctx_value_{len(self.ctx)}'
		value = None

		# prepare in condition
		if f.operator.lower() in ('ancestors of', 'descendants of', 'not ancestors of', 'not descendants of'):

			# TODO: handle list and tuple
			# if not isinstance(values, (list, tuple)):
			# 	values = values.split(",")

			ref_doctype = f.doctype

			if frappe.get_meta(f.doctype).get_field(f.fieldname) is not None :
				ref_doctype = frappe.get_meta(f.doctype).get_field(f.fieldname).options

			try:
				lft, rgt = frappe.db.get_value(ref_doctype, f.value, ["lft", "rgt"])
			except TypeError:
				lft, rgt = None, None

			# Get descendants elements of a DocType with a tree structure
			if lft and rgt and f.operator.lower() in ('descendants of', 'not descendants of') :
				value = frappe.db.sql_list(f"""select name from `tab{ref_doctype}`
					where lft >= %s and rgt <= %s order by lft asc""", (lft, rgt))
			elif lft and rgt:
				# Get ancestor elements of a DocType with a tree structure
				value = frappe.db.sql_list(f"""select name from `tab{ref_doctype}`
					where lft <= %s and rgt >= %s order by lft desc""", (lft, rgt))

			if not value:
				value = ['____NONE____']

			# changing operator to IN as the above code fetches all the parent / child values and convert into tuple
			# which can be directly used with IN operator to query.
			f.operator = 'not in' if f.operator.lower() in ('not ancestors of', 'not descendants of') else 'in'

		elif f.operator.lower() in ('in', 'not in'):
			value = f.value or ''
			if isinstance(value, (list, tuple)):
				pass # Most used, to ignore below comparisons
			if isinstance(value, string_types):
				value = value.split(",")
			elif isinstance(value, map):
				value = list(value)

		else:
			df = frappe.get_meta(f.doctype).get_field(f.fieldname)

			if f.operator.lower() == 'between' and \
				(f.fieldname in ('creation', 'modified') or (df and (df.fieldtype=="Date" or df.fieldtype=="Datetime"))):

				from_date, to_date = get_between_date_filter(f.value, df)
				from_date_value_holder = f'__ctx_value_{len(self.ctx)}'
				to_date_value_holder = f'__ctx_value_{len(self.ctx)+1}'
				self.ctx[from_date_value_holder] = from_date
				self.ctx[to_date_value_holder] = to_date

				return f'{column_name} between %({from_date_value_holder})s and %({to_date_value_holder})s'

			elif df and df.fieldtype=="Date":
				value = getdate(f.value).strftime("%Y-%m-%d")

			elif (df and df.fieldtype=="Datetime") or isinstance(f.value, datetime):
				value = get_datetime(f.value).strftime("%Y-%m-%d %H:%M:%S.%f")

			elif df and df.fieldtype=="Time":
				value = get_time(f.value).strftime("%H:%M:%S.%f")

			elif f.operator.lower() == "is":
				if f.value == 'set':
					f.operator = '!='
				elif f.value == 'not set':
					f.operator = '='

				value = ""

			elif f.operator.lower() in ("like", "not like") or (isinstance(f.value, string_types) and
				(not df or df.fieldtype not in ["Float", "Int", "Currency", "Percent", "Check"])):
					value = "" if f.value==None else f.value

					if f.operator.lower() in ("like", "not like") and isinstance(value, string_types):
						# because "like" uses backslash (\) for escaping
						value = value.replace("\\", "\\\\").replace("%", "%%")
			else:
				value =  flt(f.value) if f.value else ""

		self.ctx[value_holder] = value
		condition = f'{column_name} {f.operator} %({value_holder})s'

		return condition

def get_between_date_filter(value, df=None):
	'''
		return the formattted date as per the given example
		[u'2017-11-01', u'2017-11-03'] => '2017-11-01 00:00:00.000000' AND '2017-11-04 00:00:00.000000'
	'''
	from_date = None
	to_date = None
	date_format = "%Y-%m-%d %H:%M:%S.%f"

	if df:
		date_format = "%Y-%m-%d %H:%M:%S.%f" if df.fieldtype == 'Datetime' else "%Y-%m-%d"

	if value and isinstance(value, (list, tuple)):
		if len(value) >= 1: from_date = value[0]
		if len(value) >= 2: to_date = value[1]

	if not df or (df and df.fieldtype == 'Datetime'):
		to_date = add_to_date(to_date, days=1)

	return get_datetime(from_date).strftime(date_format), get_datetime(to_date).strftime(date_format)
