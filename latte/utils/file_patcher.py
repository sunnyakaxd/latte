import frappe.handler
import glob
from hashlib import md5
import os

def patch(import_call, method_name, method):
	if not os.path.exists('../patch_files/'):
		os.mkdir('../patch_files/')

	patch_list_file = md5(f'{import_call}|{method_name}'.encode()).hexdigest()
	# print('Trying', import_call, method_name, patch_list_file)
	try:
		with open(f'../patch_files/{patch_list_file}', 'r') as f:
			modules_to_patch = f.read().split('\n')
	except FileNotFoundError:
		generate_patch_file(import_call, patch_list_file)
		return patch(import_call, method_name, method)

	for module in modules_to_patch:
		if not (module and module.strip()):
			continue
		try:
			# print('Patching', module, 'for', method_name)
			module = frappe.get_module(module)
			setattr(module, method_name, method)
		except (ModuleNotFoundError, ImportError):
			pass

def generate_patch_file(import_call, patch_list_file):
	modules = []
	for file_name in glob.iglob('../apps/**/*.py', recursive=True):
		with open(file_name, 'r') as f:
			if validate_module(import_call, f):
				module_name = '.'.join(file_name.split('/')[3:])[:-3]
				modules.append(module_name)

	with open(f'../patch_files/{patch_list_file}', 'w') as f:
		f.write('\n'.join(modules))

def validate_module(import_call, f):
	for line in f:
		if import_call in line:
			return True