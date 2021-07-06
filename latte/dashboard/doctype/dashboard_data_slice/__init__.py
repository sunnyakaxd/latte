import frappe
import jwt
import time
from latte.utils.caching import cache_me_if_you_can

@frappe.whitelist()
def run(slice_name=None, data_source_name=None, filters=None):
    return run_cached(slice_name, data_source_name, filters)

# @cache_me_if_you_can(expiry=20)
def run_cached(slice_name=None, data_source_name=None, filters=None):
    if not slice_name:
        frappe.throw('Dashboard Name Required')

    dataslice_doc = frappe.get_doc('Dashboard Data Slice', slice_name)

    response, status = dataslice_doc.execute(data_source_name, filters)
    return frappe._dict({
        'response': response,
        'status': status
    })

@frappe.whitelist()
def get_metabase_url(name, resource_type, metabase_site_url=None, metabase_secret_key=None):
    if frappe.conf.metabase_site_url:
        metabase_site_url = frappe.conf.metabase_site_url

    if frappe.conf.metabase_secret_key:
        metabase_secret_key = frappe.conf.metabase_secret_key

    payload = {
        'resource': {resource_type: int(name)},
        'params': {},
        'exp': round(time.time()) + (60 * 100)  # 100 minute expiration
    }
    token = jwt.encode(payload, metabase_secret_key, algorithm='HS256')

    iframeUrl = metabase_site_url + '/embed/'+ resource_type +'/' + token.decode('utf8') + '#bordered=true&titled=false'

    return iframeUrl

@frappe.whitelist()
def save_chart_config(data_slice, config):
    data_slice_doc = frappe.get_doc("Dashboard Data Slice", data_slice)
    data_slice_doc.chart_default_config = config
    data_slice_doc.save()
    return "Success"