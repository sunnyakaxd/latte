
import frappe
from frappe.model.document import Document
import json
import datetime
import requests
from six import iteritems, string_types
import os
import re
from collections import namedtuple

def send_ulterius(recipients,message,doc,broadcast):
    for recipient in recipients:
        log_ulterius_notification(
            action="NOTIFICATION",
            request=message,
            user_id=recipient,
            notification_status="Queued",
            doc_type=doc and doc.doctype,
            doc_name=doc and doc.name,
            linked_broadcast=broadcast.name,
        )
    if not broadcast.schedule_notification:
        execute_scheduled_broadcast([broadcast.name])

@frappe.whitelist()
def execute_scheduled_broadcast(params):
    if isinstance(params,str):
        params=json.loads(params)
    alert=frappe.get_doc("Broadcast",params[0])
    current_date = frappe.utils.now_datetime()
    ulterius_logs=frappe.get_all("Ulterius Notification Log",filters={"notification_status":"Queued","broadcast":alert.name},fields=["name"])
    for ulterius_log in ulterius_logs:
        ulterius_log=frappe.get_doc("Ulterius Notification Log",ulterius_log.name)
        response=send_ulterius_request(ulterius_log)
        ulterius_log.response=response
        ulterius_log.notification_status=("Success") if response==200 else "Failed"
        ulterius_log.save(ignore_permissions=True)

def send_ulterius_request(ulterius_notification_log):
    ulterius_url = get_ulterius_url()
    site_config = frappe.local.conf
    response = None
    json_data=json.loads(ulterius_notification_log.request_json)
    
    if 'mute_reseller_notification' in site_config:
        if site_config['mute_reseller_notification'] != True:
            try:
                if ulterius_url != "":
                    response = requests.post(ulterius_url, json=json_data)
                    if response!=None:
                        return response.status_code
                else:
                    return "Ulterius Url is empty!"
            except Exception as ex:
                response = ex
            return response


def get_ulterius_url():
    url = ""
    try:
        ulterius_url = frappe.db.sql_list("""SELECT 
											ulterius_url
                                            FROM 
											`tabReseller App Version`
                                            WHERE 
											status='Published'
                                            AND 
											enable_push_notification=1
                                            ORDER BY modified DESC""")

        if len(ulterius_url):
            if ulterius_url[0][-1:] == '/':
                url = ulterius_url[0]+"ulterius/broadcastMessage"
            else:
                url = ulterius_url[0]+"/ulterius/broadcastMessage"
        else:
            url = ""
    except Exception:
        frappe.log_error(frappe.get_traceback(),'get_ulterius_url')
    return url


def log_ulterius_notification(action, request, user_id, notification_status,doc_type,doc_name,linked_broadcast):
    try:
        ul_log = frappe.new_doc('Ulterius Notification Log')
        if ul_log is not None:
            ul_log.user_id = user_id
            ul_log.request_json = json.dumps({
                "action": action,
                "appId": "mobileKirana",
                "userId": user_id,
                "message":{
                    "docType": doc_type,
                    "docName": doc_name,
                    "message": request,
                    "priority": "",
                    "mobile_ui_page":"",
                },
            })
            ul_log.notification_status = notification_status
            ul_log.action = action
            ul_log.reference_doctype=doc_type
            ul_log.reference_docname=doc_name
            ul_log.broadcast=linked_broadcast
            ul_log.insert(True)
    except Exception as ex:
        frappe.log_error(frappe.get_traceback(),'ulterius_notification_log')
        