# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import now_datetime, cint, cstr
import re
from six import string_types
from frappe.model import naming, document
from frappe.model.naming import (
    validate_name,
    set_name_from_naming_options,
    make_autoname,
    _set_amended_name
)

def set_new_name(doc):
    """
    Sets the `name` property for the document based on various rules.

    1. If amended doc, set suffix.
    2. If `autoname` method is declared, then call it.
    3. If `autoname` property is set in the DocType (`meta`), then build it using the `autoname` property.
    4. If no rule defined, use hash.

    :param doc: Document to be named.
    """

    doc.run_method("before_naming")

    autoname = frappe.get_meta(doc.doctype).autoname or ""

    if autoname.lower() != "prompt" and not frappe.flags.in_import:
        doc.name = None

    if getattr(doc, "amended_from", None):
        _set_amended_name(doc)
        return

    elif getattr(doc.meta, "issingle", False):
        doc.name = doc.doctype

    else:
        doc.run_method("autoname")

    if not doc.name and autoname:
        set_name_from_naming_options(autoname, doc)

    # if the autoname option is 'field:' and no name was derived, we need to
    # notify
    if autoname.startswith('field:') and not doc.name:
        fieldname = autoname[6:]
        frappe.throw(_("{0} is required").format(
            doc.meta.get_label(fieldname)))

    if doc.name and autoname.lower() not in ("hash", "auto_increment") and ("#" not in autoname):
        doc.name = ' '.join(doc.name.split())

    # at this point, we fall back to name generation with the hash option
    if not doc.name or autoname == 'hash':
        doc.name = make_autoname('hash', doc.doctype)

    # Monkeypatch: Check for special character if to be disallowed-
    # read from site_config for sanitise_docnames = 1
    docnames_disallowed_chars = frappe.local.conf.get(
        "docnames_disallowed_chars")
    if docnames_disallowed_chars:
        string_check = re.compile(docnames_disallowed_chars)
        if string_check.search(doc.name):
            frappe.throw(
                f"{doc.name} contains special character. Not allowed list - {docnames_disallowed_chars}")

    doc.name = validate_name(
        doc.doctype,
        doc.name,
        frappe.get_meta(doc.doctype).get_field("name_case")
    )


naming.set_new_name = set_new_name
document.set_new_name = set_new_name
