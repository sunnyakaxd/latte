import frappe
import kubernetes
from frappe import local
from redis import Redis, ConnectionError, TimeoutError

def get_api_client():
	configuration = kubernetes.client.Configuration()
	configuration.verify_ssl = False

	# Configure API key authorization: BearerToken
	configuration.api_key['authorization'] = local.conf.k8s_api_key
	# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
	configuration.api_key_prefix['authorization'] = 'Bearer'

	# Defining host is optional and default to http://localhost
	configuration.host = local.conf.k8s_api_host
	# Enter a context with an instance of the API kubernetes.client
	return kubernetes.client.ApiClient(configuration)

def get_core_v1_api_client():
	try:
		return local.__k8s_core_v1_api_client
	except AttributeError:
		local.__k8s_core_v1_api_client = kubernetes.client.CoreV1Api(get_api_client())
		return local.__k8s_core_v1_api_client

def get_pod_meta(namespace, label_selector=None):
	return get_core_v1_api_client().list_namespaced_pod(namespace, label_selector=label_selector)

def get_cache_pod_ip():
	pod_meta = get_pod_meta(local.conf.k8s_namespace, f'app={local.conf.k8s_release}-redis-sccache')
	host_list = []
	for row in pod_meta.items:
		port = [[
			port.container_port
			for port in cont.ports if port.name == 'client'
		][0] for cont in row.spec.containers if cont.name == 'redis-sccache'][0]
		redis_url = f'redis://{row.status.pod_ip}:{port}'
		try:
			Redis.from_url(redis_url, socket_timeout=5, socket_connect_timeout=1).ping()
			host_list.append(redis_url)
		except (ConnectionError, TimeoutError):
			pass

	return sorted(host_list)

def refresh_cache_host_list():
	if not frappe.local.conf.detect_redis_caches:
		return

	hosts = get_cache_pod_ip()
	if frappe.local.conf.redis_caches == hosts:
		return

	for host in hosts:
		Redis.from_url(host, socket_timeout=5, socket_connect_timeout=1).flushall()

	from frappe.installer import update_site_config
	update_site_config('redis_caches', hosts)