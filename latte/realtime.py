import frappe
import os
from frappe.realtime import (
	get_task_progress_room,
	get_user_room,
	get_doc_room,
	get_site_room,
	get_chat_room,
	emit_via_redis
)
from frappe import local

@frappe.whitelist()
def can_subscribe_doc(doctype, docname):
	if os.environ.get('CI'):
		return True

	if not frappe.has_permission(doctype=doctype, doc=docname, ptype='read'):
		raise PermissionError()
	return True

def publish_realtime(event=None, message=None, room=None,
	user=None, doctype=None, docname=None, task_id=None,
	after_commit=False):
	"""Publish real-time updates

	:param event: Event name, like `task_progress` etc. that will be handled by the client (default is `task_progress` if within task or `global`)
	:param message: JSON message object. For async must contain `task_id`
	:param room: Room in which to publish update (default entire site)
	:param user: Transmit to user
	:param doctype: Transmit to doctype, docname
	:param docname: Transmit to doctype, docname
	:param after_commit: (default False) will emit after current transaction is committed"""
	if (skip_events := local.conf.skip_realtime_events) and event in skip_events:
		return

	if message is None:
		message = {}

	if event is None:
		if getattr(frappe.local, "task_id", None):
			event = "task_progress"
		else:
			event = "global"

	if event=='msgprint' and not user:
		user = frappe.session.user

	if not room:
		if not task_id and hasattr(frappe.local, "task_id"):
			task_id = frappe.local.task_id

		if task_id:
			room = get_task_progress_room(task_id)
			if not "task_id" in message:
				message["task_id"] = task_id

			after_commit = False
		elif user:
			room = get_user_room(user)
		elif doctype and docname:
			room = get_doc_room(doctype, docname)
		else:
			room = get_site_room()
	else:
		# frappe.chat
		room = get_chat_room(room)
		# end frappe.chat

	if after_commit:
		params = [event, message, room]
		if not params in frappe.local.realtime_log:
			frappe.local.realtime_log.append(params)
	else:
		emit_via_redis(event, message, room)
