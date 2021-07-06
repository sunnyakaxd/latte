import frappe
from frappe import local
from frappe.website.doctype.website_theme.website_theme import WebsiteTheme

def clear_cache_if_current_theme(self):
	if local.flags.in_migrate or local.flags.in_install_app or local.flags.in_install:
		return

	website_settings = frappe.get_doc("Website Settings", "Website Settings")
	if getattr(website_settings, "website_theme", None) == self.name:
		website_settings.clear_cache()

WebsiteTheme.clear_cache_if_current_theme = clear_cache_if_current_theme