import pandas
import frappe
from frappe import local

old_read_sql = pandas.read_sql

def read_sql(query, con=None, index_col=None, coerce_float=True, params=None,
	parse_dates=None, columns=None, chunksize=None):
	return old_read_sql(
		query,
		con or local.db.get_connection(),
		index_col,
		coerce_float,
		params,
		parse_dates,
		columns,
		chunksize,
	)

pandas.read_sql = read_sql