import frappe.installer
from frappe.installer import (
	getpass,
	print_db_config,
	expected_config_for_barracuda_3,
	remove_from_installed_apps,
	make_site_config
)
from latte.database_utils.connection_pool import PatchedDatabase
import latte
from frappe import local

def get_root_connection(root_login='root', root_password=None):
	if not frappe.local.flags.root_connection:
		if root_login:
			if not root_password:
				root_password = frappe.conf.get("root_password") or None

			if not root_password:
				root_password = getpass.getpass("MySQL root password: ")
		frappe.local.flags.root_connection = PatchedDatabase(
			user=root_login,
			password=root_password,
			use_db=False,
		)


	return frappe.local.flags.root_connection

def check_database(mariadb_variables, variables_dict):
	for key, value in variables_dict.items():
		if (db_val := mariadb_variables.get(key)) != value:
			print(f'Variable "{key}" is "{db_val}" but expected "{value}"')
			site = frappe.local.site
			msg = ("Creation of your site - {x} failed because MariaDB is not properly {sep}"
				   "configured to use the Barracuda storage engine. {sep}"
				   "Please add the settings below to MariaDB's my.cnf, restart MariaDB then {sep}"
				   "run `bench new-site {x}` again.{sep2}"
				   "").format(x=site, sep2="\n"*2, sep="\n")

			print_db_config(msg, expected_config_for_barracuda_3)
			raise frappe.exceptions.ImproperDBConfigurationError(
				reason="MariaDB default file format is not Barracuda"
			)

def remove_app(app_name, dry_run=False, yes=False):
	from pymysql.err import InternalError, OperationalError
	"""Delete app and all linked to the app's module with the app."""

	if not dry_run and not yes:
		confirm = input("All doctypes (including custom), modules related to this app will be deleted. Are you sure you want to continue (y/n) ? ")
		if confirm!="y":
			return

	from frappe.utils.backups import scheduled_backup
	print("Backing up...")
	scheduled_backup(ignore_files=True)

	drop_doctypes = []
	frappe.local.flags.in_install_app = True

	# remove modules, doctypes, roles
	for module_name in frappe.get_module_list(app_name):
		for doctype in frappe.get_list("DocType", filters={"module": module_name},
			fields=["name", "issingle"]):
			print("removing DocType {0}...".format(doctype.name))

			if not dry_run:
				frappe.delete_doc("DocType", doctype.name, force=True)

				if not doctype.issingle:
					drop_doctypes.append(doctype.name)

		# remove reports, pages and web forms
		for doctype in ("Report", "Page", "Web Form"):
			for record in frappe.get_list(doctype, filters={"module": module_name}):
				print("removing {0} {1}...".format(doctype, record.name))
				if not dry_run:
					frappe.delete_doc(doctype, record.name, force=True)

		print("removing Module {0}...".format(module_name))
		if not dry_run:
			frappe.delete_doc("Module Def", module_name, force=True)

	# delete desktop icons
	frappe.db.sql('delete from `tabDesktop Icon` where app=%s', app_name)

	remove_from_installed_apps(app_name)

	if not dry_run:
		# drop tables after a commit
		frappe.db.commit()

		for doctype in set(drop_doctypes):
			try:
				frappe.db.sql("drop table `tab{0}`".format(doctype))
			except (InternalError, OperationalError) as e:
				if e.args[0] == 1051:
					pass

def add_module_defs(app):
	modules = frappe.get_module_list(app)
	for module in modules:
		if frappe.db.get_value('Module Def', module):
			continue

		d = frappe.new_doc("Module Def")
		d.app_name = app
		d.module_name = module
		d.save(ignore_permissions=True)

def make_conf(db_name=None, db_password=None, site_config=None):
	site = frappe.local.site
	make_site_config(db_name, db_password, site_config)
	sites_path = frappe.local.sites_path
	latte.destroy()
	latte.init(site, sites_path=sites_path, force=True)

frappe.installer.remove_app = remove_app
frappe.installer.add_module_defs = add_module_defs
frappe.installer.init_singles = lambda : True
frappe.installer.get_root_connection = get_root_connection
frappe.installer.check_database = check_database
frappe.installer.make_conf = make_conf
