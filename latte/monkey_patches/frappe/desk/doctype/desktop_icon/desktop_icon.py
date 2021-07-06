import frappe
from frappe.desk.doctype.desktop_icon import desktop_icon
from frappe.desk.doctype.desktop_icon.desktop_icon import get_desktop_icons
from latte.utils.caching import cache_me_if_you_can


old_get_desktop_icons = desktop_icon.get_desktop_icons

def patched_get_desktop_icons(user=None):
    if not user:
        user = frappe.session.user

    icons = cached_desktop_icons(user)
    modules = {row.module_name for row in icons}
    for icon in "Setup", "Core":
        if icon not in modules:
            icons.append(frappe._dict({'module_name': icon}))

    return icons


cached_desktop_icons = cache_me_if_you_can(key=lambda u=None: (u, 3600))(old_get_desktop_icons)

desktop_icon.get_desktop_icons = patched_get_desktop_icons
