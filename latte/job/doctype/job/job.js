// Copyright (c) 2020, Sachin Mane and contributors
// For license information, please see license.txt

frappe.ui.form.on('Job', {
	refresh: function(frm) {
		frm.add_custom_button('Retry Now', () => {
			frappe.call('latte.job.doctype.job.job.retry', {
				name: frm.doc.name,
			}).then(() => {
				frappe.msgprint('Retried');
			});
		});
	}
});
