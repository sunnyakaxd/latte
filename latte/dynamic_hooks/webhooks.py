import frappe

def load_webhooks():
	webhooks = frappe.db.sql('''
		select distinct
			webhook_doctype,
			webhook_docevent
		from
			`tabWebhook`
	''')

	return {
		'doc_events': {
			dt: {
				method: 'frappe.integration.doctype.webhook.run_webhooks'
			}
			for dt, method in webhooks
		}
	}