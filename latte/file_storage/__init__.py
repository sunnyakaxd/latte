import frappe
from werkzeug.wrappers import Response
from latte.file_storage.doctype.storage_adapter_settings.storage_adapter_settings import StorageAdapterSettings
# from latte.file_storage.doctype.attachment.attachment import has_download_permission
from latte.json import dumps
from mimetypes import guess_type, add_type as add_mime_type
from urllib.parse import unquote_plus
add_mime_type('text/plain', '.conf')

@frappe.whitelist(allow_guest=True)
def get_proxy_meta():
	# TODO
	# password azure key,
	# every adapter except for file should be enabled in site config
	# check upload limit
	# Doctype in meta data azure
	# cluster id in tags

	is_local_request = frappe.local.request.headers.get('X-Request-Is-Local') or ""
	if not is_local_request.strip():
		frappe.throw('Not Allowed/Not Available', frappe.PermissionError)

	path = unquote_plus(frappe.local.request.headers.get('X-Request-Uri'))
	attachment = frappe.db.get_value('File', filters={
		'file_url': path,
	}, fieldname=[
		'adapter_type', 'adapter_id', 'file_name', 'is_private',
		'attached_to_doctype', 'attached_to_name'
	], as_dict=True)
	if not attachment:
		frappe.throw('Not Allowed/Not Available', frappe.PermissionError)
	if attachment.is_private:
		from latte.file_storage.file import has_download_permission
		has_download_permission(attachment.attached_to_doctype, attachment.attached_to_name)
	adapter = StorageAdapterSettings.get_adapter_by_name(attachment.adapter_type)
	metadata = adapter.get_proxy_meta(attachment.adapter_id)
	response_headers = metadata['response_headers'] = metadata.get('response_headers') or {}
	response_headers['Content-Disposition'] = f'inline; filename="{attachment.file_name}"'
	response_headers['Content-Type'] = guess_type(attachment.file_name)[0]
	response = Response()
	response.mimetype = 'application/json'
	response.charset = 'utf-8'
	response.data = dumps(metadata)

	return response
