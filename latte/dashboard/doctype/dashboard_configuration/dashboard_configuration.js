// Copyright (c) 2019, Sachin Mane and contributors
// For license information, please see license.txt

frappe.ui.form.on('Dashboard Configuration', {
	refresh(frm) {
		frm.add_custom_button(__("Show Dashboard"), () => frappe.set_route('dashboard', frm.doc.name));
		frm.add_custom_button(__("Publish"), () => {
			frappe.prompt(
				[{
					fieldtype: 'Check',
					fieldname: 'sync_on_publish',
					label: __('Publish'),
					'default': 0,
				}],
				(data) => {
					frappe.call('latte.dashboard.doctype.dashboard_configuration.publish', {
						'dashboard_name': cur_frm.doc.name
					}).then((res) => {
						frm.reload_doc();
					})
				},
				__("Confirm")
			);
		}).addClass('btn-danger');

		// TODO - Legacy Code
		if (!frm.doc.v2) {
			frappe.msgprint(`
				<h4>Attention!</h4>
				<p>Kindly migrate to Dashboard v2. <br>
				Other than additional functionalities added, there are few things that have been updated
				<ul>
					<li>Removed Dashboard Layouts - Use the Configuration</li>
					<li>Removed Layout Names, Columns, Heights in Dashboard DataSlices Table</li>
					<li>Removed Project/ Project Template related change - Use Events</li>
					<li>Removed DataSlice - GridTitle/ GridViewPort/ CSS/ DataSource/ Report/ Method/ Query/ MultipleDS/ GridConfig</li>
				</ul>
				</p>
			`)
		}
		// TODO - Legacy Code
		
		// Auto Upgrade Layout
		frm.trigger('_upgrade_layout');
		// Dashboard Layout Config Trigger
		frm.trigger('_configure_layout');

	},
	v2: function(frm) {
		if (!frm.doc.name)
			frappe.throw('Set Dashboard Name, before enabling v2.')
		if(frm.doc.v2) {
			// Update all child DataSlice to add DS to dashboard_datasource
			const fn = (df) => {
				if (!df.multiple_ds && !frappe.utils.is_empty(df.data_source
					&& df.dashboard_datasource?.length <= 0)) {
					frappe.db.set_value('Dashboard Data Slice', df.name, 
						{'dashboard_datasource': [{
							data_source_name: 'Default', 
							data_source: df.data_source,
							query: df.query,
							report: df.report,
							method: df.method
						}]})
				}
			};
			frappe.call({
				method: 'latte.dashboard.doctype.dashboard_configuration.dashboard_dataslices',
				args: { dashboard_name: frm.doc.name},
				type: 'GET',
				callback: (r) => {
					$.each(r.message, (_, df) => fn(df));
				},
				error: (r) => {
					console.log(r);
				}
			});
		}
	},
	_upgrade_layout: function(frm) {
		frm.trigger('_default_layout').then(res => {
			// console.log('UPGRADE LAYOUT', res);
			frm.set_value('layout_detail', JSON.stringify(res));
		});
	},
	_configure_layout: function (frm) {
		var wrapper = $(frm.get_field('configure_layout').wrapper);
		wrapper.empty();
		var add_filter_btn = $(`<button class="btn btn-primary"> Configure Layout </button>`).appendTo(wrapper);

		add_filter_btn.on('click', function () {
			var dialog = new frappe.ui.Dialog({
				fields: [],
				title: "Configure Layout",
				primary_action: function () {
						const layout = [];
						let gsi = $('.grid-stack-item');
						Array.prototype.forEach.call(gsi, (item) => {
							const data = $(item).data();
							const keys = Object.keys(data);
							if(keys.indexOf("uniqueId") > -1) {
								const slice_layout = {};
								keys.forEach(k => {
									if (k.startsWith('gs')) {
										slice_layout[k] = data[k];
									}
								});
								slice_layout['uniqueId'] = data['uniqueId'];
								slice_layout['sliceName'] = data['sliceName'];
								layout.push(slice_layout);
							}
						});
						frm.configured_layout = layout;
						frm.trigger('_default_layout').then(() => frm.configured_layout = null);
						this.hide();
				}
			});

			// Fetch Configured Layout
			frm.trigger('_default_layout').then(res => {

				let layout_container = $(`
					<div class="row">
						<div class="grid-stack" data-gs-animate="yes">
							${res.map(temp => `
								<div class="grid-stack-item" 
									data-gs-x="${temp.gsX}" 
									data-gs-y="${temp.gsY}" 
									data-gs-width="${temp.gsWidth}" 
									data-gs-height="${temp.gsHeight}"
									data-unique-id="${temp.uniqueId}"
									data-slice-name="${temp.sliceName}">
									<div class="grid-stack-item-content" style="color: #2c3e50; text-align: center; background-color: #eee; left:2px; right:2px;">
										<h4>${temp.sliceName}</h4>
									</div>
						  		</div>`).join('')}
						</div>
					</div>
				`)
				layout_container.appendTo(dialog.body);
			dialog.show();

			let grid;
			dialog.$wrapper
				.on("hide.bs.modal", function () {
					grid && grid.destroy();
				})
				.on("shown.bs.modal", function () {

					dialog.$wrapper.find('.modal-dialog').width(dialog.$wrapper.width()*0.9);
					grid = GridStack.init({
						alwaysShowResizeHandle: /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
							navigator.userAgent
						),
						resizable: {
							handles: 'e, se, s, sw, w'
						},
						// removable: '#trash',
						removeTimeout: 100,
						// acceptWidgets: '.newWidget',
						// staticGrid: true,
						verticalMargin: '4px',
						cellHeight: 10
					});
				})
			})
		})
	},

	_default_layout: function(frm) {
		return new Promise(resolve => {
			// Configured Layout to be updated
			if (frm.configured_layout) {
				frm.set_value('layout_detail', JSON.stringify(frm.configured_layout));
				frm.configured_layout = null;
				resolve(frm.doc.layout_detail);
				return;
			}

			let configured_layout = JSON.parse(frm.doc.layout_detail || '[]');
			let configured_ds = configured_layout.map(x => x['uniqueId']);
			let dashboard_ds = cur_frm.doc?.dashboard_data_slices || [];
			dashboard_ds.forEach(it => {
				if (frappe.utils.is_empty(it.id)) {
					it.id = it.name;
					frappe.db.set_value('Dashboard Data Slices', it.name, 'id', it.id);
				}
			});
			const getYOffset = () => {
				// Logic to get the Y Offset to add in.				
				if ($.isEmptyObject(configured_layout)) {
					return 0;
				}
				return Math.max.apply(Math, configured_layout.map((x) => x['gsY'] + x['gsHeight']));
			};

			
			frappe.db.get_list('Dashboard Data Slice', {
				filters:[['name', 'IN', dashboard_ds.map((t) => t.dashboard_data_slice)], ['data_type', '!=', 'Filter']], fields: ["name"],
				limit: 100
			}).then(res => {
					const _ = $.map(res, function(item) {
						return item.name
					}) || [];
					dashboard_ds = Array.prototype.filter.call(dashboard_ds, function(item) {
						return _.indexOf(item.dashboard_data_slice) > -1;
					});
					// Remove Slices should not be present.
					const _dds = dashboard_ds.map(i => i['dashboard_data_slice']);
					configured_layout = Array.prototype.filter.call(configured_layout, function(item) {
						return _dds.indexOf(item.sliceName) > -1;
					});
					// Add in missing Slice in the Dashboard
					$.each(dashboard_ds, (i, ds) => {
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
					resolve(configured_layout);
				});
			return;
		});
	}
});
