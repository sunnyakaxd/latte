import frappe.utils.pdf

def prepare_options(html, options):
    if not options:
        options = {}
    options.update({
        'print-media-type': None,
        'background': None,
        'images': None,
        'quiet': None,
        # 'no-outline': None,
        'encoding': "UTF-8",
        # 'load-error-handling': 'ignore'
    })

    if not options.get("margin-right"):
        options['margin-right'] = '15mm'

    if not options.get("margin-left"):
        options['margin-left'] = '15mm'

    html, html_options = frappe.utils.pdf.read_options_from_html(html)
    options.update(html_options or {})

    # Fixing for SSRF vulenrability to avoid session hijacking by commenting below 3 lines
    # # cookies
    # if frappe.session and frappe.session.sid:
    # 	options['cookie'] = [('sid', '{0}'.format(frappe.session.sid))]

    # page size
    if not options.get("page-size"):
        options['page-size'] = frappe.db.get_single_value(
            "Print Settings", "pdf_page_size") or "A4"

    return html, options


frappe.utils.pdf.prepare_options = prepare_options
