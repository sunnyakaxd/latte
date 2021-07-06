from latte.monkey_patches import ENQUEUED
import frappe

def patch():
	import frappe.email.queue
	from frappe.utils.verified_command import get_secret
	from six.moves.urllib.parse import urlencode
	import hmac
	def get_signed_params(params):
		"""Sign a url by appending `&_signature=xxxxx` to given params (string or dict).

		:param params: String or dict of parameters."""
		if not isinstance(params, str):
			params = urlencode(params)

		signature = hmac.new(params.encode(), digestmod='MD5')
		signature.update(get_secret().encode())
		return params + "&_signature=" + signature.hexdigest()


	frappe.email.queue.get_signed_params = get_signed_params

def clear_outbox():
	while frappe.db.execute('''
		delete from
			`tabEmail Queue`
		where
			modified < curdate() - interval 30 day
		limit 1000
	''', {}):
		frappe.db.commit()

	while frappe.db.execute('''
		delete from
			`tabEmail Queue Recipient`
		where
			modified < curdate() - interval 30 day
		limit 1000
	''', {}):
		frappe.db.commit()

	while frappe.db.execute("""
		update `tabEmail Queue`
		set
			status='Expired'
		where
			modified < curdate() - interval 7 day
			and status='Not Sent'
			and (send_after is null or send_after < %(now)s)
		limit 1000
	""", {
		'now': frappe.utils.now_datetime()
	}):
		frappe.db.commit()

frappe.email.queue.clear_outbox = clear_outbox

ENQUEUED.append(patch)