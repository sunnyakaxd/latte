// Copyright (c) 2020, Sachin Mane and contributors
// For license information, please see license.txt

frappe.ui.form.on('Permission', {
	refresh: function(frm) {
		frm.set_df_property("doc_type", "read_only", frm.doc.__islocal ? 0 : 1);
		frm.set_df_property("role", "read_only", frm.doc.__islocal ? 0 : 1);
		frm.set_df_property("permlevel", "read_only", frm.doc.__islocal ? 0 : 1);
	}
});
