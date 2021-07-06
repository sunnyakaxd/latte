// Copyright (c) 2020, Sachin Mane and contributors
// For license information, please see license.txt

this.frm.add_fetch('sender', 'email_id', 'sender_email');

this.frm.fields_dict.sender.get_query = function(){
	return {
		filters: {
			'enable_outgoing': 1
		}
	}
};

frappe.notification = {
	setup_fieldname_select(frm) {
		// get the doctype to update fields
		if(!frm.doc.document_type) {
			return;
		}

		frappe.model.with_doctype(frm.doc.document_type, function() {
			let get_select_options = function(df) {
				return {value: df.fieldname, label: df.fieldname + " (" + (df.label) + ")"};
			}

			let get_date_change_options = function() {
				let date_options = $.map(fields, function(d) {
					return (d.fieldtype=="Date" || d.fieldtype=="Datetime")?
						get_select_options(d) : null;
				});
				// append creation and modified date to Date Change field
				return date_options.concat([
					{ value: "creation", label: `creation (${('Created On')})` },
					{ value: "modified", label: `modified (${('Last Modified Date')})` }
				]);
			}

			let fields = frappe.get_doc("DocType", frm.doc.document_type).fields;
			let options = $.map(fields,
				function(d) { return in_list(frappe.model.no_value_type, d.fieldtype) ?
					null : get_select_options(d); });

			// set value changed options
			frm.set_df_property("value_changed", "options", [""].concat(options));
			frm.set_df_property("set_property_after_alert", "options", [""].concat(options));

			// set date changed options
			frm.set_df_property("date_changed", "options", get_date_change_options());

			let email_fields = $.map(fields,
				function(d) { return (d.options == "Email" ||
					(d.options=='User' && d.fieldtype=='Link')) ?
					get_select_options(d) : null; });

			// set email recipient options
			frappe.meta.get_docfield("Notification Recipient", "email_by_document_field",
				// set first option as blank to allow notification not to be defaulted to the owner
				frm.doc.name).options = [""].concat(["owner"].concat(email_fields));

			frm.fields_dict.recipients.grid.refresh();
		});
	}
}

async function setup_channels(frm) {
	const {message} = await frappe.call('latte.reminder_alert_and_notification.doctype.broadcast.broadcast.get_channel_list');
	frm.set_df_property('channel', 'options', message.join('\n'));
}

frappe.ui.form.on('Broadcast', {
	onload(frm) {
		frm.set_query("document_type", function() {
			return {
				"filters": {
					"istable": 0
				}
			}
		});
		frm.set_query("print_format", function() {
			return {
				"filters": {
					"doc_type": frm.doc.document_type
				}
			}
		});
	},

	refresh(frm) {
		setup_channels(frm);
		frm.toggle_reqd("recipients", frm.doc.channel=="Email");
		frappe.notification.setup_fieldname_select(frm);
		frm.get_field("is_standard").toggle(frappe.boot.developer_mode);
		frm.trigger('event');
		frappe.call({
			"method": "frappe.core.doctype.user.user.get_all_roles",
			"callback": function (r) {
				let roles = []
				r = r.message
				r.forEach(role => {
					roles.push(role)
				})
				roles.unshift("")
				frappe.meta.get_docfield("Receivers Template","role",frm.doc.name).options = roles;
			}
		})
	},

	document_type(frm) {
		frappe.notification.setup_fieldname_select(frm);
		frm.toggle_reqd("event",1)
	},

	view_properties(frm) {
		frappe.route_options = {doc_type:frm.doc.document_type};
		frappe.set_route("Form", "Customize Form");
	},

	event(frm) {
		if(in_list(['Days Before', 'Days After'], frm.doc.event)) {
			frm.add_custom_button(('Get Alerts for Today'), function() {
				frappe.call({
					method: 'latte.reminder_alert_and_notification.doctype.broadcast.broadcast.get_documents_for_today',
					args: {
						notification: frm.doc.name
					},
					callback: function(r) {
						if(r.message) {
							frappe.msgprint(r.message);
						} else {
							frappe.msgprint(('No alerts for today'));
						}
					}
				});
			});
		}
	},
});

