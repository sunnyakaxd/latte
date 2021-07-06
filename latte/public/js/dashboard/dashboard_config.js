frappe.provide("latte")

latte.Dashboard = class GenericDashboard {
	constructor(wrapper) {
		const that = this;
		this.wrapper = $(wrapper);
		$(`<div class="dashboard">
			<div class="dashboard-graph row">
				<div class="grid-stack" data-gs-animate="yes">
				</div>
			</div>
		</div>`).appendTo(this.wrapper.find(".page-content"));
		// Changing margin to 0px
		$('.row.layout-main .layout-main-section-wrapper').css({ 'margin': '0px' });
		this.filters = {};
		this.container = this.wrapper.find(".grid-stack");
		this.page = wrapper.page;
		this._pending_executions = {};
		this.dashboardCSS = Object.freeze({
			"Light": "assets/latte/css/dashboard/light.css",
			"Dark": "assets/latte/css/dashboard/dark.css",
			"Grey": "assets/latte/css/dashboard/grey.css"
		});
	}

	show() {
		this.route = frappe.get_route();
		if (this.route.length > 1) {
			// from route
			this.show_dashboard(this.route.slice(-1)[0]);
			//this.load_css();

		} else {
			// last opened
			
			let method = 'latte.dashboard.doctype.dashboard_configuration.dashboard_access';
			latte.xcall(
				method,
				{
				},
				'GET'
			).then((dashboards) => {
				dashboards = dashboards || [];
				dashboards.length == 0 ? frappe.msgprint('You do not have access to view any Dashboard!'):
					(() => { 
						let seldb = `
						<div>
							<h4>Select from one of the Dashboards</h4>
							<ul>
								${dashboards.map((i) => `<li><a href="#dashboard/${i}">${i}</a></li>`).join('')}
							</ul>
						</div>
						`
						frappe.msgprint(seldb, 'Select Dashboard');
					})();

			});
		}
	}

	show_dashboard(current_dashboard_name) {
		if (this.dashboard_name !== current_dashboard_name) {
			$(this.container).attr('id', this.get_container_id());
			this.dashboard_name = current_dashboard_name;
			let title = this.dashboard_name;
			if (!this.dashboard_name.toLowerCase().includes(__('dashboard'))) {
				// ensure dashboard title has "dashboard"
				title = __('{0}', [title]);
			}
			this.page.set_title(title);
			this.container.empty();
			this.dashboard_access().then((data) => {
				this.set_dropdown();
				this.refresh().then((res, rej) => {
					this.hooks = eval(`(() => { return ${(this.dashboard_doc.on_enter || '{}')} })()`)
					const _that = this;
					Promise.resolve({
						then: function(onRes, onRej) {
							if (_that.hooks && _that.hooks.on_enter) {
								let _res = _that.hooks.on_enter(_that);
								(_res && _res.then) ? (() => {
									_res.then(r => onRes(r)).catch(e => {
										console.error(e);
										frappe.throw('Cannot Enter Dashboard!');
									});
								})(): onRes();
							} else onRes();
						}
					}).then(_ => {
						this.set_layouts();
						this.refresh_elements();
						this.setup_filter();
						this.set_fluidity();
					});
				});
			});
		}
		latte.last_dashboard = current_dashboard_name;
	}

	render_theme(cb) {
		if (this.dashboard_doc.dashboard_theme) {
			let _that = this;
			//getLink(this.dash_theme, 'dashboard-css');
			//frappe.model.with_doc('Dashboard Configuration', this.dashboard_name);
			frappe.db.get_doc('Dashboard Theme', this.dashboard_doc.dashboard_theme).then((res) => {
				Object.freeze([''])
				if (res.css) frappe.dom.set_style(res.css, _that.get_container_id());
				cb();
			});
		} else cb();
	}

	// Method to Check User has Report Access
	dashboard_access() {
		return new Promise((resolve) => {
			let method = 'latte.dashboard.doctype.dashboard_configuration.dashboard_access';
			return latte.xcall(
				method,
				{
				},
				'GET'
			).then((dashboards) => {
				const err = () => frappe.throw('You do not have access to View this Dashboard!');
				dashboards && dashboards.length > 0 ? (() => {
					this.db_access = dashboards;
					if (dashboards.indexOf(this.dashboard_name) > -1) {
						resolve();
					} else {
						err();
					}
				})() : err();
			});
		});
	}

	refresh() {
		var that = this;
		if (!latte.dashboard.filters)
			latte.dashboard.filters = {};
		if (latte.dashboard.dataslice)
			latte.dashboard.dataslice = null;
		return new Promise((res, rej) => {
			this.get_dashboard_doc().then((doc) => {
				// Copying object since changing to 'doc' reflects in locals and will create errors
				latte.DataMapper.reshape_dashboard_doc(doc);
				if (this.container.children().length > 0)
					this.container.children().empty();

				// Load any Dashboard CSS
				this.dash_theme = this.dashboard_doc.dashboard_theme &&
					this.dashboardCSS[this.dashboard_doc.dashboard_theme];
				this.render_theme(() => {
					res();
				});
			});
		})
	}

	set_layouts() {
		let configured_layout = JSON.parse(this.dashboard_doc.layout_detail || '[]');
		let configured_ds = configured_layout.map(x => x['sliceId']);
		let dashboard_ds = this.dashboard_doc.data_slices || [];
		if (!configured_layout) {
			const getYOffset = () => {
				// Logic to get the Y Offset to add in.				
				if ($.isEmptyObject(configured_layout)) {
					return 0;
				}
				return Math.max.apply(Math, configured_layout.map((x) => x['gsY'] + x['gsHeight']));
			};
	
			$.each(dashboard_ds, (i, ds) => {
				ds = ds.link || {};
				if (configured_ds.indexOf(ds['id']) < 0) {
					configured_layout.push({
						'gsX': 0,
						'gsY': getYOffset(),
						'gsWidth': 12,
						'gsHeight': 2,
						'uniqueId': ds['id'],
						'sliceName': ds['dashboard_data_slice']
					});
					configured_ds.push(ds['id']);
				}
			});
		}
		const _borders = this.dashboard_doc.data_slice_borders;
		$.each(configured_layout, (i, item) => {
			let slice_container = $(`<div class="grid-stack-item" 
										data-gs-x="${item.gsX}" 
										data-gs-y="${item.gsY}" 
										data-gs-width="${item.gsWidth}" 
										data-gs-height="${item.gsHeight}"
										data-unique-id="${item.uniqueId}"
										data-slice-name="${item.sliceName}">
										<div class="grid-stack-item-content" style="left:2px; right:2px; ${!_borders ? "border: None;" : ""}">
										</div>
									</div>`);
			slice_container.appendTo(latte.dashboard.container);
		});
		latte.dashboard.grid = GridStack.init({
			verticalMargin: '4px',
			cellHeight: 10,
			staticGrid: this.dashboard_doc.is_layout_fixed ? true : false
		});
	}

	refresh_elements() {
		$('.chart-column-container').parent().remove();
		$('.chart-column-container-filter').parent().remove();
		// TODO - Check this code. Need to refactor for Filters.
		$('.page-form').empty();

		const _ds = Object.keys(this.dashboard_doc.data_slices).map(a => this.dashboard_doc.data_slices[a].link.slice_name);

		latte.xcall(
			'latte.dashboard.doctype.dashboard_configuration.dashboard_dataslices',
			{
				dashboard_name: this.dashboard_name
			},
			'GET'
		).then(dataslices => {
			Object.keys(this.dashboard_doc.data_slices).map((slice) => {
				let chart_container = $(`<div id="${slice}" class="cht-cont ${this.dashboard_doc.data_slices[slice].link.class || ''}"></div>`)
					.appendTo($("div[data-unique-id='" + this.dashboard_doc.data_slices[slice].link.id + "'] .grid-stack-item-content"));
				const sd = (dataslices.filter(x => x.name === this.dashboard_doc.data_slices[slice].link.slice_name) || [])[0];
				this.dashboard_doc.data_slices[slice].doc = sd;
				let ds = new latte.Dashboard.DataSlice[sd.data_type](
					sd,
					this.dashboard_doc.data_slices[slice].link,
					chart_container);
				this.dashboard_doc.data_slices[slice].dashobj = ds;
				chart_container.addClass(frappe.scrub(`ds-${sd.data_type}`));
				ds.update_config();
				ds.prepare_container();
				ds.refresh();
			});
		})
	}

	// Fetch all Dashboard Data for a particular dashboard Name
	// To handle Slice based filters, need to handle in fetch for every Data Slice
	fetch_all() {
		let method = 'latte.dashboard.doctype.dashboard_configuration.run';
		return frappe.xcall(
			method,
			{
				filters: this.filters,
				dashboard_name: this.dashboard_name
			}
		);
	}

	get_dashboard_doc() {
		return frappe.model.with_doc('Dashboard Configuration', this.dashboard_name);
	}

	set_dropdown() {
		this.page.clear_menu();

		// Menu Actionable for System Admin
		(frappe.user_roles.indexOf('Administrator') > -1 ||
			frappe.user_roles.indexOf('System Manager') > -1) ? (() => {
				this.page.add_menu_item('Edit Dashboard', () => {
					frappe.set_route('Form', 'Dashboard Configuration', latte.dashboard.dashboard_name);
				}, 1);

				this.page.add_menu_item('Edit Data Slice', () => {
					Object.keys(this.dashboard_doc.data_slices).forEach((item) => {
						try {
							this.dashboard_doc.data_slices[item].dashobj.data_header.enable_edit();
						} catch (error) {}
					})
				}, 1);

				this.page.add_menu_item('Create Dashboard', () => {
					frappe.new_doc('Dashboard Configuration');
				}, 1);

				frappe.db.get_list("Dashboard Configuration", { 'limit': 100 }).then(dashboards => {
					dashboards.map(dashboard => {
						let name = dashboard.name;
						if (name != this.dashboard_name) {
							this.page.add_menu_item(name, () => frappe.set_route("dashboard", name));
						}
					});
				});
			})() : (() => {
				this.page.menu_btn_group.find('.menu-btn-group-label').text('Navigate');
				this.db_access.map(dashboard => {
					this.page.add_menu_item(dashboard, () => frappe.set_route("dashboard", dashboard));
				});
			})()

		this.page.set_primary_action(
			'<div class="glyphicon glyphicon-repeat"></div>',
			() => { this.refresh_elements(); }, 'glyphicon glyphicon-repeat',
		)
	}

	setup_filter() {
		this.page.page_actions.find('.db-filters').remove();
		this.page.filter_view = $(`
			<button class="db-filters btn btn-sm">
				<i class="visible-xs glyphicon glyphicon-filter"></i>
				<span class="hidden-xs"><div class="glyphicon glyphicon-filter"></div></span>
			</button>`).prependTo(this.page.page_actions);
		$(this.page.filter_view).click(function () {
			const _filters = Object.keys(latte.dashboard.filters).map(a => {return latte.dashboard.filters[a]}) || [];
			_filters.length > 0 ? (() => {
				let _flt = latte.dashboard.filter_dialog = new frappe.ui.Dialog({
					title: __('Filters'),
					fields: _filters});
				(_flt.fields_list || []).forEach((fl) => {
					const { wrapper, df } = fl;
					df.slice.setup(wrapper);
				});
				_flt.show();
			})(): (() => {
				frappe.msgprint('No Filters Configured!');
			})();
		});
	}

	set_fluidity() {
		this.page.page_actions.find('.check-fluid').remove();
		this.page.fluid_view = $(`
			<div class="check-fluid checkbox"> 
				<label> <input type="checkbox" checked> Fluid </label> 
			</div>`).prependTo(this.page.page_actions);
		$('.page-body.container').css('background-color', '#fbfbfb')
			.removeClass('container').addClass('container-fluid');
		$('.page-body .page-wrapper').removeClass('container').addClass('container-fluid');
		$(this.page.fluid_view).find('input').change(function () {
			this.checked ?
				$('.page-body .page-wrapper').removeClass('container').addClass('container-fluid') :
				$('.page-body .page-wrapper').removeClass('container-fluid').addClass('container');
		});
		$('.page-body').css('overflow', 'hidden');
	}

	filter_triggered(filter_slice) {
		var ds_to_refresh = new Set();
		Object.keys(latte.dashboard.dashboard_doc.data_slices).map((slice_scrub) => {
			latte.dashboard.dashboard_doc.data_slices[slice_scrub].dashobj.doc.filter.forEach((filter_scrub) => {
				if (filter_scrub.filter_data_slice === filter_slice &&
					latte.dashboard.dashboard_doc.data_slices[slice_scrub].dashobj.doc.data_type != 'Filter') {
					ds_to_refresh.add(slice_scrub);
				}
			});
		})
		ds_to_refresh.forEach((ds_scrub) => {
			latte.dashboard.dashboard_doc.data_slices[ds_scrub].dashobj.refresh()
		})
	}

	get_filters() {
		return JSON.parse(localStorage.getItem('latte.filters') || '{}');
	}

	set_filters(filter = {}) {
		let filters = JSON.parse(localStorage.getItem('latte.filters') || '{}');
		filters[filter.key] = filter.value;
		localStorage.setItem('latte.filters', JSON.stringify(filters));
	}

	remove_filters(filter = {}) {
		let filters = JSON.parse(localStorage.getItem('latte.filters') || '{}');
		delete filters[filter.key];
		localStorage.setItem('latte.filters', JSON.stringify(filters));
	}

	get_container_id() {
		return this.dashboard_name
	}
}

/**
 * Frappe Xcall but with method type.
 * @param {*} method 
 * @param {*} params 
 * @param {*} type 
 */
latte.xcall = function (method, params, type) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method: method,
			args: params,
			type: type,
			callback: (r) => {
				resolve(r.message);
			},
			error: (r) => {
				reject(r.message);
			}
		});
	});
};



/**
 * Dashboard Legacy Code.
 */
latte.DashboardLegacy = class DashboardLegacy extends latte.Dashboard {
	constructor(wrapper) {
		super(wrapper);
		const that = this;
		this.wrapper = $(wrapper);
		$(`<div class="dashboard">
			<div class="dashboard-graph row"></div>
		</div>`).appendTo(this.wrapper.find(".page-content"));
		// Changing margin to 0px
		$('.row.layout-main .layout-main-section-wrapper').css({ 'margin': '0px' });
		this.filters = {};
		this.container = this.wrapper.find(".dashboard-graph");
		this.page = wrapper.page;
		this.dashboardCSS = Object.freeze({
			"Light": "assets/latte/css/dashboard/light.css",
			"Dark": "assets/latte/css/dashboard/dark.css",
			"Grey": "assets/latte/css/dashboard/grey.css"
		});
	}

	show_dashboard(current_dashboard_name) {
		if (this.dashboard_name !== current_dashboard_name) {
			$(this.container).attr('id', this.get_container_id());
			this.dashboard_name = current_dashboard_name;
			let title = this.dashboard_name;
			if (!this.dashboard_name.toLowerCase().includes(__('dashboard'))) {
				// ensure dashboard title has "dashboard"
				title = __('{0}', [title]);
			}
			this.page.set_title(title);
			this.container.empty();
			this.dashboard_access().then((data) => {
				this.set_dropdown();
				this.refresh().then((res, rej) => {
					Promise.resolve(eval(this.dashboard_doc.on_enter || '')).then(_ => {

						$('.page-body.container').removeClass('container').addClass('container-fluid');

						if ((this.dashboard_doc.project_template) != undefined && (this.dashboard_doc.project_template) != "") {

							let project_temp = this.dashboard_doc.project_template;
							this.verify_previous_open_project().then((out_res) => {
								if (out_res == 0) {

									this.is_project_created().then((proj_created) => {
										if (proj_created == 1) {
											this.display_complete_dashboard();
										}
										else if (proj_created == 0) {
											this.display_open_dashboard_option();
										}
										else {
											frappe.msgprint("Console Already Closed");
										}
									})
								}
								else {
									this.display_raise_project_closure_option();
								}
							});
						}
						else {
							this.set_layouts();
							this.refresh_elements();
						}
					});
				});
			});
		}
		latte.last_dashboard = current_dashboard_name;
	}

	// Method to Check User has Open Project Linked with it
	verify_previous_open_project() {
		let method = 'erpnow.project.api.project.is_previous_project_open';
		return frappe.xcall(
			method,
			{
				proj_temp: this.dashboard_doc.project_template
			}
		);
	}

	// Method to Check User has Project Created for today
	is_project_created() {
		let method = 'latte.dashboard.doctype.dashboard_configuration.dashboard_configuration.is_project_created';
		return frappe.xcall(
			method,
			{
				proj_temp: this.dashboard_doc.project_template
			}
		);
	}

	//Method to display complete dashboard after it gets open
	display_complete_dashboard() {
		this.set_layouts();
		this.refresh_elements();
		latte.dashboard.page.set_secondary_action('Check Progress', (evn) => {
			
			// Function to display current tasks
			

			// Close
			frappe.call({
				'method': 'latte.dashboard.doctype.dashboard_configuration.dashboard_configuration.get_task_progress',
				'args': {
					proj_temp: this.dashboard_doc.project_template
				}
			}).then((data) => {
				this.show_task_list(data)
			})
		})
	}

	// Method to Display Open Dashboard Option
	display_open_dashboard_option() {

		frappe.confirm("Do you want to open the Dashboard", () => {
			let open_result = frappe.call({
				'method': 'latte.dashboard.doctype.dashboard_configuration.dashboard_configuration.create_project',
				'args': {
					proj_temp: this.dashboard_doc.project_template
				}
			})
			this.set_layouts();
			this.refresh_elements();

		}, () => {
			frappe.msgprint("Dashboard not opened");
		})
	}

	//Method to raise Project Closure Request
	raise_closure_request() {
		frappe.hide_msgprint()
		let method = 'erpnow.project.api.project_closure_request.create_project_closure_request';

		let d = new frappe.ui.Dialog({
			"title": "Enter Reason",
			"fields": [
				{
					"fieldname": "reason",
					"fieldtype": "Text",
					"label": "Reason",
					"reqd": true
				}
			]
		})
		let __that = this

		d.show()

		d.set_primary_action(__("Submit"), function () {
			d.hide()
			try {
				frappe.xcall(
					method,
					{
						args: {
							proj_temp: __that.dashboard_doc.project_template,
							requested_by: frappe.session.user,
							reason: d.get_values()['reason']
						}
					}
				);
			}
			catch (err) {

			}
			finally {
				frappe.hide_msgprint()
			}
		}
		)

	}

	// Method to Display All task status for the day
	show_task_list(data) {

		
		// if (data.message.status == "Closed") {
		// 	frappe.msgprint("Dashboard Closed Successfully");
		// 	frappe.set_route();
		// }
		// else {
		// 	let data_to_show = '<h1 style="color:Red;text-align:center;">Can Not Close Console</h1><h1 style="color:Grey;text-align:center;">Task Status</h1>'
		// 	let header = '<table class="table table-bordered table-striped"><tr><th>Task Name</th><th>Progress</th></tr>'
		// 	let task_list = data.message.task_list
		// 	let index = 0
		// 	for (index in task_list) {
		// 		data_to_show = data_to_show + '<tr><td>' + task_list[index].subject + '</td><td>' + task_list[index].progress + '</td>	</tr>'
		// 	}
		// 	let footer = '<button id="proj_closure_request" >Raise Console Closure Request</button>'
		// 	data_to_show = header + data_to_show + '</table>' + footer
		// 	frappe.msgprint(data_to_show);
		// 	setTimeout(() => {
		// 		$('#proj_closure_request')[0].addEventListener('click', () => {

		// 			this.raise_closure_request();
		// 			// frappe.hide_msgprint();
		// 		});
		// 	}, 1000);

		

		// }

		let data_to_show = '<h1 id ="closure_status_text" style="text-align:center;"></h1><h1 style="color:Grey;text-align:center;">Task Status</h1>'
		let header = '<table class="table table-bordered table-striped"><tr><th>Task Name</th><th>Progress</th></tr>'
		let task_list = data.message.task_list
		let index = 0
		for (index in task_list) {
			data_to_show = data_to_show + '<tr><td>' + task_list[index].subject + '</td><td>' + task_list[index].progress + '</td>	</tr>'
		}
		let footer = '<button id = "close_project" class = "btn btn-primary btn-sm primary-action"> Close Console</button>&nbsp&nbsp<button id="proj_closure_request" class = "btn btn-default btn-sm">Raise Console Closure Request</button>'
		data_to_show = header + data_to_show + '</table>' + footer
		frappe.msgprint(data_to_show);
		setTimeout(() => {

			$('#close_project')[0].addEventListener('click', () => {
				frappe.call({
					'method': 'latte.dashboard.doctype.dashboard_configuration.dashboard_configuration.close_project',
					'args': {
						proj_temp: this.dashboard_doc.project_template
					}
				}).then((data) => {

					if(data.message.status == 'Closed'){
						$('#closure_status_text')[0].innerHTML  = 'Console Closed sucessfully'
						$('#closure_status_text')[0].style.color = 'green'
						setTimeout(function(){frappe.set_route()}, 2000)
					}
					else{
						$('#closure_status_text')[0].innerHTML  = 'Cannot close console'
						$('#closure_status_text')[0].style.color = 'red'
					}
				})
			})

			$('#proj_closure_request')[0].addEventListener('click', () => {
				
				this.raise_closure_request();
				// frappe.hide_msgprint();
			});

		}, 1000);
	}

	//Method to Display Project Closure Request Option
	display_raise_project_closure_option() {

		let data_to_show = '<h1 style="color:Red;text-align:center;">Previous Day Console Not Closed</h1><br>'
		let footer = '<button id="proj_closure_request" >Raise Console Closure Request</button>'
		data_to_show = data_to_show + footer
		frappe.msgprint(data_to_show);
		setTimeout(() => {
			$('#proj_closure_request')[0].addEventListener('click', () => {

				this.raise_closure_request();
				frappe.hide_msgprint();
			});
		}, 1000);
	}

	set_layouts() {
		// Setting the Layout
		this.dashboard_doc.layouts.forEach((layout) => {
			let slice_container = $(`<div id="${layout.layout_name}" class="${layout.type}"></div>`);
			if (layout.type == 'column' && layout.width != '-')
				slice_container.addClass(`col-md-${layout.width}`);
			if (!frappe.utils.is_empty(layout.parent_name))
				slice_container.appendTo($(`#${layout.parent_name}`));
			else
				slice_container.appendTo(latte.dashboard.container);

			if (!frappe.utils.is_empty(layout.height) && layout.height > 0)
				$(slice_container).css({ "height": layout.height, 'overflow-y': 'auto' });
			if (layout.is_filter) {
				slice_container.addClass('filter-form');
				slice_container.css('border', '1px solid #d1d8dd');
				latte.dashboard.page.page_form = $('<div class="page-form row hide"></div>').prependTo(slice_container);
				$(slice_container).closest('.filter-form').css('padding', '0px');
			}
		});
	}

	refresh_elements() {
		//$('.chart-column-container').parent().remove();
		$('.chart-column-container').parent().remove();
		$('.chart-column-container-filter').parent().remove();
		// TODO - Check this code. Need to refactor for Filters.
		$('.page-form').empty();
		Object.keys(this.dashboard_doc.data_slices).map((slice) => {
			let chart_container = $(`<div id="${slice}" class="cht-cont ${this.dashboard_doc.data_slices[slice].link.class || ''}"></div>`)
				.appendTo($(`#${this.dashboard_doc.data_slices[slice].link.layout_name}`));
			frappe.model.with_doc("Dashboard Data Slice", this.dashboard_doc.data_slices[slice].link.slice_name).then(sd => {
				this.dashboard_doc.data_slices[slice].doc = sd;
				let ds = new latte.DashboardLegacy.DataSlice[sd.data_type](
					sd,
					this.dashboard_doc.data_slices[slice].link,
					chart_container);
				this.dashboard_doc.data_slices[slice].dashobj = ds;
				chart_container.addClass(frappe.scrub(`ds-${sd.data_type}`));
				ds.update_config();
				ds.prepare_container();
				ds.refresh();
			});
		});
	}

	set_dropdown() {
		this.page.clear_menu();

		this.page.add_menu_item('Edit Dashboard', () => {
			frappe.set_route('Form', 'Dashboard Configuration', latte.dashboard.dashboard_name);
		}, 1);

		this.page.add_menu_item('Edit Data Slice', () => {
			Object.keys(this.dashboard_doc.data_slices).forEach((item) => {
				this.dashboard_doc.data_slices[item].dashobj.show_data_slice_actions();
			})
		}, 1);

		this.page.add_menu_item('Create Dashboard', () => {
			frappe.new_doc('Dashboard Configuration');
		}, 1);

		frappe.db.get_list("Dashboard Configuration").then(dashboards => {
			dashboards.map(dashboard => {
				let name = dashboard.name;
				if (name != this.dashboard_name) {
					this.page.add_menu_item(name, () => frappe.set_route("dashboard", name));
				}
			});
		});
		this.page.set_primary_action(
			__('Refresh'),
			() => { this.refresh_elements(); }, 'icon-refresh',
		)
	}
}

$(document).on('data-attribute-changed', function (event, filter_slice_name) {
	// latte.dashboard.refresh_elements();
	// Refresh only elements that have filter_slice_name configured in filters
	var ds_to_refresh = new Set();

	Object.keys(latte.dashboard.dashboard_doc.data_slices).map((slice_scrub) => {
		latte.dashboard.dashboard_doc.data_slices[slice_scrub].dashobj.doc.filter.forEach((filter_scrub) => {
			if (filter_scrub.filter_data_slice === filter_slice_name &&
				latte.dashboard.dashboard_doc.data_slices[slice_scrub].dashobj.doc.data_type != 'Filter') {
				ds_to_refresh.add(slice_scrub);
			}
		});
	})

	ds_to_refresh.forEach((ds_scrub) => {
		latte.dashboard.dashboard_doc.data_slices[ds_scrub].dashobj.refresh()
	})
});


$(document).on('grid-refreshed', function(event, grid_slice_name) {
	let to_refresh = []
	Object.keys(latte.dashboard.dashboard_doc.data_slices).forEach(slice => {
	    if(latte.dashboard.dashboard_doc.data_slices[slice].doc.results_from === grid_slice_name) {
	        to_refresh.push(slice)
	    }
	})

	to_refresh.forEach(slice => {
		latte.dashboard.dashboard_doc.data_slices[slice].dashobj.refresh();
	})
})