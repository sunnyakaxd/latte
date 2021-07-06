// Copyright (c) 2020, Sachin Mane and contributors
// For license information, please see license.txt

frappe.ui.form.on('Powerflow Configuration', {
	// refresh: function(frm) {
	// 	frm.events.make_select(frm);
	// },
	
	// make_select(frm) {
	// 	const allowed_states = [...new Set(frm.doc.states.map(i => i.state))];
	// 	const {state, to} = frm.fields_dict.transitions.grid.fields_map
	// 	state.fieldtype = to.fieldtype = 'Select';
	// 	state.options = to.options = allowed_states.join('\n');
	// 	frm.refresh_field('transitions');
	//   }
	
});

// frappe.ui.form.on('Powerflow State', {
// 	state(frm) {
// 	  frm.events.make_select(frm);
// 	},
// 	states_remove(frm) {
// 	  frm.events.make_select(frm);
// 	}
// });
  
