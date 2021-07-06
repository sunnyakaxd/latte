from frappe.model.document import Document

class AdapterAbc(Document):
	@staticmethod
	def upload_via_stream(*args, **kwargs):
		raise NotImplementedError("Method not implemented")

	@staticmethod
	def upload(*args, **kwargs):
		raise NotImplementedError("Method not implemented")

	@staticmethod
	def delete(adapter_id):
		raise NotImplementedError("Method not implemented")

	@staticmethod
	def get_proxy_meta(adapter_id):
		raise NotImplementedError("Method not implemented")

	@staticmethod
	def get_data_stream(adapter_id):
		raise NotImplementedError("Method not implemented")

	@staticmethod
	def get_data(adapter_id):
		raise NotImplementedError("Method not implemented")
