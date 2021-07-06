# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import os
from uuid import uuid4
from pathlib import Path
from frappe.model.document import Document
from latte.file_storage.abc import AdapterAbc

class StorageAdapterFile(AdapterAbc):
	@staticmethod
	def upload_via_stream(*args, **kwargs):
		return StorageAdapterFile.upload(*args, **kwargs)

	@staticmethod
	def get_file_path(path):
		sites_path = os.path.abspath(frappe.get_site_path())
		return f'{sites_path}/{path}'

	@staticmethod
	def upload(is_private, *args, filedata=None, datastream=None, **kwargs):
		file_name = str(uuid4())
		security_path = 'private' if is_private else 'public'
		sites_path = os.path.abspath(frappe.get_site_path())
		folder_path = f'{security_path}/files'
		file_id = f'{folder_path}/{file_name}'
		file_path = f'{sites_path}/{file_id}'
		try:
			fd = os.open(file_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 644)
		except FileNotFoundError:
			os.mkdir(folder_path)
			fd = os.open(file_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 644)

		if datastream is None:
			datastream = [filedata]

		with os.fdopen(fd, 'wb') as f:
			for data in datastream:
				f.write(data)

		try:
			os.chmod(file_path, 0o644)
		except PermissionError:
			pass

		return file_id

	@staticmethod
	def delete(file_path):
		sites_path = os.path.abspath(frappe.get_site_path())
		try:
			os.remove(f'{sites_path}/{file_path}')
		except FileNotFoundError:
			pass

	@staticmethod
	def get_proxy_meta(file_path):
		return {
			'load_type': 'file',
			'file_name': file_path,
		}

	@staticmethod
	def exists(file_path):
		return Path(StorageAdapterFile.get_file_path(file_path)).is_file()

	@staticmethod
	def get_data_stream(file_path):
		return open(StorageAdapterFile.get_file_path(file_path), 'rb')

	@staticmethod
	def get_data(file_path):
		with open(StorageAdapterFile.get_file_path(file_path), 'rb') as f:
			return f.read()
