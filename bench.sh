#!/bin/sh
cd sites
echo "Running From `pwd`"
echo "$@"
exec ../env/bin/python -u  -m frappe.utils.bench_helper frappe "$@"
