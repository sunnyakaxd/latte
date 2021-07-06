import frappe
from latte.business_process.powerflow.powerflow import Powerflow
from frappe.model.db_query import DatabaseQuery
import re
from latte.business_process.constants import POWERFFLOW_CURRENT_STATE_FIELD

def powerflow_list_execute(doctype, *args, **kwargs):
	order_by = kwargs.get('order_by') or ''
	powerflow_filter_query = ''
	
	if order_by:
		table, field, ordering = re.match(r'^`([a-zA-Z ]+)`\.`([a-zA-Z_]+)` (asc|desc)$', order_by).groups()
		required_field = f'`{table}`.`{field}`'
		if not required_field in kwargs['fields']:
			kwargs['fields'].append(f'`{table}`.`{field}`')
		order_by = f'order by built.{field} {ordering}'

	if Powerflow.is_enabled_for(doctype):
		powerflow_filter = get_powerflow_filter(kwargs.get("filters"))
		if powerflow_filter:
			powerflow_condition = get_powerflow_condition(powerflow_filter)
			powerflow_filter_query = f"WHERE {powerflow_condition}"
		db_query =  DatabaseQuery(doctype)
		db_query.initialise(*args, **kwargs)
		built_query = db_query.build_query()
		if 'total_count' not in built_query:
			influenced_query = f'''
				select
					built.*,
					`tabPowerflow Status`.current_state as {POWERFFLOW_CURRENT_STATE_FIELD},
					ps.style as __powerflow_style,
					ps.show_default_indicator as __powerflow_show_default_indicator
				from
					({built_query}) built
				left join
					`tabPowerflow Status`
				on
					`tabPowerflow Status`.ref_doctype = '{doctype}'
					and `tabPowerflow Status`.ref_docname = built.name and built.docstatus = 0
				left join
					`tabPowerflow State` ps
				on
					ps.parent = `tabPowerflow Status`.powerflow_configuration
					and ps.state = `tabPowerflow Status`.current_state
				{powerflow_filter_query}
				{order_by}
			'''
			result = db_query.run(influenced_query)
			db_query.post_process()
		else:
			result = [{'total_count': 0}]
		if powerflow_filter:
			kwargs["filters"].append(powerflow_filter)
		return result

	return DatabaseQuery(doctype).execute(*args, **kwargs)


def get_powerflow_filter(filters):
	powerflow_filter = None
	indx = -1
	for fltr in filters:
		indx += 1
		if fltr[1] and fltr[1] == POWERFFLOW_CURRENT_STATE_FIELD:
			powerflow_filter = fltr
			break
	if indx>=0 and powerflow_filter:
		filters.pop(indx)

	return powerflow_filter

def get_powerflow_condition(powerflow_filter):
	db_query =  DatabaseQuery("Powerflow Status")
	db_query.tables.append("`tabPowerflow Status`")
	new_filter = []
	new_filter.append("Powerflow Status")
	new_filter.append("current_state")
	new_filter.append(powerflow_filter[2])
	new_filter.append(powerflow_filter[3])
	return db_query.prepare_filter_condition(new_filter)
