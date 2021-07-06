from frappe import _

def get_data():
	return {
		'fieldname': 'payphi_request_docname',
		'transactions': [
			{
				'label': _('Reference'),
				'items': ['Response Logs']
			}
		]
	}