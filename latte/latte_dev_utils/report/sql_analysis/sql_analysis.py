# Copyright (c) 2013, Sachin Mane and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils.data import date_diff
from latte.database_utils.elasticsearch import get_log_es_connection
import pandas as pd

def execute(filters={}):
	from_date = filters.get('from_date') or frappe.utils.nowdate()
	to_date = filters.get('to_date') or frappe.utils.nowdate()
	min_r_rows = filters.get('min_r_rows') or 0

	index_names = [
		f'logstash-sql_analysis-{frappe.utils.add_to_date(from_date, days=count)}' for count in (range(date_diff(to_date, from_date) + 1))
	]

	conn = get_log_es_connection()
	es_index_names = list(conn.indices.get_alias(index_names, ignore_unavailable=True).keys())
	# return conn, es_index_names
	aggregations = conn.search(
		index=es_index_names,
		filter_path=['aggregations.commands.buckets'],
		body={
			'query': {
				# 'term': {
				# 	'method': 'frappe.desk.reportview.get',
				# 	'method': 'frappe.desk.query_report.run',
				# },
				'range': {
					'analysis.r_rows': {
						'gte': min_r_rows,
					}
				}
			},
			'aggs': {
				'commands': {
					'terms': {
						'field': 'method.keyword'
					},
					'aggs': {
						'identity': {
							'terms': {
								'field': 'log_identity.keyword'
							},
							'aggs': {
								'total_scanned': {
									'sum': {
										'field': 'analysis.r_rows',
									},
								},
							},
						},
						'total_scanned': {
							'sum': {
								'field': 'analysis.r_rows',
							},
						},
					},
				},
			},
		},
	)['aggregations']['commands']['buckets']

	# return aggregations

	rows = []
	for row in aggregations:
		print(row)
		for bucket in row['identity']['buckets']:
			# rows.append({
			# 	'method': row['key'],
			# 	'count': bucket['doc_count'],
			# 	'log_identity': bucket['key'],
			# 	'total_rows_scanned': bucket['total_scanned']['value'],
			# })
			rows.append((
				row['key'],
				bucket['doc_count'],
				bucket['key'],
				bucket['total_scanned']['value'],
			))

	return [
		'Method:Data:200',
		'Count:Int:200',
		'Identity:Data:200',
		'Total Row Scans:Int:100'
	], rows
