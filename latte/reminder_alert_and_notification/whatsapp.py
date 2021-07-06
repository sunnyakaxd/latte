import requests, json, base64, requests, frappe, orjson
from frappe.core.doctype.sms_settings.sms_settings import validate_receiver_nos

@frappe.whitelist()
def send_whatsapp(recipients, message, filedata=None, filename=None, template_name=None, template_params=None, params_header=None):
	recipient_list = validate_receiver_nos(recipients)
	for recipient in recipient_list:
		if template_name:
			if filedata:
				params_header = params_header or "Default"
				json_message = {
					"Header": {
						"auth": "94f82bd6e1dab59:cd989119c7914cf",
						"service_id": "Synapse:Whatsapp",
						"service_type": "sync",
						"service_version": "1.0",
						"api_name": "send_media_template",
						"account_name": "Withrun",
					},
					"Payload": {
						"filename": filename,
						"filedata": filedata,
						"template_name": template_name,
						"params_header": params_header,
						"params": template_params,
						"customer_number": f"+91{recipient}",
					}
				}
			else:
				json_message = {
					"Header": {
						"auth": "94f82bd6e1dab59:cd989119c7914cf",
						"service_id": "Synapse:Whatsapp",
						"service_type": "sync",
						"service_version": "1.0",
						"api_name": "send_text_template",
						"account_name": "Withrun",
					},
					"Payload": {
						"customer_number": f"+91{recipient}",
						"template_name": template_params,
						"params": template_params,
						"lang_code": 'en',
					}
				}

		else:
			if filedata:
				json_message = {
					"Header": {
						"auth": "94f82bd6e1dab59:cd989119c7914cf",
						"service_id": "Synapse:Whatsapp",
						"service_type": "sync",
						"service_version": "1.0",
						"api_name": "send_media_message",
						"account_name": "Withrun",
					},
					"Payload": {
						"filename": filename,
						"filedata": filedata,
						"body": message,
						"customer_number": f"+91{recipient}",
					}
				}

			else:
				json_message = {
					"Header": {
						"auth": "94f82bd6e1dab59:cd989119c7914cf",
						"service_id": "Synapse:Whatsapp",
						"service_type": "sync",
						"service_version": "1.0",
						"api_name": "send_text_message",
						"account_name": "Withrun",
					},
					"Payload": {
						"customer_number": f"+91{recipient}",
						"body": message,
						"lang_code": 'en',
					}
				}

		url = "https://synapse.elasticrun.in/api/method/synapse.execute_api"
		result = requests.post(url, data = orjson.dumps(json_message))
		return result
