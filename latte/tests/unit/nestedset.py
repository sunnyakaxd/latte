import frappe

def test():
	tree = {
		'MH': {
			'Pune': {
				'Chinchwad': {
					'Vishal Nagar': {},
					'Wakad': {},
				},
			},
			'Viman Nagar': {
				'Phoenix': {},
				'AFS': {},
			}
		}
	}
	test_add_node('MH', tree['MH'], '')

def test_add_node(key, node, parent):
	print('Adding', key)
	doc = frappe.get_doc({
		'doctype': 'Test Tree',
		'parent_test_tree': parent,
		'node_name': key,
		'is_group': 1,
	}).insert(ignore_permissions=True)
	doc = frappe.get_doc('Test Tree', doc.name)
	print(doc.lft, doc.rgt)

	for child, value in node.items():
		test_add_node(child, value, key)

'''
	things to test
		create a tree doctype
		Insertion:
			- add a new node as an independent root
			- add a new node under another node
		Moving:
			- move a node from different node

	Assertions:
		check children
			- After moving under new node
			- After adding new node
		check parents
			- After moving under new node
			- After adding new node
		ways to check:
			check children using parentfield matching
			check children using lft rgt range
			both should match
'''

def get_descendants_parentfield(doctype, docnames):
	'''
		Returns children with parentfield as docname in doctype
		doctype: String
		docnames: Tuple
	'''

	childs = frappe.get_all(doctype, {
		f'parent_{frappe.scrub(doctype)}': ('in', docnames)
	}, ['name', 'is_group'])

	if not childs:
		return docnames

	return get_descendants_parentfield(doctype, tuple(child.name for child in childs)) + docnames

def get_descendants_index(doctype, docname):
	lft, rgt = frappe.db.get_value(doctype, docname, ('lft', 'rgt'))
	if lft and rgt:
		return frappe.db.sql_list(f'''
			select
				name
			from
				`tab{doctype}`
			where
				lft between %(lft)s and %(rgt)s
		''', {
			'lft': lft,
			'rgt': rgt
		})

	return []

def compare_descendants(doctype, docname):
	'''
		Returns True if descendants using lft match those using parentfield approach
	'''
	pf_descendants = sorted(list(get_descendants_parentfield(doctype, (docname,))))
	index_descendants = sorted(get_descendants_index(doctype, docname))

	if pf_descendants == index_descendants:
		return True

	print(pf_descendants, '\n', index_descendants)
	return False