import frappe
from frappe.model.document import Document
from frappe.utils import cint

from hashlib import md5
import pandas as pd
from PIL import Image
from latte.json import loads, dumps
from uuid import uuid4
from io import BytesIO
from base64 import b64decode
from latte.file_storage.doctype.storage_adapter_settings.storage_adapter_settings import StorageAdapterSettings
from latte.utils.printing import get_pdf_data

class File(Document):
	@staticmethod
	def get_all_attachments(dt, dn, fields=['name']):
		return frappe.get_all('File', filters={
			'attached_to_doctype': dt,
			'attached_to_name': dn,
		}, fields=fields)

	@staticmethod
	def get_doc(name):
		return frappe.get_doc('File', name)

	@staticmethod
	def copy_attachments_from(s_dt, s_dn, t_dt, t_dn):
		for afile in frappe.get_all('File', filters={
			'attached_to_doctype': s_dt,
			'attached_to_name': s_dn,
		}):
			file_doc = frappe.copy_doc(frappe.get_doc('File', afile.name))
			file_doc.attached_to_doctype = t_dt
			file_doc.attached_to_name = t_dn
			file_doc.thumbnail_attachment = None
			file_doc.insert(ignore_permissions=True)

	@staticmethod
	def attach_print(print_dt, print_dn, print_format, filename=None, attach_to_dt=None, attach_to_dn=None, is_private=1):
		if not filename:
			filename = str(uuid4()) + '.pdf'
		if not attach_to_dn:
			attach_to_dn = print_dn
		if not attach_to_dt:
			attach_to_dt = print_dt

		data = get_pdf_data(print_dt, [print_dn], print_format)
		return upload_from_data(attach_to_dt, attach_to_dn, is_private, filename, data)

	@staticmethod
	def find_by_file_url(file_url):
		doc_name = frappe.db.get_value('File', filters={
			'file_url': file_url,
		})
		return doc_name and frappe.get_doc('File', doc_name)

	@staticmethod
	def find_by_file_name(file_name):
		doc_name = frappe.db.get_value('File', filters={
			'file_name': file_name,
		})
		return doc_name and frappe.get_doc('File', doc_name)

	@staticmethod
	def attach_df_as_excel(dt, dn, df, file_name, is_private=True):
		with BytesIO() as stream:
			with pd.ExcelWriter(stream, engine='xlsxwriter') as writer:
				df.to_excel(writer)

			if not file_name.endswith('xlsx'):
				file_name = f'{file_name}.xlsx'

			return upload_from_data(dt, dn, is_private, file_name=file_name, filedata=stream.getvalue())

	def copy_to(self, dt, dn):
		file_doc = frappe.copy_doc(self)
		file_doc.attached_to_doctype = dt
		file_doc.attached_to_name = dn
		file_doc.thumbnail_attachment = None
		file_doc.insert(ignore_permissions=True)
		return file_doc

	def before_link_validation(self):
		self.folder = ''

	def before_save(self):
		if not (self.adapter_type and self.adapter_id):
			self.adapter_type = 'File'
			self.is_private = frappe.utils.cint(self.is_private)
			self.adapter_id = f"{'private' if self.is_private else 'public'}/files/{self.file_name}"
			self.file_url = f"/files/{self.file_name}"

	# def validate(self):
	# 	if not self.is_folder:
	# 		if not (self.content_hash and self.content_hash.strip()):
	# 			frappe.throw('Content hash is mandatory')

	def get_adapter(self):
		return StorageAdapterSettings.get_adapter_by_name(self.adapter_type)

	def get_data(self):
		dt_adapter = frappe.get_cached_doc('Storage Adapter Settings').get_adapter_by_name(self.adapter_type)
		return dt_adapter.get_data(self.adapter_id)

	def get_data_stream(self):
		dt_adapter = frappe.get_cached_doc('Storage Adapter Settings').get_adapter_by_name(self.adapter_type)
		return dt_adapter.get_data_stream(self.adapter_id)

	def make_thumbnail(self, set_as_thumbnail=True, width=300, height=300, crop=False):
		if self.thumbnail_url:
			thumbnail = self.thumbnail_attachment
			self.db_set('thumbnail_url', '')
			self.db_set('thumbnail_attachment', '')
			frappe.delete_doc('File', thumbnail, ignore_permissions=True)

		dt_adapter = frappe.get_cached_doc('Storage Adapter Settings').get_adapter_by_name(self.adapter_type)
		datastream = dt_adapter.get_data_stream(self.adapter_id)
		image = Image.open(datastream)
		image.thumbnail((width, height,), Image.ANTIALIAS)
		thumbnail_stream = BytesIO()
		new_filename = f'thumb_{self.file_name.rsplit(".", 1)[0]}.{image.format.lower()}'
		image.save(thumbnail_stream, format=image.format)
		try:
			thumbnail_doc = upload_from_data(
				doctype=self.attached_to_doctype,
				docname=self.attached_to_name,
				is_private=self.is_private,
				file_name=new_filename,
				filedata=thumbnail_stream.getvalue(),
			)
			self.db_set("thumbnail_url", thumbnail_doc.file_url)
			self.db_set("thumbnail_attachment", thumbnail_doc.name)
		finally:
			hasattr(datastream, 'close') and datastream.close()

		return self.thumbnail_url

	def remove_thumbnail(self):
		remove_thumbnail(self.name)

	def after_delete(self):
		frappe.db.run_after_commit(
			delete_file_from_adapter,
			attachment=self,
		)

@frappe.whitelist()
def make_thumbnail(name):
	frappe.get_doc('File', name).make_thumbnail()
	frappe.msgprint('Thumbnail Created')

@frappe.whitelist()
def remove_thumbnail(name):
	thumbnail = frappe.db.get_value('File', name, 'thumbnail_attachment')
	frappe.db.set_value('File', name, 'thumbnail_attachment', '')
	frappe.db.set_value('File', name, 'thumbnail_url', '')
	frappe.delete_doc(
		'File',
		thumbnail,
		ignore_permissions=True,
	)
	frappe.msgprint('Thumbnail Removed')

def remove_files(doc, _=None):
	remove_file_by_dt_dn(doc.doctype, doc.name)

def remove_file_by_dt_dn(dt, dn):
	for aFile in frappe.get_all('File', filters={
		'attached_to_doctype': dt,
		'attached_to_name': dn,
	}):
		frappe.delete_doc('File', aFile.name, ignore_permissions=True)

def delete_file_from_adapter(attachment):
	# Check if the same content hash or adapterID is referenced from another file attachment.
	files_with_adapter_id = frappe.get_all('File', filters={
			'adapter_type': attachment.adapter_type,
			'adapter_id': attachment.adapter_id,
			'file_size': ['>', 0],
		}, fields=[
			'name',
			'adapter_id',
			'adapter_type',
		])
	if not files_with_adapter_id:
		attachment.get_adapter().delete(attachment.adapter_id)

def get_files(dt, dn):
	return frappe.get_all('File', filters={
		'attached_to_doctype': dt,
		'attached_to_name': dn,
	}, fields=[
		'name',
		'file_name',
		'file_url',
		'is_private',
	])

@frappe.whitelist()
def uploadfile(doctype=None, docname=None, is_private=None, filename=None, filedata=None, _ignore_permissions=False, file_url=None):
	doctype = doctype or frappe.local.form_dict.get('doctype')
	docname = docname or frappe.local.form_dict.get('docname')
	is_private = is_private or frappe.local.form_dict.get('is_private')
	filename = filename or frappe.local.form_dict.get('filename')
	filedata = filedata or frappe.local.form_dict.get('filedata') or None
	fileurl = file_url or frappe.local.form_dict.get('file_url') or ''

	file_name = filename
	if not _ignore_permissions:
		has_upload_permission(doctype, docname)

	if filedata:
		if ',' in filedata:
			filedata = filedata.split(',')[1]

		filedata = b64decode(filedata)
		file_doc = upload_from_data(doctype, docname, is_private, file_name,filedata=filedata)

	else:
		import urllib.parse
		parsed = urllib.parse.urlparse(fileurl)
		file_doc = File.find_by_file_url(parsed.path)
		if file_doc:
			File.copy_attachments_from(file_doc.attached_to_doctype, file_doc.attached_to_name, doctype, docname)
		else:
			frappe.throw("Invalid url entered")

	return {
		"name": file_doc.name,
		"file_name": file_doc.file_name,
		"file_url": file_doc.file_url,
		"is_private": file_doc.is_private,
		"comment": file_doc.get('comment', ''),
	}

class DuplicateContentHashError(Exception):
	__slots__ = ['file_with_same_hash']
	def __init__(self, *args, file_with_same_hash=None, **kwargs):
		super().__init__(*args, **kwargs)
		self.file_with_same_hash = file_with_same_hash

def upload_from_file_path(doctype, docname, is_private, file_name, file_path):
	with open(file_path) as f:
		return upload_from_data(doctype, docname, is_private, file_name, datastream=f)

def upload_from_data(doctype, docname, is_private, file_name, filedata=None, datastream=None):
	if (filedata is None and datastream is None):
		frappe.throw('One of filedata/datastream is mandatory')

	is_private = cint(is_private)

	content_hash = None
	data_length = 0
	file_with_same_hash = None
	unique_adapter_file_id = None
	dt_adapter = frappe.get_cached_doc('Storage Adapter Settings').get_adapter_for_dt(doctype)
	try:
		if filedata is not None:
			content_hash, data_length, unique_adapter_file_id = handle_upload_from_string(
				adapter=dt_adapter,
				filedata=filedata,
				is_private=is_private,
			)
		else:
			content_hash, data_length, unique_adapter_file_id = handle_upload_from_stream(
				adapter=dt_adapter,
				datastream=datastream,
				is_private=is_private,
			)
	except DuplicateContentHashError as e:
		file_with_same_hash = e.file_with_same_hash

	if not file_with_same_hash:
		if frappe.db.get_value('File', filters={
			'file_name': file_name,
		}):
			file_name = f'{str(uuid4())}_{file_name}'
		file_doc = frappe.get_doc({
			'doctype': 'File',
			'file_name': file_name,
			'file_url': f'/files/{file_name}',
			'attached_to_doctype': doctype,
			'attached_to_name': docname,
			'is_private': is_private,
			'content_hash': content_hash,
			'file_size': data_length,
			'adapter_type': dt_adapter.adapter_type,
			'adapter_id': unique_adapter_file_id,
		})
	else:
		file_doc = frappe.copy_doc(frappe.get_doc('File', file_with_same_hash))
		file_doc.attached_to_doctype = doctype
		file_doc.attached_to_name = docname
		file_doc.is_private = cint(is_private)

	file_doc.insert(ignore_permissions=True)
	comment = {}
	if doctype and docname:
		icon = '<i class="fa fa-lock text-warning"></i>' if file_doc.is_private else ""
		file_name = file_doc.file_name or file_doc.file_url
		comment = frappe.get_doc(doctype, docname).add_comment(
			"File",
			f"added <a href='{file_doc.file_url}' target='_blank'>{file_name}</a>{icon}"
		)
	file_doc.comment = comment

	return file_doc

def handle_upload_from_string(adapter, filedata, *args, **kwargs):
	data_length = len(filedata)
	content_hash = md5(filedata).hexdigest() or '__INVALID_HASH__'
	if not data_length:
		frappe.throw('No data uploaded')

	files_with_same_hash = frappe.get_all('File', filters={
		'content_hash': content_hash,
		'file_size': data_length,
		'does_not_exist': 0,
	}, fields=[
		'name',
		'adapter_id',
		'adapter_type',
	])

	for attached_file in files_with_same_hash:
		old_file_adapter = frappe.get_cached_doc('Storage Adapter Settings').get_adapter_by_name(
			attached_file.adapter_type
		)
		if old_file_adapter.exists(attached_file.adapter_id):
			raise DuplicateContentHashError(file_with_same_hash=attached_file.name)
		else:
			frappe.db.set_value('File', attached_file.name, 'does_not_exist', 1)

	unique_adapter_file_id = adapter.upload(
		*args,
		filedata=filedata,
		**kwargs
	)
	return content_hash, data_length, unique_adapter_file_id

class StreamAnalyzer(object):
	__slots__ = [
		'__sig', '__source', '__length', '__content_hash',
	]
	def __init__(self, source):
		self.__sig = md5()
		self.__source = source
		self.__length = 0

	def __len__(self):
		return self.__length

	def __iter__(self):
		for chunk in self.__source:
			self.__sig.update(chunk)
			self.__length += len(chunk)
			yield chunk
		self.verify_hash()

	def read(self):
		try:
			chunk = self.__source.next()
			self.__sig.update(chunk)
			self.__length += len(chunk)
			return chunk
		except StopIteration:
			self.verify_hash()
			return b''

	def verify_hash(self):
		content_hash = self.__sig.hexdigest()
		self.__content_hash = content_hash
		if not self.__length:
			frappe.throw('No data uploaded')

	@property
	def content_hash(self):
		return self.__content_hash

def handle_upload_from_stream(adapter, datastream, *args, **kwargs):
	stream = StreamAnalyzer(datastream)
	unique_adapter_file_id = adapter.upload_via_stream(
		*args,
		datastream=stream,
		**kwargs
	)
	return stream.content_hash, len(stream), unique_adapter_file_id

@frappe.whitelist()
def authenticate_socketio_upload(doctype=None, docname=None, is_private=None, filename=None):
	has_upload_permission(doctype, docname)
	upload_id = str(uuid4())
	frappe.cache().set(f'upload_auth|{frappe.session.user}|{upload_id}', dumps({
		'doctype': doctype,
		'docname': docname,
		'is_private': is_private,
		'file_name': filename,
	}))
	return upload_id

@frappe.whitelist()
def upload_via_socketio(upload_id):
	cache = frappe.cache()
	upload_details = cache.get(f'upload_auth|{frappe.session.user}|{upload_id}')
	if not upload_details:
		frappe.throw('Premature Upload Called')

	upload_details = loads(upload_details)
	data = []
	upload_cache_path = f'upload_file|{frappe.session.user}|{upload_id}'
	while (chunk := cache.rpop(upload_cache_path)):
		data.append(chunk)

	file_doc = upload_from_data(**upload_details, filedata=(b'').join(data))

	frappe.db.run_after_commit(lambda: cache.delete(upload_cache_path))

	return {
		"name": file_doc.name,
		"file_name": file_doc.file_name,
		"file_url": file_doc.file_url,
		"is_private": file_doc.is_private,
		"comment": file_doc.comment,
	}

@frappe.whitelist()
def delete_file(fid, dt, dn):
	attachment_name = frappe.db.get_value('File', filters={
		'name': fid,
		'attached_to_doctype': dt,
		'attached_to_name': dn,
	})
	if not attachment_name:
		frappe.throw(f'File {fid} does not exists', frappe.DoesNotExistError)
	doc = frappe.get_doc(dt, dn)
	if not doc.has_permission('write'):
		frappe.throw(f'Not authorised to remove attachment from "{dt}" "{dn}"', frappe.PermissionError)

	frappe.delete_doc('File', fid, ignore_permissions=True)

def has_upload_permission(dt, dn):
	if not (dt and dn):
		return
	doc = frappe.get_doc(dt, dn)
	if not doc.has_permission('read'):
		frappe.throw(f'Not authorised to upload attachment to "{dt}" "{dn}"', frappe.PermissionError)

def has_download_permission(dt, dn):
	if not (dt and dn):
		return
	doc = frappe.get_doc(dt, dn)
	if not doc.has_permission('read'):
		frappe.throw(f'Not authorised to download attachment to "{dt}" "{dn}"', frappe.PermissionError)
