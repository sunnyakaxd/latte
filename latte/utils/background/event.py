import redis
import frappe
import logging
from zlib import compress
from six import string_types
from pygelf import GelfUdpHandler

def publish_redis_event(queue, compressed):
	client = get_redis_client()
	if not client:
		return
	client.lpush(f'events:queue:{queue}', compressed)

def publish_gelf_event(queue, compressed):
	writer = get_gelf_writer(queue)
	if not writer:
		return
	writer.debug(compressed)

style_map = {
	'redis': publish_redis_event,
	'gelf': publish_gelf_event,
}

def publish_event(event, payload='', doctype='', queue='default', buffer=False):
	event_style = frappe.local.conf.event_style
	event_dict = {
		'event': event,
		'payload': payload if isinstance(payload, string_types) else frappe.as_json(payload),
		'doctype': doctype,
		'queue': queue,
	}
	payload = frappe.as_json(event_dict)

	# compressed = compress(payload.encode())
	compressed = payload
	style_map.get(event_style, publish_gelf_event)(queue, compressed)

redis_client_map = {}

def get_redis_client():
	redis_event_writer = frappe.local.conf.redis_event_writer
	if not redis_event_writer:
		frappe.logger().warn('Redis event fired but writer not configured')
	try:
		return redis_client_map[redis_event_writer]
	except KeyError:
		client = redis.StrictRedis.from_url(redis_event_writer)

		return client

GELF_WRITERS = {}

def get_gelf_writer(queue):
	try:
		return GELF_WRITERS[queue]
	except KeyError:
		pass

	logger = logging.getLogger(f'events:queue:{queue}')
	gelf_config = frappe.local.conf.gelf_event_writer
	if not gelf_config:
		frappe.logger().warn('Gelf event queue is not configured, while events are being fired')
		return

	gelf_host = gelf_config.get('host', '127.0.0.1')
	gelf_port = gelf_config.get('port', 32001)
	handler = GelfUdpHandler(host=gelf_host, port=gelf_port)
	logger.addHandler(handler)
	logger.setLevel(logging.DEBUG)
	logger.propagate = True
	GELF_WRITERS[queue] = logger
	return logger


