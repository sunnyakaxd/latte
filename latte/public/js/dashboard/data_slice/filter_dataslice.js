import Awesomplete from 'awesomplete';

latte.Dashboard.DataSlice.Filter = class DashboardFilterDataSlice extends latte.Dashboard.DataSlice {
    render() {
        super.render();
        let index = Array.prototype.indexOf.call(this.datamanager.data.response.columns || this.datamanager.data.response.keys, this.doc.filter_field);
        latte.dashboard.get_filters()[this.doc.name] = null;
        let that = this;
        
        this.doc.filter_type == 'Config' ? (() => {
            this.doc.filter_config = JSON.parse(this.doc.filter_config) || {};
            this.doc.filter_config.slice = this;
            latte.dashboard.filters[this.doc.name] = this.doc.filter_config;
        })(): (() => {
            latte.dashboard.filters[this.doc.name] = {
                fieldname: this.doc.filter_field,
                label: __(this.doc.name),
                fieldtype: 'ACSelect',
                slice: this
            }
        })();
        latte.dashboard.filters[this.doc.name]['change'] = function() {
            if (frappe.utils.is_empty(this.value))  return;
            that.on_filter_change(this.value, that.doc.data_slice_name);
            that.setup();
        }
    }

    setup($wrapper) {
        if (!$wrapper) {
            const _me = this;
            $wrapper = Array.prototype.filter.call(latte.dashboard.filter_dialog.fields_list || [], function(item) {
                return item.df.slice.doc.name == _me.doc.name; 
            });
            if($wrapper) $wrapper = $wrapper[0].wrapper; else return;
        }
        $wrapper = $($wrapper);
        (latte.dashboard.get_filters() || {})[this.doc.name] ? (() => {
            $wrapper.find('.filter-tag').remove();
            let $selfl = $(`<div class="filter-tag btn-group">
                <button class="btn btn-default btn-xs toggle-filter" title="Edit Filter">${latte.dashboard.get_filters()[this.doc.name]}</button>
                <button class="btn btn-default btn-xs remove-filter" title="Remove Filter">
                    <i class="fa fa-remove text-muted"></i>
                </button>
            </div>`).appendTo($wrapper.find('.form-group'));
            $wrapper.find('input').val(latte.dashboard.get_filters()[this.doc.name]);
            const _me = this;
            $selfl.find('.remove-filter').click(function() { 
                // latte.dashboard.remove_filters(_me.doc.name);
                $selfl.remove();
                $wrapper.find('input').val('');
                _me.on_filter_change('', _me.doc.data_slice_name);
            });
        })() : (() => {return;})();
    }

    on_filter_change(value, data_slice_name) {
        const old_value = latte.dashboard.get_filters()[data_slice_name];

        if(frappe.utils.is_empty(value)) {
            latte.dashboard.remove_filters({
                key: data_slice_name
            });
            return
        }
        if(old_value == value) return;

        if(Array.isArray(value) && Array.isArray(old_value))
            if(value.every(val => old_value.includes(val)))
                return;

        latte.dashboard.set_filters({
            key: data_slice_name,
            value: value
        });
        latte.dashboard.filter_triggered(data_slice_name);
    }

    prepare_container() {
        return;
    }
}


frappe.ui.form.ControlACSelect = frappe.ui.form.ControlData.extend({ 
    make_input: function() {
		var me = this;
		$('<div class="link-field ui-front" style="position: relative; line-height: 1;">\
			<input type="text" class="input-with-feedback form-control">\
			<span class="link-btn">\
				<a class="btn-open no-decoration" title="' + __("Open Link") + '">\
					<i class="octicon octicon-arrow-right"></i></a>\
			</span>\
		</div>').prependTo(this.input_area);
		this.$input_area = $(this.input_area);
		this.$input = this.$input_area.find('input');
		this.$link = this.$input_area.find('.link-btn');
		this.$link_open = this.$link.find('.btn-open');
		this.set_input_attributes();
		this.$input.on("focus", function() {
            me.awesomplete.list = me.get_autocomplete_results();
		});
		this.$input.on("blur", function() {
			// if this disappears immediately, the user's click
			// does not register, hence timeout
			setTimeout(function() {
				me.$link.toggle(false);
			}, 500);
		});
		this.input = this.$input.get(0);
		this.has_input = true;
		this.translate_values = true;
		this.setup_awesomeplete();
    },
    setup_awesomeplete: function() {
		var me = this;
		this.$input.cache = {};
		this.awesomplete = new Awesomplete(me.input, {
			minChars: 0,
			maxItems: 99,
			autoFirst: true,
			list: [],
			data: function (item) {
				return {
					label: item.label || item.value,
					value: item.value
				};
			},
			filter: function() {
				return true;
			},
			item: function (item) {
				var d = this.get_item(item.value);
				if(!d.label) {	d.label = d.value; }
                
				return $('<li></li>')
					.data('item.autocomplete', item)
					.prop('aria-selected', 'false')
					.html('<a><p>' + item + '</p></a>')
					.get(0);
			},
			sort: function() {
				return 0;
            }
        });

        this.awesomplete.get_item = function(value) {
            return this._list.find(function(item) {
                return item.value === value;
            });
        }      

		this.$input.on("input", frappe.utils.debounce(function(e) {
			var term = e.target.value;
            me.awesomplete.list = me.get_autocomplete_results(term); 
		}, 618));

		this.$input.on("blur", function() {
			if(me.selected) {
				me.selected = false;
				return;
			}
			var value = me.get_input_value();
			if(value!==me.last_value) {
				me.parse_validate_and_set_in_model(value);
			}
		});

		this.$input.on("awesomplete-open", function() {
			me.$wrapper.css({"z-index": 100});
			me.$wrapper.find('ul').css({"z-index": 100});
			me.autocomplete_open = true;
		});

		this.$input.on("awesomplete-close", function() {
			me.$wrapper.css({"z-index": 1});
			me.autocomplete_open = false;
		});

		this.$input.on("awesomplete-select", function(e) {
			var o = e.originalEvent;
			var item = me.awesomplete.get_item(o.text.value);

			me.autocomplete_open = false;

			// prevent selection on tab
			var TABKEY = 9;
			if(e.keyCode === TABKEY) {
				e.preventDefault();
				me.awesomplete.close();
				return false;
			}

			if(item.action) {
				item.value = "";
				item.action.apply(me);
			}

			// if remember_last_selected is checked in the doctype against the field,
			// then add this value
			// to defaults so you do not need to set it again
			// unless it is changed.
			if(me.df.remember_last_selected_value) {
				frappe.boot.user.last_selected_values[me.df.options] = item.value;
			}

			me.parse_validate_and_set_in_model(item.value);
		});

		this.$input.on("awesomplete-selectcomplete", function(e) {
			var o = e.originalEvent;
			if(o.text.value.indexOf("__link_option") !== -1) {
				me.$input.val("");
			}
		});
    },
    get_autocomplete_results: function(term) {
        let _ = this.df.slice.datamanager._data.response.result;
        if (!frappe.utils.is_empty(term)) {
            _ = Array.prototype.filter.call(this.df.slice.datamanager._data.response.result, function(item) {
                return item[0].toLowerCase().startsWith(term.toLowerCase());
            });
        }
        return Array.prototype.map.call(_, function(item) {
            return {
                label: item,
                value: item
            };
        })
    }

});








/**
 * TODO - Legacy Code
 */
latte.DashboardLegacy.DataSlice.Filter = class DashboardFilterDataSliceLegacy extends latte.DashboardLegacy.DataSlice {
    render() {
        super.render();

        //$('<div id="dashboard-filters"></div>').appendTo($('.layout-main-section'));
        let index = Array.prototype.indexOf.call(this.datamanager.data.response.columns || this.datamanager.data.response.keys, this.doc.filter_field);
        latte.dashboard.get_filters()[this.doc.name] = null;
        let that = this;

        if(this.doc.filter_type == 'Config') {
            let filter_conf = `latte.dashboard.filters["${this.doc.name}"] = ${this.doc.filter_config}`;

            frappe.dom.eval(filter_conf);

            if (!latte.dashboard.filters[this.doc.name]) {
                return;
            }

            const filter_field_conf = latte.dashboard.filters[this.doc.name];

            filter_field_conf['change'] = function() {
                that.on_filter_change(this.value, that.doc.data_slice_name);
            }

            this.control = this.make_control(filter_field_conf)

            if(latte.dashboard.get_filters()[this.doc.data_slice_name]){
                this.control.set_value(latte.dashboard.get_filters()[this.doc.data_slice_name]);
                // this.control.$input.trigger('change')
            }

        } else {
            this.control = this.make_control({
                fieldname: this.doc.filter_field,
                label: __(this.doc.filter_field),
                fieldtype: 'Select',
                options: this.datamanager.data.response != undefined
                    ? [''].concat(Array.from(new Set(this.datamanager.data.response.result.map(item => item[index])))) :
                    [''].concat(Array.from(new Set(this.datamanager.data.response.values.map(item => item[index])))),
                reqd: 1,
                change() {
                    const old_value = latte.dashboard.get_filters()[that.doc.data_slice_name];
                    if(old_value == this.value) return;

                    latte.dashboard.set_filters({
                        key: that.doc.data_slice_name,
                        value: this.value
                    });
                    $(document).trigger('data-attribute-changed', [that.doc.data_slice_name]);
                },
            });
        }
        eval(this.doc.js || '');
        this.load_selection();
    }

    make_control(df) {
        var f = frappe.ui.form.make_control({
            df: df,
            parent: this.chart_container,
            only_input: df.fieldtype=="Check" ? false : true,
        })
        f.refresh();
        $(f.wrapper)
            .addClass('col-md-2')
            .attr("title", __(df.label)).tooltip();

        // html fields in toolbar are only for display
        if (df.fieldtype=='HTML') {
            return;
        }

        // hidden fields dont have $input
        if (!f.$input) f.make_input();

        f.$input.addClass("input-sm").attr("placeholder", __(df.label));

        if(df.fieldtype==="Check") {
            $(f.wrapper).find(":first-child")
                .removeClass("col-md-offset-4 col-md-8");
        }

        if(df.fieldtype=="Button") {
            $(f.wrapper).find(".page-control-label").html("&nbsp;")
            f.$input.addClass("btn-sm").css({"width": "100%", "margin-top": "-1px"});
        }

        if(df["default"])
            f.set_input(df["default"])
        //this.fields_dict[df.fieldname || df.label] = f;
        return f;
    }

    on_filter_change(value, data_slice_name) {
        const old_value = latte.dashboard.get_filters()[data_slice_name];

        if(frappe.utils.is_empty(value)) {
            latte.dashboard.remove_filters({
                key: data_slice_name
            });
        }
        if(old_value == value) return;

        if(Array.isArray(value) && Array.isArray(old_value))
            if(value.every(val => old_value.includes(val)))
                return;

        latte.dashboard.set_filters({
            key: data_slice_name,
            value: value
        });
        $(document).trigger('data-attribute-changed', [data_slice_name]);
    }

    prepare_container() {
        let class_name = this.doc.name.replace(/ /g, '');
        this.chart_container = $(`<div class="chart-column-container-filter">
            <div class="data-wrapper data-wrapper-${class_name}">
            </div>
        </div>`);
        if (this.container)
            this.chart_container.appendTo(this.container);
        let last_synced_text = $(`<span class="last-synced-text"></span>`);
        last_synced_text.prependTo(this.chart_container);
        if (this.container)
            this.chart_container.appendTo(this.container.find('.page-form'));
        if (this.container.hasClass('filter-form'))
            this.container.css('padding','0');
    }

    load_selection() {
        if (Object.hasOwnProperty.call(latte.dashboard.get_filters(), this.doc.name)) {
            let filter = latte.dashboard.get_filters()[this.doc.name];
            if (!frappe.utils.is_empty(filter)){
                undefined != this.control.input ?
                    $(this.control.input).val(filter):
                    $(this.control).val(filter);
                    // this.control.$input.trigger('change')
            }
        }
    }
}