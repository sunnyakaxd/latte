import frappe
from latte.model.document import get_controller
from frappe.utils.nestedset import NestedSet

def do_nothing(*_, **__):
	pass

def update_types():
	for doctype in get_nested_doctypes():
		print('Updating field type for', doctype)
		update_field_types(doctype)

def update_field_types(doctype):
	''' Updates Float10 type for NestedSet Docs'''
	doc = frappe.get_doc('DocType', doctype)
	for field in doc.fields:
		if field.fieldname in ('lft', 'rgt'):
			field.fieldtype = 'Float10'
			field.db_update()
	doc.db_set('modified', frappe.utils.now_datetime())

def update_fieldtype(doc, event):
	try:
		_class = get_controller(doc.name, doc.module)
		if not issubclass(_class, NestedSet):
			return
	except (ModuleNotFoundError, AttributeError):
		return

	if (fields := [field for field in doc.fields if field.fieldname in ('lft', 'rgt')]):
		for field in fields:
			field._validate_selects = do_nothing
			field.fieldtype = 'Float10'

def rebuild_all_trees():
	from frappe.utils.nestedset import rebuild_tree

	for doctype in get_nested_doctypes():
		if is_tree_updated(doctype):
			rebuild_tree(doctype, f'parent_{frappe.scrub(doctype)}')
			frappe.db.commit()
			try:
				for method in frappe.get_hooks('on_tree_rebuild')[doctype]:
					frappe.get_attr(method)(doctype)
			except KeyError:
				frappe.log_error(f'{doctype} modified but not rebuilt', title='NestedSet rebuild skipped')

def is_tree_updated(tree_doctype):
	'''
		Returns True if a node has been updated/added in the tree
	'''
	return frappe.db.sql_list(f'''
		select
			1
		from
			`tab{tree_doctype}`
		where
			lft != cast(lft as int)
			or rgt != cast(rgt as int)
	''')

def get_nested_doctypes():
	''' Returns Tree type doctypes '''

	valid_doctypes = frappe.db.sql_list('''
	select
		df.parent
	from
		`tabDocField` df
	where
		df.fieldname = 'lft'
		or df.fieldname = 'rgt'
	''')

	nested_docs = []

	for doctype in valid_doctypes:
		try:
			_class = get_controller(doctype)
			if issubclass(_class,NestedSet):
				nested_docs.append(doctype)
		except ModuleNotFoundError:
			continue

	return nested_docs