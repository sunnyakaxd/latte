// Copyright (c) 2019, Sachin Mane and contributors
// For license information, please see license.txt

frappe.ui.form.on("Dashboard Data Slice", "onload_post_render", function (frm) {
	frappe.require('assets/frappe/js/lib/jscolor/jscolor.js', function () {
		$.each(['background_color', 'text_color'], function (i, v) {
			$(frm.fields_dict[v].input).addClass('color {required:false,hash:true}');
		});
        jscolor.bind();

        $(`<div>
                <span class="small control-label">User one of the Color Combinations below, by clicking on it.</span>
                <div class="row color-schemes" style="text-align: center; cursor: pointer;">
                    <div class="col-sm-3" data-bg="#cce5ff" data-c="#004085" style="padding:10px; color: #004085; background-color: #cce5ff;">Primary</div>
                    <div class="col-sm-3" data-bg="#e2e3e5" data-c="#383d41" style="padding:10px; color: #383d41; background-color: #e2e3e5;">Secondary</div>
                    <div class="col-sm-3" data-bg="#d4edda" data-c="#155724" style="padding:10px; color: #155724; background-color: #d4edda;">Success</div>
                    <div class="col-sm-3" data-bg="#f8d7da" data-c="#721c24" style="padding:10px; color: #721c24; background-color: #f8d7da;">Danger</div>
                    <div class="col-sm-3" data-bg="#fff3cd" data-c="#856404" style="padding:10px; color: #856404; background-color: #fff3cd;">Warning</div>
                    <div class="col-sm-3" data-bg="#d1ecf1" data-c="#0c5460" style="padding:10px; color: #0c5460; background-color: #d1ecf1;">Info</div>
                    <div class="col-sm-3" data-bg="#fefefe" data-c="#818182" style="padding:10px; color: #818182; background-color: #fefefe;">Light</div>
                    <div class="col-sm-3" data-bg="#d6d8d9" data-c="#1b1e21" style="padding:10px; color: #1b1e21; background-color: #d6d8d9;">Dark</div>
                </div>
            </div>`).appendTo($('#color-schemes'));

        $.each($('.color-schemes div'), (_, i) => {
            $(i).click((e) => {
                const _color = $(e.currentTarget).data();
                cur_frm.set_value('background_color', _color.bg);
                cur_frm.fields_dict.background_color.input.color.fromString(_color.bg);
                cur_frm.set_value('text_color', _color.c);
                cur_frm.fields_dict.text_color.input.color.fromString(_color.c);
            });
        });
	});
});

frappe.ui.form.on('Dashboard Data Slice', {
	refresh: function (frm) {

        const _def = ['multiple_ds', 'data_source', 'report', 'query', 'method', 'dashboard_datasource', 'join_field'];
        frm['ff'] = {
            all: ['dashboard_datasource', 'join_field', 'multiple_ds', 'data_source', 'report', 'query', 'method',
            'title', 'grid_title', 'grid_action', 'grid_download', 'grid_view_port',
            'html_template', 'js', 'filter', 'filter_config', 'filter_type', 'filter_parser',
            'filter_field', 'background_color', 'text_color', 'chart_type', 'chart_default_config'],
            count: _def.concat(['title', 'filter_parser', 'html_template',
                        'js', 'filter', 'background_color', 'text_color']),
            list: _def.concat(['title', 'grid_download', 'filter_parser', 'html_template',
                        'js', 'filter', 'background_color', 'text_color']),
            grid: _def.concat(['grid_title', 'title', 'grid_download', 'grid_view_port', 'grid_action',
                        'filter_parser', 'js', 'filter']),
            filter: _def.concat(['filter_config', 'filter_field', 'filter_type']),
            html: _def.concat(['title', 'html_template', 
                        'js', 'background_color', 'text_color']),
            chart: _def.concat(['title', 'filter_parser', 'js', 'filter', 'chart_type', 'chart_default_config']),
            map: _def.concat(['title', 'filter_parser', 'js', 'filter', 'chart_type', 'chart_default_config'])
        }

        frm.trigger('update_section_views');
        frm.trigger('update_slice_fields');
    },
    data_type: function(frm) {
        frm.trigger('update_section_views');
        frm.trigger('update_slice_fields');
    },
    module: function(frm) {
        frm.trigger('update_section_views');
    },
    data_slice_name: function(frm) {
        frm.trigger('update_section_views');
    },
    // reset: function(frm) {
    //     frm.trigger('update_section_views');
    //     frm.trigger('update_slice_fields');
    // },
    update_section_views: function(frm) {
        const sections = Array.prototype.filter.call(Object.keys(frm.fields_dict), (fld) => {
            return ['data_source_section', 'configuration', 'filters_section', 'miscellaneous'].indexOf(fld) > -1;
        }).map(fld => frm.fields_dict[fld]);
        // If DataSlice Name/ DataType & Module not selected - Hide the rest
        if (frappe.utils.is_empty(frm.doc.data_slice_name) || 
                frappe.utils.is_empty(frm.doc.data_type)) {
                    // Hide Data Sources && Hide Configuration && Hide Filters & Hide Misc
                    $.each(sections, (_, $sec) => {
                        $($sec.body).closest('.form-section').hide();
                    });
                    frm.trigger('reset_dependents');
                } else {
                    $.each(sections, (_, $sec) => {
                        $($sec.body).closest('.form-section').show();
                    });
                }
    },
    reset_dependents: function(frm) {
        $.each(frm.ff.all, 
                (_, fld) => {
            frm.set_value(fld, '');
            frm.set_df_property(fld, 'hidden', 1);
        });
        $(frm.get_field('add_filter').wrapper).empty();
    },
    update_slice_fields: function(frm) {
        let _hidefields = [];
        let _showfields = [];
        switch(frm.doc.data_type) {
            case 'Count': 
                _showfields = frm.ff.count;
                _hidefields = frm.ff.all.filter((f) => _showfields.indexOf(f) < 0);
                if (frappe.utils.is_empty(frm.doc.html_template)) {
                    frm.set_value("html_template", "<div><b>${obj.doc.name}</b></div>" +
				       "<div style='font-size: 60px; font-weight: 400;'>${obj.response.result[0][0] || '-'}</div>");
                }
                break;
            case 'List':
                _showfields = frm.ff.list;
                _hidefields = frm.ff.all.filter((f) => _showfields.indexOf(f) < 0);
                if (frappe.utils.is_empty(frm.doc.html_template)) {
                    frm.set_value("html_template", "<div><b>${obj.doc.name}</b></div>" +
				       "<div>${slice.response.result[0][0] || '-'}</div>");
                }
                break;
            case 'Grid':
                _showfields = frm.ff.grid;
                $(frm.fields_dict['miscellaneous'].body).closest('.form-section').hide();
                _hidefields = frm.ff.all.filter((f) => _showfields.indexOf(f) < 0);
                break;
            case 'HTML':
                _showfields = frm.ff.html;
                $(frm.fields_dict['data_source_section'].body).closest('.form-section').hide();
                $(frm.fields_dict['filters_section'].body).closest('.form-section').hide();
                _hidefields = frm.ff.all.filter((f) => _showfields.indexOf(f) < 0);
                break;
            case 'Chart':
                _showfields = frm.ff.chart;
                _hidefields = frm.ff.all.filter((f) => _showfields.indexOf(f) < 0);
                break;
            case 'Map':
                _showfields = frm.ff.map;
                _hidefields = frm.ff.all.filter((f) => _showfields.indexOf(f) < 0);
                break;
            case 'Filter':
                _showfields = frm.ff.filter;
                frm.trigger('show_filter_config');
                $(frm.fields_dict['miscellaneous'].body).closest('.form-section').hide();
                $(frm.fields_dict['configuration'].body).closest('.form-section').hide();
                _hidefields = frm.ff.all.filter((f) => _showfields.indexOf(f) < 0);
                break;
        }
        $.each(_hidefields, (_, fld) => { 
            frm.set_value(fld, '');
            frm.set_df_property(fld, 'hidden', 1);
        });
        $.each(_showfields, (_, fld) => {
            frm.set_df_property(fld, 'hidden', 0);
        });
        frm.trigger('data_source');
    },
    data_source: function (frm) {
        $.each(['Report', 'Method', 'Query'].filter((i) => i != frm.doc.data_source), (_, fl) => {
            frm.set_value(fl.toLowerCase(), '');
            frm.set_df_property(fl.toLowerCase(), 'hidden', 1);
        });
        frm.set_df_property(frm.doc.data_source.toLowerCase(), 'hidden', 0);
    },
	show_filter_config: function (frm) {
	 	var wrapper = $(frm.get_field('add_filter').wrapper);
	 	wrapper.empty();
	    var add_filter_btn = $(`<button class="btn btn-primary"> Add Filter </button>`).appendTo(wrapper);
	 	var filter_config_fields = [
	 		{
	 			'fieldtype': 'Select',
	 			'fieldname': 'fieldtype',
	 			'options': 'Check\nData\nDate\nDatetime\nDateRange\nFloat\nInt\nLink\nRead Only\nSelect\nTime',
	 			'label': 'Filter Type'
	 		},
	 		{
	 			'fieldtype': 'Data',
	 			'fieldname': 'label',
				'label': 'Filter Label'
			},
			{
				'fieldtype': 'Data',
				'fieldname': 'options',
				'label': 'Filter Options'
	 		},
	 	];

	 	add_filter_btn.on('click', function () {
			var dialog = new frappe.ui.Dialog({
	 			fields: filter_config_fields,
	 			title: "Add Filter",
	 			primary_action: function () {
					var values = this.get_values();
	 				if (values) {
	 					this.hide();
	 					frm.set_value('filter_config', JSON.stringify(values));
	 				}
	 			}
	 		});
			dialog.show();
			const values = JSON.parse(frm.doc.filter_config);
		})
	}

});
