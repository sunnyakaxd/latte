import frappe.desk.reportview
from latte.business_process.powerflow.powerflow_list_view import powerflow_list_execute

frappe.desk.reportview.execute = powerflow_list_execute