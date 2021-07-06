// Copyright (c) 2020, Sachin Mane and contributors
// For license information, please see license.txt

function add_thumbnail_creator(frm) {
	frm.add_custom_button('Make Thumbnail', () => {
		frappe.call('latte.file_storage.file.make_thumbnail', {
			name: frm.doc.name,
		}).then(() => {
			frm.reload_doc();
		});
	});
	frm.add_custom_button('Remove Thumbnail', () => {
		frappe.call('latte.file_storage.file.remove_thumbnail', {
			name: frm.doc.name,
		}).then(() => {
			frm.reload_doc();
		});
	});
}

frappe.ui.form.on('Attachment', {
	refresh: function(frm) {
		add_thumbnail_creator(frm);
	}
});
