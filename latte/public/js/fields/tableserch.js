frappe.ui.form.ControlTableSearch = frappe.ui.form.Control.extend({
	make: function() {
		this._super();

		const me = this;

		this.searchOn= this.df.options.split(".")[0];
		this.searchField = this.df.options.split(".")[1] || "name";

		// need to see if this can be shortened
		this.doctype = cur_frm.meta.fields.filter(fld => fld.fieldname === this.searchOn)[0].options;

		this.in_list_view = locals["DocType"][this.doctype].fields
			.filter(fld => fld.in_list_view)

		this.grid_view_fields = this.in_list_view.map(fld => fld.fieldname);
		this.grid_view_headers = this.in_list_view.map(fld => fld.label);
	
		this.html_element = 'input';
		this.$input = $("<"+ this.html_element +">")
			.attr("type", this.input_type)
			.attr("autocomplete", "off")
			.attr("placeholder", "Search Table")
			.addClass("input-with-feedback form-control")
			.css({"border": "1px solid"})
			.prependTo(this.wrapper)

		
		this.$content = $("<div class='content-area'> </div>");
		this.$content.appendTo(this.wrapper);

		this.$input.on("input", frappe.utils.debounce(function(e) {
			me.refresh_input(e.target.value);
		}, 200));
	},

	refresh_input: function(value) {
		let content = this.get_content(value);
		this.$content.html(content);
	},

	get_content: function(value) {
		if(!value) {
			return null;
		}

		let matchedRecords = cur_frm.doc[this.searchOn].filter(rec => 
			rec[this.searchField].toLowerCase().includes(value.toLowerCase())
		);

		if(!matchedRecords || !matchedRecords.length) {
			return this.get_default_html();
		}

		const table = this.prepareHTMLTableOfMatched(this.searchOn, this.searchField, matchedRecords);
		setTimeout(() => this.registerOnClick(this.searchOn), 100);

		return table;
	},

	get_default_html: function(value) {
		return `
			<table class="table table-bordered table-striped">
				<tr>
					<td> No Matching Rows </td>
				</tr>
			</table>
		`;
	},

	prepareHTMLTableOfMatched: function(formField, field, records) {
		return `
			<table class="table table-bordered table-striped">
				
				<tr>
					${this.grid_view_headers.map(hdr => `<th> ${hdr} </th>`).join("")}
				</tr>

				${records.map(rec => {
					return `
						<tr class="table-search-${formField}" data-idx=${rec['idx']} style="cursor: pointer">
							${this.grid_view_fields.map(fld => `<td> ${rec[fld]} </td>`).join("")}
						<tr>
						`
				}).join("")}
			</table>
		`
	},

	registerOnClick: function(field) {
		const me = this;
		this.$wrapper
			.find(`.table-search-${field}`)
			.each(function() {
				$(this).on('click', () => {
					me.$wrapper.parent()
						.find(`.frappe-control[data-fieldname='${field}']`)
						.find(`.grid-row[data-idx=${this.dataset.idx}]`)
						.find(`.octicon-triangle-down`)
						.click();
				})
			})

	}

});
