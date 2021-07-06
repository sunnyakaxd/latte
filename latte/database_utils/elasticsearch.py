from elasticsearch import Elasticsearch
from frappe import local

CONNECTION = None

def get_log_es_connection():
	global CONNECTION
	if not CONNECTION:
		hosts = local.conf.log_es_hosts
		if not hosts:
			raise Exception('Elasticsearch hosts for logger es instance not configured')

		CONNECTION = Elasticsearch(hosts)

	return CONNECTION

