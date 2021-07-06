import frappe

def create_payment_request(ref_dt, ref_dn, amount, merchant_id):
	payphi_controller = frappe.get_doc('PayPhi Settings', 'PayPhi Settings')
	present = frappe.db.get_value('PayPhi Payment Request', {'reference_docname':ref_dn, 'reference_doctype':ref_dt, 'expired':0})
	if present:
		frappe.throw(f'Payment Request is already created for this document. Please check <b><a href="/desk#Form/PayPhi Payment Request/{present}">{present}</a><b>')
	payphi_controller.create_payment_request(ref_dt, ref_dn, amount, merchant_id)