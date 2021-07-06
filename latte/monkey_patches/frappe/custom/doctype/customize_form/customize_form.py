from frappe.custom.doctype.customize_form.customize_form import CustomizeForm, docfield_properties
from latte.business_process.powerflow.powerflow import Powerflow
from latte.business_process.constants import POWERFFLOW_CURRENT_STATE_FIELD

old_fetch_to_customize = CustomizeForm.fetch_to_customize

def fetch_to_customize(self):
	old_fetch_to_customize(self)
	if self.fields and Powerflow.is_enabled_for(self.doc_type):
		count = len(self.fields)
		i = -1
		while(i<count):
			i += 1
			if self.fields[i].fieldname == POWERFFLOW_CURRENT_STATE_FIELD:
				self.fields.pop(i)
				break

CustomizeForm.fetch_to_customize = fetch_to_customize

docfield_properties.update({
	'regex_pattern': 'Data',
})