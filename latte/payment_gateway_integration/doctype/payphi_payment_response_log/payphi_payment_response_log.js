// Copyright (c) 2021, Sachin Mane and contributors
// For license information, please see license.txt

frappe.ui.form.on('PayPhi Payment Response Log', {
	refresh: function(frm) {
		frm.add_custom_button('Retry', () => {
			frappe.call('latte.payment_gateway_integration.doctype.payphi_payment_response_log.payphi_payment_response_log.retry', {
				doc: frm.doc,
			})
		})
		if (frm.doc.error_log) {
			frm.set_intro(`
				Last Error:
				<a target="_" href="/desk#Form/Error Log/${frm.doc.error_log}">
					${frm.doc.error_log}
				</a>
			`)
		}
	}
});