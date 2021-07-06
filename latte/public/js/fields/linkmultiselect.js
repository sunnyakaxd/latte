import Awesomplete from 'awesomplete';

/**
 * Class representing a Mutli Select for Link Fields.
 * @extends frappe.ui.form.ControlAutocomplete
 *
 * Options to provide
 * M - Mandatory, O - Optional
 * - "options"(M): Doctype name for link, it is mandatory
 * - "parsist"(O): Will persist the value entered after selecting an option otherwise blank
 * - "filters"(O): any other filters if needed(filters on name will not be applied)
 *
 * Currently not supported
 * Link validation - It does not link validation unlike link fields, use it accordinly
 */
frappe.ui.form.ControlLinkMultiSelect = frappe.ui.form.ControlAutocomplete.extend({
	make: function() {
		this._super();
	},

	/**
	 * Binds functions on events
	 * Events 
	 * - focus 
	 * - input
	 */
	make_input: function() {
		var me = this;
		this._super();
		me.set_autocomplete_data();
		this.$input.on("focus", function() {
			
			if(!me.awesomplete.isOpened) {
				me.set_autocomplete_data();
				me.awesomplete.open();
			}
		});

		this.$input.on("blur", function() {
			
			me.awesomplete.close();
		});

		this.$input.on("awesomplete-select", function(e) {
			setTimeout(() => {
				if(!me.awesomplete.isOpened) {
					me.set_autocomplete_data();
					me.awesomplete.open();
				}
			}, 100)

			me.append_value = me.search_txt;
		})

		this.$input.on("input", frappe.utils.debounce(function(e){
			me.set_autocomplete_data();
		}, 618))


	},

	get_awesomplete_settings() {
		const settings = this._super();

		return Object.assign(settings, {
			filter: function(text, input) {
				let d = this.get_item(text.value);
				if(!d) {
					return Awesomplete.FILTER_CONTAINS(text, input.match(/[^,]*$/)[0]);
				}

				let getMatch = value => Awesomplete.FILTER_CONTAINS(value, input.match(/[^,]*$/)[0]);

				// match typed input with label or value or description
				let v = getMatch(d.label);
				if(!v && d.value) {
					v = getMatch(d.value);
				}
				if(!v && d.description) {
					v = getMatch(d.description);
				}

				return v;
			},

			replace: function(text) {
				const before = this.input.value.match(/^.+,\s*|/)[0];
				this.input.value = before + text + ", ";
			}
		});
	},

	/**
	 * Gets value as it is from the field
	 * Will be returned as comma saperated string
	 */	
	get_value() {
		let data = this._super();
		// find value of label from option list and return actual value string
		if (this.df.options && this.df.options.length && this.df.options[0].label) {
			data = data.split(',').map(op => op.trim());
			data = data.map(val => {
				let option = this.df.options.find(op => op.label === val);
				return option ? option.value : null;
			}).filter(n => n != null).join(', ');
		}
		return data;
	},

	/**
	 * Sets input
	 * if persist flag is provided, sets input as selected options + previous input
	 */		
	set_formatted_input(value) {
		const me = this;
		if (!value) return;
		// find label of value from option list and set from it as input
		if (this.df.options && this.df.options.length && this.df.options[0].label) {
			value = value.split(',').map(d => d.trim()).map(val => {
				let option = this.df.options.find(op => op.value === val);
				return option ? option.label : val;
			}).filter(n => n != null).join(', ');
		}

		
		if(this.df.persist) {
			value = value + me.append_value;
			me.append_value = '';
		}
		this._super(value);
	},

	set_value(value) {
		$(this.$input[0]).val(value);
	},

	/**
	 * Returns value as array
	 */		
	get_values() {
		const value = this.get_value() || '';
		const values = value.split(/\s*,\s*/).filter(d => d);

		return values;
	},

	/**
	 * Calls api to get the values
	 */	
	set_autocomplete_data() {
	// get_data() {
		const me = this;
		if (!this.df.options) {
			frappe.throw(`Please provide DocType in options for - ${this.df.fieldname}`)
		}

		let data;
		
		let values = this.get_value().split(",").map(val => val.trim());
		let txt = "";
		let already_selected = [];


		if(values.length) {
			txt = values.pop();
			already_selected = values; 
		}

		this.search_txt = txt;

		let filters = {
			"name": ["not in", already_selected]
		}

		if(this.df.filters) {
			filters = {...this.df.filters, ...filters}
		}
		
		frappe.call({
			type: "GET",
			method:'frappe.desk.search.search_link',
			async: false,
			no_spinner: true,
			args: {
				doctype: this.df.options,
				txt: txt,
				filters: filters
			},
			callback: function(r) {
				data = r.results;
				me.set_data(data)
			}
		});
		return data;		
	}
});


if(Awesomplete) {
	Awesomplete.prototype.get_item = function(value) {
		return this._list.find(function(item) {
			return item.value === value;
		});
	};
}