// Copyright (c) 2020, Sachin Mane and contributors
// For license information, please see license.txt

function add_fixer(frm) {
	frm.add_custom_button('Reset', () => {
		frappe.call('latte.latte_dev_utils.doctype.autoincrement_refresh.autoincrement_refresh.reset', {
			name: frm.doc.name,
		}).then(() => {
			frm.reload_doc();
		})
	})
}

frappe.ui.form.on('Autoincrement Refresh', {
	refresh: function(frm) {
		add_fixer(frm)
	}
});
