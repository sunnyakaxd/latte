import frappe
from frappe import local
from frappe.utils import nestedset
import random

def patched_update_add_node(doc, parent, parent_field):
	print('Parent=', parent, not not parent)
	if not parent:
		parent_lft = frappe.db.sql(f'''
			select
				rgt
			from
				`tab{doc.doctype}`
			where
				name != %(name)s
			order by
				rgt desc
			limit 1
		''', {
			'name': doc.name,
		})
		if parent_lft:
			parent_lft = parent_lft[0][0]
		else:
			parent_lft = -10.0**12

		parent_rgt = 10.0**12
	else:
		parent_lft, parent_rgt = frappe.db.get_value(doc.doctype, parent, ['lft', 'rgt'])

	add_child(doc.doctype, doc.name, parent_lft, parent_rgt)

def patched_update_move_node(doc, parent_field):
	'''
		is called when op!=p
		so just add_child under p with doc's details
	'''
	parent_rgt = frappe.db.get_value(doc.doctype, doc.get(parent_field), 'rgt')
	tree_lft = local.db.sql(f'''
		select
			rgt
		from
			`tab{doc.doctype}`
		where
			rgt < %(parent_rgt)s
		order by
			rgt desc
		limit
			1
	''', {
		'parent_rgt': parent_rgt,
	})[0][0]

	add_child(doc.doctype, doc.name, tree_lft, parent_rgt)


# called in the on_update method
def update_nsm(doc):
	# get fields, data from the DocType
	opf = 'old_parent'
	pf = "parent_" + frappe.scrub(doc.doctype)

	if hasattr(doc,'nsm_parent_field'):
		pf = doc.nsm_parent_field
	if hasattr(doc,'nsm_oldparent_field'):
		opf = doc.nsm_oldparent_field

	p, op = doc.get(pf) or None, doc.get(opf) or None

	# has parent changed (?) or parent is None (root)
	if not doc.lft and not doc.rgt:
		patched_update_add_node(doc, p or '', pf)
	elif op != p:
		patched_update_move_node(doc, pf)

	# set old parent
	doc.set(opf, p)
	frappe.db.set_value(doc.doctype, doc.name, opf, p or '', update_modified=False)

	doc.reload()


def add_child(doctype, docname, left, right):
	print('add_child running for', doctype, docname, left, right)
	PRECISION = -9

	safe_left = left + 10**PRECISION
	safe_right = right - 10**PRECISION

	lft = _getsafeval(safe_left, safe_right, retry=True)
	rgt = _getsafeval(lft, safe_right, retry=True)

	frappe.log_error(f'''{doctype=} {docname=} {left=} {right=} {lft=} {rgt=}''', title=f'Add child for {doctype}')
	if lft == rgt:
		frappe.throw(f'''INVALID VALUES FOR {lft=} {rgt=}''')

	frappe.db.sql(f"""
		update
			`tab{doctype}`
		set
			lft = %(lft)s
			, rgt = %(rgt)s
		where
			name = %(docname)s
	""", {
		'lft': lft,
		'rgt': rgt,
		'docname': docname,
	}, debug=1)

	for descendent in get_immediate_descendents(doctype, docname):
		add_child(doctype, descendent.name, lft, rgt)

def get_immediate_descendents(doctype, docname):
	return frappe.get_all(doctype, filters={
		f'parent_{frappe.scrub(doctype)}': docname
	})

def _getsafeval(left, right, retry=False):
	'''
		Returns a mid value in the given range
		param retry:
		-----------
		default: False. if set to true, ensures that mid value does not equal left/right
	'''
	PRECISION = -9
	inf_loop_safe_counter = 4

	if retry:
		while inf_loop_safe_counter > 0:
			inf_loop_safe_counter -= 1

			mid = random.uniform(left, right)
			if mid == left or mid == right:
				safe_left = left + 10**PRECISION
				safe_right = right - 10**PRECISION
				return _getsafeval(safe_left, safe_right)
			else:
				return mid

	return random.uniform(left, right)

def rebuild_node(doctype, parent, left, parent_field):
	"""
		reset lft, rgt and recursive call for all children
	"""
	# the right value of this node is the left value + 1
	right = left+1

	# get all children of this node
	result = local.db.sql(f"SELECT name FROM `tab{doctype}` WHERE `{parent_field}`=%s", (parent))
	for r in result:
		right = rebuild_node(doctype, r[0], right, parent_field)

	# we've got the left value, and now that we've processed
	# the children of this node we also know the right value
	local.db.sql(f"""
		UPDATE `tab{doctype}`
		SET
			lft=%s,
			rgt=%s
		WHERE
			name=%s
	""", (left, right, parent))

	#return the right value of this node + 1
	return right+1

# nestedset.update_move_node = patched_update_move_node
# nestedset.update_nsm = update_nsm
# nestedset.update_add_node = patched_update_add_node
# nestedset.rebuild_node = rebuild_node
