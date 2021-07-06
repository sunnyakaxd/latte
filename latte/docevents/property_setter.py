def on_update(doc, event=None):
	from latte.utils.caching import flushall, invalidate
	flushall()
	invalidate(f'meta|{doc.doc_type}')
