
def on_update(doc, event=None):
	from latte.latte_core.naming.auto_increment import migrate_doc
	migrate_doc(doc)
	from latte.utils.caching import flushall, invalidate
	flushall()
	invalidate(f'meta|{doc.name}')
