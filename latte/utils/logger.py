from logging import LogRecord
from typing import Optional

from six import string_types

import frappe
import uuid
import logging
import zlib
from socket import gethostname
from logging.handlers import RotatingFileHandler
from pygelf import GelfUdpHandler
from frappe.model.document import Document
from latte.json import dumps_binary, loads
from traceback import walk_stack
from frappe import local

class CustomAttributes(logging.Filter):
	__slots__ = [
		'__modulename',
		'__index_name',
		'__storage_key',
	]
	def __init__(self, *args, modulename=None, index_name=None, storage_key=None, **kwargs):
		self.__modulename = modulename
		self.__index_name = index_name
		self.__storage_key = storage_key
		super().__init__(*args, **kwargs)

	def filter(self, record):
		message = enrich(record.msg)

		message['module'] = self.__modulename
		message['index_name'] = self.__index_name
		message['storage_key'] = self.__storage_key
		message['timestamp'] = record.created
		message['host'] = gethostname()

		if isinstance(message, frappe._dict):
			message = dict(message)

		record.msg = dumps_binary(message)

		return True

def enrich(logged_msg):
	if isinstance(logged_msg, dict):
		message = logged_msg
	elif isinstance(logged_msg, Document):
		message = logged_msg.as_dict()
	else:
		message = {'info': logged_msg}

	flags = local.flags

	flags.request_id_number = (flags.request_id_number or 0) + 1

	request_id = flags.request_id

	if not request_id:
		request_id = flags.request_id = str(uuid.uuid4())

	if 'request_id' not in message:
		message['request_id'] = request_id

	if 'task_id' not in message:
		message['task_id'] = flags.task_id

	if 'runner_type' not in message:
		message['runner_type'] = flags.runner_type

	message['log_number'] = flags.request_id_number
	message['site'] = getattr(local, 'site', None)

	if 'user' not in message:
		message['user'] = frappe.session.user
	if 'log_identity' not in message:
		message['log_identity'] = flags.log_identity
	if 'method' not in message:
		message['method'] = flags.current_running_method

	return message

def get_logger(module=None, with_more_info=False, index_name=None):
	if module is None:
		frame = next(walk_stack(None))[0]
		module = f'{frame.f_code.co_filename} | {frame.f_code.co_name}'

	storage_key = f'{module}_{index_name or "default"}'
	try:
		return frappe.loggers[storage_key]
	except KeyError:
		pass

	logger = logging.getLogger(storage_key)
	frappe.loggers[storage_key] = logger

	if getattr(logger, '__patched', None):
		return logger
	#logger.__patched = True

	logger_type = local.conf.logger_type
	# logger.addFilter(CustomAttributes(
	# 	modulename=module,
	# 	index_name=index_name or 'default',
	# 	storage_key=storage_key,
	# ))

	handler = None
	if logger_type != 'file':
		handler = get_gelf_handler()
		logger.addFilter(CustomAttributes(
				modulename=module,
				index_name=index_name or 'default',
				storage_key=storage_key,
		))
	if not handler:
		formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
		handler = RotatingFileHandler(
				local.conf.logfile or '../logs/frappe.log',
			maxBytes=100 * 1024 * 1024,
			backupCount=10,
		)
		handler.setFormatter(formatter)

	logger.addHandler(handler)
	logging_level = local.conf.logging_level or logging.INFO
	if str(logging_level).isnumeric():
		logging_level = int(logging_level)
	logger.setLevel(logging_level)
	logger.propagate = True
	logger.__patched = True
	return logger


def get_gelf_handler():
	gelf_config = local.conf.gelf_config
	if not gelf_config:
		return

	gelf_gelf_host = gelf_config.get('host', '127.0.0.1')
	gelf_gelf_port = gelf_config.get('port', 32000)
	return CustomGelfUdpHandler(host=gelf_gelf_host, port=gelf_gelf_port, include_extra_fields=True)

class CustomGelfUdpHandler(GelfUdpHandler):
	def convert_record_to_gelf(self, record):
		return zlib.compress(record.msg)


# class DictMessageFormatter(logging.Formatter):
#
# 	def __init__(self, fmt: Optional[str] = ..., ) -> None:
# 		super().__init__(fmt, validate=False)
#
# 	def formatMessage(self, record: LogRecord) -> str:
# 		msg = record.msg
# 		if msg:
# 			if isinstance(msg, dict):
# 				msg_dict = msg
# 			elif isinstance(msg, string_types):
# 				try:
# 					msg_dict = loads(msg)
# 				except:
# 					msg_dict = {"message": msg}
# 			else:
# 				msg_dict: {"message": msg}
#
# 			if not msg_dict.get("method", None):
# 				msg_dict.update({"method": "<function>"})
# 			if not msg_dict.get("info", None):
# 				msg_dict.update({"info": "<info>"})
# 			if record.args:
# 				record.args.update(msg_dict)
# 			else:
# 				record.args = msg_dict
# 			print(f"##### Record Args - {record.args}")
# 		return super(DictMessageFormatter, self).formatMessage(record)
