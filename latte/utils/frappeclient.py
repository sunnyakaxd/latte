from __future__ import print_function, unicode_literals
from frappe.utils.response import as_raw
import requests
import json
import frappe
from six import iteritems, string_types
from base64 import b64encode
'''
FrappeClient is a library that helps you connect with other frappe systems
'''

class FrappeException(Exception):
	pass

class FrappeClient(object):
	def __init__(self, url, username=None, password=None, api_key=None, api_secret=None, verify=True):
		self.headers = {
			'Accept': 'application/json',
			'Content-Type': 'application/json',
		}
		self.verify = verify
		self.url = url

		# login if username/password provided
		if username and password:
			self.session = requests.session()
			self._login(username, password)
		elif api_key and api_secret:
			self.session = requests
			access_token = f'{api_key}:{api_secret}'
			print("access_token",access_token)
			self.headers['Authorization'] = f'token {access_token}'
		else:
			frappe.throw('Either username/password or api_key/secret is necessary')

	def __enter__(self):
		return self

	def __exit__(self, *args, **kwargs):
		self.logout()

	def _login(self, username, password):
		'''Login/start a sesion. Called internally on init'''
		r = self.session.post(self.url, data=frappe.as_json({
			'cmd': 'login',
			'usr': username,
			'pwd': password
		}), verify=self.verify, headers=self.headers)

		if r.status_code == 200 and r.json().get('message') == "Logged In":
			return r.json()
		else:
			if r.status_code == 401:
				raise Exception('Incorrect password in frappeclient')

			try:
				json_response = r.json()
				exception = FrappeException('message', json_response.get('message') or json_response.get('exc'))
				for msg in json_response.get('_server_messages', []):
					frappe.msgprint(msg)
			except:
				exception = FrappeException(r.text)

			exception.http_status_code = 417 if r.status_code == 417 else 500
			raise exception

	def logout(self):
		'''Logout session'''
		self.session.get(self.url, params={
			'cmd': 'logout',
		}, verify=self.verify, headers=self.headers)

	def ping(self):
		return self.get_api('frappe.ping')

	def get_list(self, doctype, fields='"*"', filters=None, limit_start=0, limit_page_length=0):
		"""Returns list of records of a particular type"""
		if not isinstance(fields, string_types):
			fields = json.dumps(fields)
		params = {
			"fields": fields,
		}
		if filters:
			params["filters"] = json.dumps(filters)
		if limit_page_length:
			params["limit_start"] = limit_start
			params["limit_page_length"] = limit_page_length
		res = self.session.get(self.url + "/api/resource/" + doctype, params=params, verify=self.verify, headers=self.headers)
		return self.post_process(res)

	def insert(self, doc):
		'''Insert a document to the remote server

		:param doc: A dict or Document object to be inserted remotely'''
		res = self.session.post(self.url + "/api/resource/" + doc.get("doctype"),
			data=frappe.as_json(doc), verify=self.verify, headers=self.headers)
		return self.post_process(res)

	def insert_many(self, docs):
		'''Insert multiple documents to the remote server

		:param docs: List of dict or Document objects to be inserted in one request'''
		return self.post_request({
			"cmd": "frappe.client.insert_many",
			"docs": frappe.as_json(docs)
		})

	def update(self, doc):
		'''Update a remote document

		:param doc: dict or Document object to be updated remotely. `name` is mandatory for this'''
		url = self.url + "/api/resource/" + doc.get("doctype") + "/" + doc.get("name")
		res = self.session.put(url, data=frappe.as_json(doc), verify=self.verify, headers=self.headers)
		return self.post_process(res)

	def bulk_update(self, docs):
		'''Bulk update documents remotely

		:param docs: List of dict or Document objects to be updated remotely (by `name`)'''
		return self.post_request({
			"cmd": "frappe.client.bulk_update",
			"docs": frappe.as_json(docs)
		})

	def delete(self, doctype, name):
		'''Delete remote document by name

		:param doctype: `doctype` to be deleted
		:param name: `name` of document to be deleted'''
		return self.post_request({
			"cmd": "frappe.client.delete",
			"doctype": doctype,
			"name": name
		})

	def submit(self, doc):
		'''Submit remote document

		:param doc: dict or Document object to be submitted remotely'''
		return self.post_request({
			"cmd": "frappe.client.submit",
			"doc": frappe.as_json(doc)
		})

	def get_value(self, doctype, filters=None, fieldname=None):
		'''Returns a value form a document

		:param doctype: DocType to be queried
		:param fieldname: Field to be returned (default `name`)
		:param filters: dict or string for identifying the record'''
		return self.get_request({
			"cmd": "frappe.client.get_value",
			"doctype": doctype,
			"fieldname": fieldname or "name",
			"filters": frappe.as_json(filters)
		})

	def set_value(self, doctype, docname, fieldname, value):
		'''Set a value in a remote document

		:param doctype: DocType of the document to be updated
		:param docname: name of the document to be updated
		:param fieldname: fieldname of the document to be updated
		:param value: value to be updated'''
		return self.post_request({
			"cmd": "frappe.client.set_value",
			"doctype": doctype,
			"name": docname,
			"fieldname": fieldname,
			"value": value
		})

	def cancel(self, doctype, name):
		'''Cancel a remote document

		:param doctype: DocType of the document to be cancelled
		:param name: name of the document to be cancelled'''
		return self.post_request({
			"cmd": "frappe.client.cancel",
			"doctype": doctype,
			"name": name
		})

	def get_doc(self, doctype, name="", filters=None, fields=None):
		'''Returns a single remote document

		:param doctype: DocType of the document to be returned
		:param name: (optional) `name` of the document to be returned
		:param filters: (optional) Filter by this dict if name is not set
		:param fields: (optional) Fields to be returned, will return everythign if not set'''
		params = {}
		if filters:
			params["filters"] = json.dumps(filters)
		if fields:
			params["fields"] = json.dumps(fields)

		res = self.session.get(self.url + "/api/resource/" + doctype + "/" + name,
			params=params, verify=self.verify, headers=self.headers)

		return self.post_process(res)

	def rename_doc(self, doctype, old_name, new_name):
		'''Rename remote document

		:param doctype: DocType of the document to be renamed
		:param old_name: Current `name` of the document to be renamed
		:param new_name: New `name` to be set'''
		params = {
			"cmd": "frappe.client.rename_doc",
			"doctype": doctype,
			"old_name": old_name,
			"new_name": new_name
		}
		return self.post_request(params)

	def get_api(self, method, params={}, as_raw=False):
		res = self.session.get(
			f"{self.url}/api/method/{method}/",
			params=params,
			verify=self.verify,
			headers=self.headers,
		)
		return self.post_process(res, as_raw)

	def post_api(self, method, data={}):
		res = self.session.post(
			f"{self.url}/api/method/{method}/",
			json=data,
			verify=self.verify,
			headers=self.headers,
		)
		return self.post_process(res)

	def get_request(self, params):
		if cmd := params.get('cmd'):
			url = self.url + '/api/method/' + cmd
			del params['cmd']
		else:
			url = self.url

		res = self.session.get(
			url,
			params=self.preprocess(params),
			verify=self.verify,
			headers=self.headers,
		)
		res = self.post_process(res)
		return res

	def post_request(self, data):
		if cmd := data.get('cmd'):
			url = self.url + '/api/method/' + cmd
			del data['cmd']
		else:
			url = self.url

		res = self.session.post(url, json=self.preprocess(data), verify=self.verify, headers=self.headers)
		res = self.post_process(res)
		return res

	def preprocess(self, params):
		"""convert dicts, lists to json"""
		for key, value in iteritems(params):
			if isinstance(value, (dict, list)):
				params[key] = json.dumps(value)

		return params

	def post_process(self, response, as_raw=False):
		if as_raw:
			return response.content
		else:
			try:
				rjson = response.json()
			except json.decoder.JSONDecodeError:
				# print(response.text)
				raise FrappeException(response.text)

		if rjson and ("exc" in rjson) and rjson["exc"]:
			try:
				exc = json.loads(rjson["exc"])[0]
				exc = 'FrappeClient Request Failed\n\n' + exc
			except Exception:
				exc = rjson["exc"]

			raise FrappeException(exc)
		if 'data' in rjson:
			return rjson['data']
		elif 'message' in rjson:
			return rjson['message']
		else:
			return rjson

class FrappeOAuth2Client(FrappeClient):
	def __init__(self, url, access_token, verify=True):
		self.access_token = access_token
		self.headers = {
			"Authorization": "Bearer " + access_token,
			"content-type": "application/x-www-form-urlencoded"
		}
		self.verify = verify
		self.session = OAuth2Session(self.headers)
		self.url = url

	def get_request(self, params):
		res = requests.get(self.url, params=self.preprocess(params), headers=self.headers, verify=self.verify)
		res = self.post_process(res)
		return res

	def post_request(self, data):
		res = requests.post(self.url, data=self.preprocess(data), headers=self.headers, verify=self.verify)
		res = self.post_process(res)
		return res

class OAuth2Session():
	def __init__(self, headers):
		self.headers = headers
	def get(self, url, params, verify):
		res = requests.get(url, params=params, headers=self.headers, verify=verify)
		return res
	def post(self, url, data, verify):
		res = requests.post(url, data=data, headers=self.headers, verify=verify)
		return res
	def put(self, url, data, verify):
		res = requests.put(url, data=data, headers=self.headers, verify=verify)
		return res
