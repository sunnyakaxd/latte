import frappe
from frappe.model.document import Document
run_notifications = Document.run_notifications

eventname_map = {
	'Save': 'on_update,on_update_after_submit',
	'Value Change': 'on_update,on_update_after_submit',
	'New': 'after_insert',
	'Submit': 'on_submit',
	'Cancel': 'on_cancel',
	'Method': None,
}

def load_notification_hooks(dt='Notification', handler_name='latte.dynamic_hooks.notification.run_notifications'):
	hooks = {}
	notification_hooks = frappe.db.sql(f'''
		select distinct
			document_type,
			event,
			method
		from
			`tab{dt}`
		where
			enabled = 1
			and event in %(events)s
	''', {
		'events': list(eventname_map),
	})

	for dt, event, method in notification_hooks:
		if event == 'Method':
			frappe.append_hook(hooks, dt, {
				method: handler_name,
			})
		else:
			for event in eventname_map[event].split(','):
				frappe.append_hook(hooks, dt, {
					event: handler_name,
				})

	return {
		'doc_events': hooks
	}

def load_broadcast_hooks(dt='Broadcast', handler_name='latte.reminder_alert_and_notification.doctype.broadcast.broadcast.execute_broadcast'):
	hooks = {}
	broadcast_hooks = frappe.db.sql(f'''
		select distinct
			document_type,
			event,
			method
		from
			`tab{dt}`
		where
			enabled = 1
			and event in %(events)s
	''', {
		'events': list(eventname_map),
	})
	for dt, event, method in broadcast_hooks:
		if event == 'Method':
			frappe.append_hook(hooks, dt, {
				method: handler_name,
			})
		else:
			for event in eventname_map[event].split(','):
				frappe.append_hook(hooks, dt, {
					event: handler_name,
				})

	return {
		'doc_events': hooks
	}
	