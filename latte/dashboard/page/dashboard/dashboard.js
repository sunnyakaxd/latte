frappe.provide("latte")

// Latte Dashboard Page
frappe.pages['dashboard'].on_page_load = function(wrapper) {
	var that = this;
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Dashboard',
		single_column: true
	});

	if(window.location.pathname == '/db') {
		$('.page-head').css('top', '0px');
		$('.page-container').css('margin-top', '0px');
		$('#page-desktop').empty();
	}

	if (window.__loading_dependencies) {
		return;
	}
	window.__loading_dependencies = new Promise(async (resolve, reject) => {
		await getScript('/assets/js/dashboard.min.js');
		await getLink('/assets/latte/css/dashboard/default_theme.css', 'dashboard-base-theme');
		// await getLink('/assets/latte/css/dashboard/chart_theme.css', 'chart-base-theme');
		await getLink('/assets/latte/css/dashboard/map_theme.css', 'map-base-theme');
		resolve();
	}).catch(e => {
		reject(e);
	});

	Promise.resolve(window.__loading_dependencies).then((v) => {
		load_dashboard().then(() => {
			latte.dashboard = new latte.OverDashboard(wrapper);
			if($(wrapper).is(':visible'))
				that.render();
		});
	});
	$(wrapper).bind('show', function() {
		that.render();
	});
	this.render = () => {
		latte.dashboard && latte.dashboard.show();
	}
}

const getScript = function(url) {
	return new Promise((resolve, reject) => {
		$.ajax({
			url,
			data: {
				ver: _version_number,
			},
			dataType: 'script',
			cache: true,
			success: resolve,
			error: reject,
		});
	});
}

const getLink = function(url, id) {
	return new Promise(((resolve, reject) => {
		const link = document.createElement('link');
		link.setAttribute('rel', 'stylesheet');
		link.setAttribute('type', 'text/css');
		link.setAttribute('id', id);
		link.onload = resolve;
		link.onerror = reject;
		link.setAttribute('href', url);
		document.getElementsByTagName('head')[0].appendChild(link);
	}));
}

frappe.route.on('change', () => {
	if (!frappe.get_route_str().startsWith("dashboard") && $('#dashboard-base-theme').length > 0) {
		$('#dashboard-base-theme').attr('disabled', true);
		$('.page-body.container-fluid').removeClass('container-fluid').addClass('container');
		$('.page-body .page-wrapper').removeClass('container-fluid').removeClass('container');

		if (latte.dashboard?.hooks?.on_exit) latte.dashboard.hooks.on_exit(latte.dashboard);
	} else if (frappe.get_route_str().startsWith("dashboard") && $('#dashboard-base-theme').length > 0) {
		$('#dashboard-base-theme').attr('disabled', false);

		// TODO - Legacy Code
		if (latte.dashboard.set_fluidity) {
			latte.dashboard.set_fluidity();
		} else {
			$('.page-body.container').removeClass('container').addClass('container-fluid');
		}
	}
});

let load_dashboard = function() {
	return new Promise((resolve) => {
		// Checking Dashboard Version
		// TODO - Legacy Code
		try {
			if (frappe.get_route().slice().length == 1) {
				latte.OverDashboard = latte.Dashboard;
				resolve();
				return;
			}
			frappe.db.get_value('Dashboard Configuration', frappe.get_route().slice(-1)[0], 'v2')
				.then(res => {
					if (res && res.message.v2) {
						latte.OverDashboard = latte.Dashboard;
					} else {
						latte.OverDashboard = latte.DashboardLegacy;
					}
					resolve();
				})
		} catch (e) {
			console.error('Error occurred while checking on Dashboard Version', e);
			latte.OverDashboard = latte.DashboardLegacy;
			resolve();
		}
		// TODO - Legacy Code
	});
}