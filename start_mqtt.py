# -*- coding: utf-8 -*-

import sys
from gevent import monkey, spawn
monkey.patch_all()

import frappe
from latte.commands.utils import patch_all
patch_all()
import latte
from latte.utils.logger import get_logger
import paho.mqtt.client as mqtt
from frappe import local
import signal
from latte.json import loads
from latte.utils.background.job import Task

GRACEFUL_SHUTDOWN_WAIT = 10

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
	print("Connected with result code "+str(rc))

	# Subscribing in on_connect() means that if we lose the connection and
	# reconnect then subscriptions will be renewed.
	client.subscribe("worker_all")

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
	logger = get_logger('mqtt_worker')
	try:
		task_dict = loads(msg.payload)
		method = task_dict.pop('method')
		Task(
			method=method,
			site='site1.docker',
			user='Administrator',
			queue='mqtt_worker',
			kwargs=task_dict,
		).process_task()

	except Exception:
		if userdata.developer_mode:
			print(msg.payload)
			print(frappe.get_traceback())

		logger.error({
			'topic': msg.topic,
			'method': '__NONE__',
			'pool_size': 0,
			'stage': 'Fatal',
			'traceback': frappe.get_traceback()
		})

def start():
	from gevent.signal import signal as handle_signal
	latte.init(site='')
	mqtt_conf = local.conf.mqtt_conf
	if not mqtt_conf:
		print('mqtt_conf not present in common_site_config.json, exiting', file=sys.stderr)
		return

	broker_host = mqtt_conf['broker']
	broker_port = mqtt_conf['port']
	print(f'Starting mqtt worker listening to host', broker_host, 'on port', broker_port)
	handle_signal(signal.SIGHUP, graceful_shutdown)
	handle_signal(signal.SIGINT, graceful_shutdown)
	handle_signal(signal.SIGTERM, graceful_shutdown)

	client = mqtt.Client(userdata=local.conf)
	client.on_connect = on_connect
	client.on_message = on_message

	client.connect(broker_host, broker_port, 60)

	# Blocking call that processes network traffic, dispatches callbacks and
	# handles reconnecting.
	# Other loop*() functions are available that give a threaded interface and a
	# manual interface.
	client.loop_forever()

def graceful_shutdown(*args, **kwargs):
	from latte.utils.background.job import Task
	print('Warm shutdown requested')
	graceful = Task.pool.join(timeout=GRACEFUL_SHUTDOWN_WAIT)
	print('Shutting down, Gracefully=', graceful)
	exit(0 if graceful else 1)

start()