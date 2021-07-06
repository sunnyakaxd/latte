import DataManager from './binding/datamanager.js';

latte.Dashboard.DataSlice = class GenericDashboardDataSlice {
	constructor(slice_doc, link, slice_container) {
		this.doc = slice_doc;
		this.link = link;
		this.container = slice_container;
		this.config = {
			'data_source': 'single',
			'dom_binding': 'sync' // sync/async
	  	}
		return this;
	}

	update_config() {}

	prepare_container() {
		let columns = this.link.col_span;//column_width_map['Half'];
		let rows = this.link.row_span;
		let class_name = this.link.slice_name.replace(/ /g, '');
		this.chart_container = $(`<div class="chart-column-container">
			<div class="chart-wrapper chart-wrapper-${class_name || this.link.name}">
				<div class="lds-ellipsis chart-loading-state"><div></div><div></div><div></div><div></div></div>
				<div class="chart-filter-dependent hide " style="color:grey">
					<div class="glyphicon glyphicon-comment"></div>
					<div>${__("Slice is Filter Dependent")}</div>
				</div>
				<div class="chart-empty-state hide " style="color:grey" >
					<div class="glyphicon glyphicon-check"></div>
					<div>${__("Nothing to Show.")}</div>
				</div>
				<div class="chart-error hide ">
					<div class="glyphicon glyphicon-exclamation-sign"></div>
					<div>${__("Something's gone wrong!")}</div>
				</div>
				<div class="chart-perm-err hide ">
					<div class="glyphicon glyphicon-ban-circle"></div>
					<div>${__("You do not have access!")}</div>
				</div>
			</div>
			<div class="data-header-wrapper">
				<div class="row">
					<div class="title col-md-6"></div>
					<div class="text-right buttons col-md-6"></div>
				</div>
			</div>
			<div class="data-wrapper data-wrapper-${class_name || this.link.name}">
			</div>
		</div>`);
		this.chart_container.chart_wrapper = this.chart_container.find('.chart-wrapper');
		this.chart_container.data_header_wrapper = this.chart_container.find('.data-header-wrapper');
		this.chart_container.data_wrapper = this.chart_container.find('.data-wrapper');

		this.data_header = latte.Dashboard.DataSlice.DataHeader[this.doc.data_type] ?
			new latte.Dashboard.DataSlice.DataHeader[this.doc.data_type](this, this.chart_container.data_header_wrapper):
			new latte.Dashboard.DataSlice.DataHeader(this, this.chart_container.data_header_wrapper);
		// Setting Header Title
		this.data_header.set_title();

		if (this.container)
			this.chart_container.appendTo(this.container);
		let last_synced_text = $(`<span class="last-synced-text"></span>`);
		last_synced_text.prependTo(this.chart_container);
	}

	refresh() {
		if (!this.filter_dependency()) {
			let result = this.fetch_results();
			let is_err = (res) => {
				if ("Success" != res.status) {
					res.status == 'Permission Error'? this.is_permerr(true): this.is_err(true);
					return true;
				}
				return false;
			}
			switch (`${this.config.dom_binding}`) {
				case 'sync':
					result.forEach((r) => {
						r.req.then((res) => {
							if(!is_err(res)) {
								this.datamanager = new DataManager({
									'resp': res,
									'ds': r.ds
								});
								this.render();
								this.is_loading(false);
							}
						});
					});
					break;
				case 'async':
					result.forEach((r) => {
						r.req.then((resp) => {
							if(!is_err(resp)) {
								let obj = {
									'resp': resp,
									'ds': r.ds
								};
								!this.datamanager ?
									(() => {
										this.datamanager = new DataManager(obj, {
										'type': 'multiple',
										'joinField': this.doc.join_field
									})})():
									(() => {
										this.datamanager.data = obj
									})();
								this.binding_model.data = this.datamanager.data;
								this.is_loading(false);
							}
						});
					});
					this.render();
					break;
				default:
					break;
			}

		}
	}

	filter_dependency() {
		let is_dependent = false;
		this.doc.filter && this.doc.filter.forEach((c) => {
			if(c.is_required && frappe.utils.is_empty(latte.dashboard.get_filters()[c.filter_data_slice])) {
				is_dependent = true;
			}
		});
		return is_dependent ?
			(() => {
				this.is_filter_dependent(is_dependent);
				return is_dependent;
			})(): is_dependent;
	}

	fetch_results() {
		this.is_loading(true);
		let invoke = (data_source) => {
			return {
				req: this._funnel_requests(data_source),
				ds: data_source
			}
		}
		const ds = this.config.data_source == 'single'? [this.doc.dashboard_datasource[0]]:
				this.doc.dashboard_datasource;
		return Array.prototype.map.call(ds,
				(ds) => invoke(ds.data_source_name));
	}

	/**
	 * Method will pass DataSlice requests to be execute.
	 * If same requests accross DS are to be executed, a hook on promise to be created
	 * on previous pending resolution.
	 */
	_funnel_requests(data_source) {
		// Tracking Unique Request Call
		let _name;
		const _get_ds = (doc, type) => {

			switch(type) {
				case 'Report':
					return `Report-${doc.report}`;
					break;
				case 'Method':
					return `Method-${doc.method}`;
					break;
				case 'Query':
					return `Query-${(() => {
						const _ = doc.query.replace(/[\s\n]/g, '').toLowerCase();
						let __name = _.length;
						return __name + Array.from(_).reduce((a, c) =>
							typeof a === 'string' || a instanceof String? a.charCodeAt(0): a + c.charCodeAt(0));
					})()}`;
					break;
			}
		}
		const ds = (Array.prototype.filter.call(this.doc.dashboard_datasource, function(f) {
			return f.data_source_name == data_source
		}) || [])[0];
		_name = _get_ds(ds, ds.data_source);

		let pexec = latte.dashboard._pending_executions[_name];
		let _call;
		const _resp = new Promise((resolve) => {
			_call = resolve;
		})
		if (pexec) {
			latte.dashboard._pending_executions[_name].cb.push(
				_call
			);
			return _resp;
		} else {
			let method = 'latte.dashboard.doctype.dashboard_data_slice.run';
			const _req = frappe.xcall(
				method,
				{
					filters: latte.dashboard.get_filters(),
					slice_name: this.doc.name,
					data_source_name: data_source
				},
				true,
				'GET',
			)
			latte.dashboard._pending_executions[_name] = {
				promise: _req,
				cb: [_call]
			};
			latte.dashboard._pending_executions[_name].promise
				.then(res => {
					$.each(latte.dashboard._pending_executions[_name].cb, function(i, cb) {
						cb(JSON.parse(JSON.stringify(res)));
					});
					delete latte.dashboard._pending_executions[_name];
				});
			return _resp;
		}
	}

	fetch(filters, refresh = false) {
		this.is_loading(true);
		let method = 'latte.latte.doctype.dashboard_configuration.run';
		return frappe.xcall(
			method,
			{
				dashboard_name: this.dashboard_name,
				filters: {}
			}
		);
	}

	render() {
		this.is_loading(false);
	}

	run_post_js() {
		eval(`(() => {
			let dashboard = latte.dashboard;
			let slice = this;
			${this.doc.js || ''}
		})()`);
	}

	has_permission() {
		if(this.datamanager.data.status == "Success")
			return true;
		this.is_permerr(true);
	}

	is_loading(flag) {
		let _ = this.container.find('.chart-loading-state');
		flag ?
		(() => {_.show(); this.alter_datawrapper('add', 'data-wrapper', 'load')})():
		(() => {_.hide(); this.alter_datawrapper('remove', 'data-wrapper', 'load')})();
	}

	is_filter_dependent(flag) {
		flag ?
		(() => { this.alter_datawrapper('remove', 'chart-filter-dependent', 'hide'); this.is_loading(false); this.alter_datawrapper('add', 'data-wrapper', 'load')})():
		(() => { this.alter_datawrapper('add', 'chart-filter-dependent', 'hide'); this.alter_datawrapper('remove', 'data-wrapper', 'load')})();
	}

	is_empty(flag) {
		flag ?
		(() => { this.alter_datawrapper('remove', 'chart-empty-state', 'hide'); this.is_loading(false); this.alter_datawrapper('add', 'data-wrapper', 'hide')})():
		(() => { this.alter_datawrapper('add', 'chart-empty-state', 'hide'); this.alter_datawrapper('remove', 'data-wrapper', 'hide')})();
	}

	is_err(flag) {
		flag ?
		(() => { this.alter_datawrapper('remove', 'chart-error', 'hide'); this.is_loading(false); this.alter_datawrapper('add', 'data-wrapper', 'hide')})():
		(() => { this.alter_datawrapper('add', 'chart-error', 'hide'); this.alter_datawrapper('remove', 'data-wrapper', 'hide')})();
	}

	is_permerr(flag) {
		let _ = $(this.container).find('.chart-perm-err');
		flag ?
			(() => { this.alter_datawrapper('remove', 'chart-perm-err', 'hide'); this.is_loading(false); this.alter_datawrapper('add', 'data-wrapper', 'hide')})():
			(() => { this.alter_datawrapper('add', 'chart-perm-err', 'hide'); this.alter_datawrapper('remove', 'data-wrapper', 'hide')})();
	}

	alter_datawrapper(df, fnd, cls) {
		if ((() => ['add', 'remove'].indexOf(df) > -1)())
			this.container.find(`.${fnd}`)[(df + 'Class')](cls);
	}
}

/**
 * TODO - Legacy Code
 */
latte.DashboardLegacy.DataSlice = class GenericDashboardDataSliceLegacy extends latte.Dashboard.DataSlice {
	prepare_container() {
		let columns = this.link.col_span;//column_width_map['Half'];
		let rows = this.link.row_span;
		let class_name = this.link.slice_name.replace(/ /g, '');
		this.chart_container = $(`<div class="col-sm-${columns} chart-column-container">
			<div class="chart-wrapper chart-wrapper-${class_name}">
				<div class="chart-loading-state loader"></div>
				<div class="chart-filter-dependent hide " style="color:grey">${__("This slice is dependent on Filter")}</div>
				<div class="chart-empty-state hide " style="color:grey" >${__("This slice has no data currently")}</div>
				<div class="chart-error hide ">${__("Error Occurred")}</div>
				<div class="chart-perm-err hide ">${__("Permission Denied")}</div>
			</div>
			<div class="data-header-wrapper">
			</div>
			<div class="data-wrapper data-wrapper-${class_name}">
			</div>
		</div>`);
		if (rows > 0)
			this.chart_container.css({ "height": rows, 'overflow-y': 'auto' });
		if (this.container)
			this.chart_container.appendTo(this.container);
		let last_synced_text = $(`<span class="last-synced-text"></span>`);
		last_synced_text.prependTo(this.chart_container);
	}
	refresh() {
		if (!this.filter_dependency()) {
			let result = this.fetch_results();
			let is_err = (res) => {
				if ("Success" != res.status) {
					res.status == 'Permission Error'? this.is_permerr(true): this.is_err(true);
					return true;
				}
				return false;
			}
			switch (`${this.config.dom_binding}_${frappe.scrub(this.doc.multiple_ds == 0? 'Single': 'Multiple')}`) {
				case 'sync_single':
					result[0].req.then((res) => {
						if(!is_err(res)) {
							this.datamanager = new DataManager({
								'resp': res,
								'ds': result[0].ds
							});
							this.render();
							this.is_loading(false);
						}
					});
					break;
				case 'async_single':
					result[0].req.then(res => {
						if(!is_err(res)) {
							this.datamanager = new DataManager({
								'resp': res,
								'ds': result[0].ds
							});
							this.binding_model.data = this.datamanager.data;
							this.is_loading(false);
						}
					});
					this.render();
					break;
				case 'async_multiple':
					result.forEach(res => {
						res.req.then((resp) => {
							if(!is_err(resp)) {
								let obj = {
									'resp': resp,
									'ds': res.ds
								};
								!this.datamanager ?
									(() => {
										this.datamanager = new DataManager(obj, {
										'type': 'multiple',
										'joinField': this.doc.join_field
									})})():
									(() => {
										this.datamanager.data = obj
									})();
								this.binding_model.data = this.datamanager.data;
								this.is_loading(false);
							}
						});
					});
					this.render();
					break;
				default:
					break;
			}

		}
	}

	fetch_results() {
		this.is_loading(true);
		// Is single/ multiple sources supported
		if(this.config.data_source == 'single' && this.doc.multiple_ds == 1)
			frappe.throw(`Multiple Reports not supported for Report - ${this.doc.name}`);

		let invoke = (data_source) => {
			return {
				req: this._funnel_requests(data_source),
				ds: data_source
			}
		}
		if (this.doc.multiple_ds)
			return Array.prototype.map.call(this.doc.dashboard_datasource,
				(ds) => invoke(ds.data_source_name));
		return [invoke()];
	}

	/**
	 * Method will pass DataSlice requests to be execute.
	 * If same requests accross DS are to be executed, a hook on promise to be created
	 * on previous pending resolution.
	 */
	_funnel_requests(data_source) {
		// Tracking Unique Request Call
		let _name;
		const _get_ds = (doc, type) => {

			switch(type) {
				case 'Report':
					return `Report-${doc.report}`;
					break;
				case 'Method':
					return `Method-${doc.method}`;
					break;
				case 'Query':
					return `Query-${(() => {
						const _ = doc.query.replace(/[\s\n]/g, '').toLowerCase();
						let __name = _.length;
						return __name + Array.from(_).reduce((a, c) =>
							typeof a === 'string' || a instanceof String? a.charCodeAt(0): a + c.charCodeAt(0));
					})()}`;
					break;
			}
		}
		this.doc.multiple_ds ? (() => {
			const ds = (Array.prototype.filter.call(this.doc.dashboard_datasource, function(f) {
				return f.data_source_name == data_source
			}) || [])[0];
			_name = _get_ds(ds, ds.data_source);
		})(): (() => {
			_name = _get_ds(this.doc, this.doc.data_source);
		})();

		let pexec = latte.dashboard._pending_executions[_name];
		let _call;
		const _resp = new Promise((resolve) => {
			_call = resolve;
		})
		if (pexec) {
			latte.dashboard._pending_executions[_name].cb.push(
				_call
			);
			return _resp;
		} else {
			let method = 'latte.dashboard.doctype.dashboard_data_slice.run';
			const _req = frappe.xcall(
				method,
				{
					filters: latte.dashboard.get_filters(),
					slice_name: this.doc.name,
					data_source_name: data_source
				},
				true,
				'GET',
			)
			latte.dashboard._pending_executions[_name] = {
				promise: _req,
				cb: [_call]
			};
			latte.dashboard._pending_executions[_name].promise
				.then(res => {
					$.each(latte.dashboard._pending_executions[_name].cb, function(i, cb) {
						cb(res);
					});
					delete latte.dashboard._pending_executions[_name];
				});
			return _resp;
		}
	}

	set_grid_title() {
		if(frappe.utils.is_empty(this.doc.grid_title)) return;

		this.chart_container.find(".grid-title").remove();
		this.chart_container.find('.data-header-wrapper').prepend(
			$(`<div class="grid-title"
			style="text-align: center; font-size: 16px; font-weight: 500; text-align: left; padding: 1px 1px 5px 5px;">
				${this.doc.grid_title}
				</div>`)
		);
	}

	show_data_slice_actions() {
		let actions = [
			{
				label: __("Refresh"),
				action: 'action-refresh',
				handler: () => {
					this.refresh();
				}
			},
			{
				label: __("Edit..."),
				action: 'action-edit',
				handler: () => {
					frappe.set_route('Form', 'Dashboard Data Slice', this.doc.name);
				}
			}
		];
		this.set_chart_actions(actions);
	}

	set_chart_actions(actions) {
		this.chart_actions = $(`<div class="chart-actions btn-group dropdown pull-right">
			<a class="dropdown-toggle" data-toggle="dropdown"
				aria-haspopup="true" aria-expanded="false"> <button class="btn btn-default btn-xs"><span class="caret"></span></button>
			</a>
			<ul class="dropdown-menu" style="max-height: 300px; overflow-y: auto;">
				${actions.map(action => `<li><a data-action="${action.action}">${action.label}</a></li>`).join('')}
			</ul>
		</div>
		`);

		this.chart_actions.find("a[data-action]").each((i, o) => {
			const action = o.dataset.action;
			$(o).click(actions.find(a => a.action === action));
		});

		try {
			this.chart_container.find(".chart-actions").remove();
			this.chart_actions.prependTo(this.chart_container);
		} catch (error) {}
	}
}