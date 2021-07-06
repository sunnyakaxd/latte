// Copyright (c) 2020, Sachin Mane and contributors
// For license information, please see license.txt

frappe.ui.form.on('Bulk Notification', {
	refresh(frm) {
		start_execution(frm)
	},
	on_submit(frm) {
		start_execution(frm)
		frm.refresh();	
	}	
});

function start_execution(frm) {
	var at = cur_frm.doc.initiation_details
	var log = $(frm.fields_dict["initiation_log"].wrapper).empty();
	$(frappe.render_template(at)).appendTo(log);
}
