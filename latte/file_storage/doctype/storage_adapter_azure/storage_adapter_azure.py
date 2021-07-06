# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from azure.storage.blob import BlobClient, BlobServiceClient, StorageStreamDownloader
from uuid import uuid4
from hmac import HMAC
from hashlib import sha256
from base64 import b64encode, b64decode
from datetime import datetime
from frappe.model.document import Document
from latte.file_storage.abc import AdapterAbc

class StorageAdapterAzure(AdapterAbc):
	@staticmethod
	def get_blob_client(blob_name, **kwargs):
		config = StorageAdapterAzure.get_azure_config()
		container = config.container_name
		connection_string = config.connection_string
		client = BlobClient.from_connection_string(
			connection_string,
			container,
			blob_name,
			**kwargs
		)
		return client

	@staticmethod
	def upload(filedata, *args, **kwargs):
		blob_name = str(uuid4())
		client = StorageAdapterAzure.get_blob_client(blob_name)
		try:
			client.upload_blob(
				data=filedata,
			)
		except ResourceNotFoundError:
			StorageAdapterAzure.create_container()
			client.upload_blob(
				data=filedata,
			)

		return client.blob_name

	# def download(blob_name):
	# 	client = get_blob_client(blob_name, max_single_get_size=1024*1024)
	# 	writer = client.download_blob()
	# 	return writer.chunks()

	@staticmethod
	def delete(blob_name):
		client = StorageAdapterAzure.get_blob_client(blob_name)
		print('deleting', blob_name)
		client.delete_blob()

	@staticmethod
	def exists(blob_name):
		client = StorageAdapterAzure.get_blob_client(blob_name)
		try:
			return not not client.get_blob_properties()
		except ResourceNotFoundError:
			return False

	@staticmethod
	def get_azure_config():
		blob_config = frappe.get_doc('Storage Adapter Azure')
		blob_config.connection_string = f'DefaultEndpointsProtocol=https;\
AccountName={blob_config.account};\
AccountKey={blob_config.account_key};\
EndpointSuffix=core.windows.net'
		return blob_config

	@staticmethod
	def create_container():
		config = StorageAdapterAzure.get_azure_config()
		service_client = BlobServiceClient.from_connection_string(config.connection_string)
		try:
			service_client.create_container(config.container_name)
		except ResourceExistsError:
			return

	@staticmethod
	def get_proxy_meta(blob_name):
		config = StorageAdapterAzure.get_azure_config()
		container = config.container_name

		formatted_date = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
		api_version = config.api_version
		account_key = config.account_key
		account = config.account
		return {
			'load_type': 'api',
			'headers': {
				'Authorization': f'''SharedKeyLite {account}:{StorageAdapterAzure.get_signature(
					formatted_date,
					account_key,
					api_version,
					account,
					container,
					blob_name,
				)}''',
				'x-ms-date': formatted_date,
				'x-ms-version': api_version,
			},
			'proxy': f'{account}.blob.core.windows.net',
			'proxy_uri': f'/{container}/{blob_name}',
		}

	@staticmethod
	def get_signature(formatted_date, account_key, api_version, account, container, blob_name):
		string_to_sign = f'''GET



x-ms-date:{formatted_date}
x-ms-version:{api_version}
/{account}/{container}/{blob_name}'''
		print(string_to_sign)
		signature = b64encode(
			HMAC(
				b64decode(account_key),
				string_to_sign.encode('utf-8'),
				sha256
			).digest()
		)
		return str(signature, 'utf-8')

	def validate_settings(self):
		to_validate = ['Account', 'Container Name', 'Account Key', 'API Version']
		not_present = [field for field in to_validate if not getattr(self, frappe.scrub(field))]
		if not_present:
			frappe.throw(f'''
				Kindly fill in {frappe.utils.comma_and(not_present)} fields in
				<strong><a href="/desk#Form/Storage Adapter Azure">Storage Adapter Azure</a></strong>
				to continue
			''')

		self.get_blob_client('___RANDOM___')
