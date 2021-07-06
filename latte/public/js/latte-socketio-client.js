frappe.socketio.init = function initSocketio(port = 3000) {
	if (frappe.boot.disable_async) {
		return;
	}

	if (frappe.socketio.socket) {
		return;
	}

	const { origin } = window.location;

	//Enable secure option when using HTTPS
	if (window.location.protocol == "https:") {
		frappe.socketio.socket = io.connect(frappe.socketio.get_host(port), {
			secure: true,
			query: {
				origin,
			},
			transports: ['websocket'],
		});
	}
	else if (window.location.protocol == "http:") {
		frappe.socketio.socket = io.connect(frappe.socketio.get_host(port), {
			transports: ['websocket'],
			query: {
				origin,
			},
		});
	}
	else if (window.location.protocol == "file:") {
		frappe.socketio.socket = io.connect(window.localStorage.server);
	}

	if (!frappe.socketio.socket) {
		console.log("Unable to connect to " + frappe.socketio.get_host(port));
		return;
	}

	frappe.socketio.socket.on('msgprint', function(message) {
		frappe.msgprint(message);
	});

	frappe.socketio.socket.on('eval_js', function(message) {
		eval(message);
	});

	frappe.socketio.socket.on('progress', function(data) {
		if(data.progress) {
			data.percent = flt(data.progress[0]) / data.progress[1] * 100;
		}
		if(data.percent) {
			if(data.percent==100) {
				frappe.hide_progress();
			} else {
				frappe.show_progress(data.title || __("Progress"), data.percent, 100, data.description);
			}
		}
	});

	frappe.socketio.setup_listeners();
	frappe.socketio.setup_reconnect();
	frappe.socketio.uploader = new frappe.socketio.SocketIOUploader();

	$(document).on('form-load form-rename', function(e, frm) {
		if (frm.is_new()) {
			return;
		}

		for (var i=0, l=frappe.socketio.open_docs.length; i<l; i++) {
			var d = frappe.socketio.open_docs[i];
			if (frm.doctype==d.doctype && frm.docname==d.name) {
				// already subscribed
				return false;
			}
		}

		frappe.socketio.doc_subscribe(frm.doctype, frm.docname);
	});

	$(document).on("form-refresh", function(e, frm) {
		if (frm.is_new()) {
			return;
		}

		frappe.socketio.doc_open(frm.doctype, frm.docname);
	});

	$(document).on('form-unload', function(e, frm) {
		if (frm.is_new()) {
			return;
		}

		// frappe.socketio.doc_unsubscribe(frm.doctype, frm.docname);
		frappe.socketio.doc_close(frm.doctype, frm.docname);
	});

	window.onbeforeunload = function() {
		if (!cur_frm || cur_frm.is_new()) {
			return;
		}

		// if tab/window is closed, notify other users
		if (cur_frm.doc) {
			frappe.socketio.doc_close(cur_frm.doctype, cur_frm.docname);
		}
	}
}