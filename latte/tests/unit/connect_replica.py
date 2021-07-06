import frappe
from latte import read_only

def test_me():
	print('Initial', frappe.db.host, frappe.db.port)
	test_read_only()
	print('Final', frappe.db.host, frappe.db.port)

	print('Testing Priority')
	test_read_only_priority_high()
	test_read_only_priority_low()

@read_only()
def test_read_only(level=0):
	if level > 10:
		return

	print(f'Level {level}, Before', frappe.db.host, frappe.db.port)
	test_read_only(level + 1)
	print(f'Level {level}, After', frappe.db.host, frappe.db.port)

@read_only(replica_priority=0)
def test_read_only_priority_high():
	print(f'High priority Db name', frappe.db.host, frappe.db.port)

@read_only(replica_priority=1)
def test_read_only_priority_low():
	print(f'Low priority Db name', frappe.db.host, frappe.db.port)
