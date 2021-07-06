// Copyright (c) 2021, Sachin Mane and contributors
// For license information, please see license.txt

frappe.ui.form.on('PayPhi Payment Request', {
	refresh: function(frm) {
		transaction_status_update(frm);
	}
});


function transaction_status_update(frm) {
	frm.add_custom_button("Show Transaction Status", () => {
	  frappe.call({
	  method: 'latte.payment_gateway_integration.doctype.payphi_payment_request.payphi_payment_request.get_latest_txn_status',
	  args: {
			merchant_txn_no: frm.doc.name,
			merchant_id: frm.doc.merchant_id,
			original_txn_no: frm.doc.remote_txn_id,
			aggregator_id: frm.doc.aggregator_id,
		  },
	  freeze: true,
		  });
		}, 'Update Transaction Status');
	}
