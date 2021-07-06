
frappe.provide("latte.dashboard_theme");
$.extend(latte.dashboard_theme, {
	color_variables: ["background_color", 
		"footer_color", "footer_text_color",  
		"top_bar_color", "top_bar_text_color",
		"text_color", "link_color"]
});

frappe.ui.form.on("Dashboard Theme", "onload_post_render", function(frm) {
	frappe.require('assets/frappe/js/lib/jscolor/jscolor.js', function() {
		$.each(latte.dashboard_theme.color_variables, function(i, v) {
			$(frm.fields_dict[v].input).addClass('color {required:false,hash:true}');
		});
		jscolor.bind();
	});
});