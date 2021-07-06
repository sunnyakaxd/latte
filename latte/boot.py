import frappe

def dashboard_access(bootinfo):
    roles = frappe.get_roles()
    try:
        dashboard_role_access = frappe.db.sql("""
            SELECT
                cd.name, dra.role
            FROM
                `tabDashboard Roles Access` dra
            INNER JOIN
                `tabDashboard Configuration` cd
            ON cd.name = dra.parent
            WHERE cd.last_published_sync IS NOT NULL AND dra.role IN ({roles}) group by cd.name
        """.format(roles=', '.join(['%s']*len(roles))), roles, as_dict=1)

        for dra in dashboard_role_access:
            bootinfo.page_info[dra['name']] = frappe._dict({
                'title': dra['name'],
                'name': dra['name'],
                'route': 'dashboard/' + dra['name']
            })
    except Exception as a:
        error_trace = frappe.get_traceback()
        frappe.log_error(error_trace)

DEFAULT_UPLOAD_CONFIG = {
    'file_size_limit': 2,
    'disable_socketio': 0,
    'form_data_limit': 24576,
}
def file_size_limit(bootinfo):
    upload_config = frappe.local.conf.upload_config
    if not upload_config:
        bootinfo['upload_config'] = DEFAULT_UPLOAD_CONFIG
    else:
        bootinfo['upload_config'] = {
            'file_size_limit': upload_config.get('file_size_limit', DEFAULT_UPLOAD_CONFIG['file_size_limit']),
            'disable_socketio': upload_config.get('disable_socketio', DEFAULT_UPLOAD_CONFIG['disable_socketio']),
            'form_data_limit': upload_config.get('form_data_limit', DEFAULT_UPLOAD_CONFIG['form_data_limit']),
        }
