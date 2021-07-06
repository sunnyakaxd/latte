from frappe import local
from frappe.website import router

old_sync = router.sync_global_search

def sync_global_search():
	if not local.conf.enable_global_search:
		return

	return old_sync()

router.sync_global_search = sync_global_search