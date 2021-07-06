import frappe
from frappe import local
from latte.utils.caching import cache_me_if_you_can, invalidate, flushall
from uuid import uuid4

def execute():
	test_get_cached_doc()
	test_caching()
	test_invalidation()

def test_get_cached_doc():
	# load cache
	flushall()
	print('Testing get cached doc')
	frappe.get_cached_doc('System Settings')
	new_doc = frappe.get_doc('System Settings')
	new_doc.save()
	frappe.db.commit()
	local.latte_cache.clear()
	cached_doc = frappe.get_cached_doc('System Settings')
	assert(cached_doc.modified == new_doc.modified)

@cache_me_if_you_can(key=lambda: 'test', expiry=100000)
def get_uuid():
	return str(uuid4())

def test_caching():
	flushall()
	print('testing simple caching')
	assert(get_uuid() == get_uuid())

def test_invalidation():
	flushall()
	print('testing invalidation')
	generated = get_uuid_with_invalidation()
	invalidate('caching_test')
	assert(get_uuid_with_invalidation() != generated)
	assert(get_uuid_with_invalidation() == get_uuid_with_invalidation())

@cache_me_if_you_can(key=lambda:'test', invalidate='caching_test', expiry=100000)
def get_uuid_with_invalidation():
	retval = str(uuid4())
	return retval
