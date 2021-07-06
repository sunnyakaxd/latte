import frappe.model.db_query
from frappe.model.db_query import DatabaseQuery
from latte.overrides.frappe.model.db_query import PatchedDatabaseQuery

DatabaseQuery.build_and_run = PatchedDatabaseQuery.build_and_run
DatabaseQuery.build_query = PatchedDatabaseQuery.build_query
DatabaseQuery.run = PatchedDatabaseQuery.run
DatabaseQuery.prepare_filter_condition = PatchedDatabaseQuery.prepare_filter_condition
frappe.model.db_query.DatabaseQuery = PatchedDatabaseQuery
