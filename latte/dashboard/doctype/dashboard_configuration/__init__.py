import frappe

@frappe.whitelist()
def dashboard_access():
    if frappe.local.request.method != 'GET':
        frappe.throw("Method not supported")
    user_roles = set(frappe.get_roles())
    dashboards = frappe.db.sql(''' 
        SELECT dc.name, dc.last_published_sync 
        FROM `tabDashboard Configuration` dc 
        INNER JOIN `tabDashboard Roles Access` dr 
        ON dc.name = dr.parent 
        WHERE role in ({}) 
        GROUP BY dc.name'''.format(', '.join('\"{}\"'.format(i) for i in user_roles)))

    if dashboards:
        # return [d[0] for d in dashboards]  if 'System Manager' in user_roles else [d[0] for d in dashboards if d[1]]
        return [d[0] for d in dashboards]
    return []

@frappe.whitelist()
def publish(dashboard_name=None):
    if not dashboard_name:
        frappe.throw("Dashboard Name Required")

    dashboard_doc = frappe.get_doc('Dashboard Configuration', dashboard_name)
    if not dashboard_doc:
        frappe.throw('Dashboard %s not found', dashboard_name)

    for dashboard_slice in dashboard_doc.dashboard_data_slices:
        dashboard_slice.obj = frappe.get_doc("Dashboard Data Slice", dashboard_slice.dashboard_data_slice)

    dashboard_doc.published_configuration = frappe.as_json(dashboard_slice)
    dashboard_doc.last_published_sync = frappe.utils.now()
    dashboard_doc.save()
    return dashboard_doc.published_configuration

@frappe.whitelist()
def dashboard_dataslices(dashboard_name=None):
    if frappe.local.request.method != 'GET':
        frappe.throw("Method not supported")

    if not dashboard_name:
        frappe.throw("Dashboard Name Required")

    dashboard_doc = frappe.get_doc('Dashboard Configuration', dashboard_name)
    if not dashboard_doc:
        frappe.throw('Dashboard %s not found', dashboard_name)
    dataslices = list(set(map(lambda ds: ds.dashboard_data_slice, dashboard_doc.dashboard_data_slices)))
    slices = []
    for ds in dataslices:
        slices.append(frappe.get_doc("Dashboard Data Slice", ds))
    return slices

@frappe.whitelist()
def run(dashboard_name=None, filters=None):
    if not dashboard_name:
        frappe.throw('Dashboard Name Required')

    dashboard_doc = frappe.get_doc('Dashboard Configuration', dashboard_name)

    if not dashboard_doc:
        frappe.throw('Dashboard %s not found', dashboard_name)

    # Check User Permission for Role Access
    role_perms = set([r.role for r in dashboard_doc.role_permission])
    user_roles = set(frappe.get_roles())
    if len(role_perms.intersection(user_roles)) <= 0:
        frappe.throw("You do not have access for Dashboard - {}".format(dashboard_name))

    dashboard_configuration_data = {
        'name': dashboard_name,
        'data_slice_data': [],
    }
    dashboard_slice_data = []
    for dashboard_data_slice in dashboard_doc.dashboard_data_slices:
        data_slice = frappe.get_doc('Dashboard Data Slice', dashboard_data_slice.dashboard_data_slice)
        result, status = data_slice.execute(filters)
        dashboard_slice_data.append({
            'data_slice_id': dashboard_data_slice.name,
            'data_slice_name': data_slice.data_slice_name,
            'data_type': data_slice.data_type,
            'data_source': data_slice.data_source,
            'result': result,
            'status': status
        })
    dashboard_configuration_data['data_slice_data'] = dashboard_slice_data
    return dashboard_configuration_data