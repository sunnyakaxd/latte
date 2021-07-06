import frappe
from frappe.utils import cint, flt
from frappe.model.db_schema import (
	DbTable, DbColumn, default_shortcuts,
	get_definition, type_map, varchar_len, standard_varchar_columns
)
from latte.utils.indexing import create_index
from frappe import local
from pymysql.err import InternalError, OperationalError
from pymysql.constants import ER
import re

def alter(self):
	for col in self.columns.values():
		col.build_for_alter_table(self.current_columns.get(col.fieldname.lower(), None))

	query = []

	for col in self.change_type:
		current_def = self.current_columns.get(col.fieldname.lower(), None)
		query.append(f"change `{current_def['name']}` `{col.fieldname}` {col.get_definition()}")

	if self.set_default:
		self.col_map = {
			row.Field: row for row in local.db.sql(f'desc `{self.name}`', as_dict=True)
		}

	for col in self.set_default:
		db_col = self.col_map[col.fieldname]
		if col.fieldname=="name":
			continue

		convertor = None
		if col.fieldtype in ("Check", "Int"):
			col_default = cint(col.default)
			convertor = cint

		elif col.fieldtype in ("Currency", "Float", "Percent"):
			col_default = flt(col.default)
			convertor = flt

		elif not col.default:
			if col.fieldtype in ('Data', 'Select', 'Link', 'Dynamic Link', 'Read Only', 'Color'):
				col_default = "''"
			else:
				col_default = "null"
			convertor = str

		else:
			col_default = "'{}'".format(col.default.replace("'", "\\'"))
			convertor = str

		if db_col.Default is None:
			db_col.Default = 'null'
		elif db_col.Default == '':
			db_col.Default = "''"

		if convertor and db_col.Default:
			db_col.Default = convertor(db_col.Default)

		if db_col.Default != col_default:
			print(
				col.fieldname,
				f'"{db_col.Default}"',
				type(db_col.Default),
				f'"{col_default}"',
				type(col_default),
				db_col.Default != col_default
			)
			query.append(f'alter column `{col.fieldname}` set default {col_default}')

	for col in self.add_column:
		query.append(f"add column `{col.fieldname}` {col.get_definition()}")

	if query:
		print(f"alter table `{self.name}` {', '.join(query)}")
		local.db.sql(f"alter table `{self.name}` {', '.join(query)}")

	for col in self.add_index:
		create_index(self.name, col.fieldname)

DbTable.alter = alter

def patched_get_definition(self, with_default=1):
	column_def = get_definition(self.fieldtype, precision=self.precision, length=self.length)

	if not column_def:
		return column_def

	if self.fieldtype in ("Check", "Int"):
		default_value = cint(self.default) or 0
		column_def += ' not null default {0}'.format(default_value)

	elif self.fieldtype in ("Currency", "Float", "Percent"):
		default_value = flt(self.default) or 0
		column_def += ' not null default {0}'.format(default_value)

	elif self.fieldtype in ('Date', 'Datetime'):
		if str(self.default).lower() == 'today':
			default = 'CURRENT_DATE'
		elif str(self.default).lower() == "now":
			default = 'CURRENT_TIMESTAMP'
		elif self.default:
			default = f'"{self.default}"'
		else:
			default = 'null'
		column_def += f' default {default}'
	elif self.fieldtype in ('Time'):
		if self.default:
			default = f'"{self.default}"'
		else:
			default = 'null'
		column_def += f' default {default}'

	elif (
		self.default is not None
		and (self.default not in default_shortcuts)
		and (not self.default.startswith(":"))
		and (column_def not in ('text', 'longtext'))
	):
		column_def += f' default "' + self.default.replace('"', '\"') + '"'

	if self.unique and (column_def not in ('text', 'longtext')):
		column_def += ' unique'

	return column_def

DbColumn.get_definition = patched_get_definition

def create(self):
	add_text = ''

	# columns
	column_defs = self.get_column_definitions()
	if column_defs: add_text += ',\n'.join(column_defs) + ',\n'

	# index
	index_defs = self.get_index_definitions()
	if index_defs: add_text += ',\n'.join(index_defs) + ',\n'

	# create table
	creation_query = f"""create table `{self.name}` (
		name varchar({varchar_len}) not null primary key,
		creation datetime(6),
		modified datetime(6),
		modified_by varchar({varchar_len}),
		owner varchar({varchar_len}),
		docstatus int(1) not null default '0',
		parent varchar({varchar_len}),
		parentfield varchar({varchar_len}),
		parenttype varchar({varchar_len}),
		idx int(8) not null default '0',
		{add_text}
		index parent(parent),
		index modified(modified))
		ENGINE={self.meta.get("engine") or 'InnoDB'}
		ROW_FORMAT=COMPRESSED
		CHARACTER SET=utf8mb4
		COLLATE=utf8mb4_unicode_ci
	"""

	local.db.sql(creation_query)

DbTable.create = create

def validate(self):
	"""Check if change in varchar length isn't truncating the columns"""
	if self.is_new():
		return

	self.get_columns_from_db()

	columns = [frappe._dict({"fieldname": f, "fieldtype": "Data"}) for f in standard_varchar_columns]
	columns += self.columns.values()

	for col in columns:
		if len(col.fieldname) >= 64:
			frappe.throw(f"Fieldname is limited to 64 characters ({frappe.bold(col.fieldname)})")

		if col.fieldtype in type_map and type_map[col.fieldtype][0]=="varchar":

			# validate length range
			new_length = cint(col.length) or cint(varchar_len)
			if not (1 <= new_length <= 1000):
				frappe.throw(f"Length of {col.fieldname} should be between 1 and 1000")

			if not frappe.local.conf.reduce_varchar_on_migration:
				continue

			current_col = self.current_columns.get(col.fieldname, {})
			if not current_col:
				continue
			current_type = self.current_columns[col.fieldname]["type"]
			current_length = re.findall('varchar\(([\d]+)\)', current_type)
			if not current_length:
				# case when the field is no longer a varchar
				continue
			current_length = current_length[0]
			if cint(current_length) > cint(new_length):
				try:
					# check for truncation
					max_length = frappe.db.sql("""select max(char_length(`{fieldname}`)) from `tab{doctype}`"""\
						.format(fieldname=col.fieldname, doctype=self.doctype))

				except (InternalError, OperationalError) as e:
					if e.args[0] == ER.BAD_FIELD_ERROR:
						# Unknown column 'column_name' in 'field list'
						continue

					else:
						raise

				if max_length and max_length[0][0] and max_length[0][0] > new_length:
					if col.fieldname in self.columns:
						self.columns[col.fieldname].length = current_length

					frappe.msgprint(f"""
						Reverting length to {current_length}
						for '{col.fieldname}' in '{self.doctype}';
						Setting the length as {new_length} will cause truncation of data.
					""")

DbTable.validate = validate

type_map.update({
	'LinkMultiSelect': ('varchar', varchar_len),
	'Float10': ('decimal', '22,10'),
})
