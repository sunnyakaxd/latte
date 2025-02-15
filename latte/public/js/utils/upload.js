// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// parent, args, callback
frappe.upload = {
	make(opts) {
		if (!opts.args) opts.args = {};

		if (opts.allow_multiple === undefined) {
			opts.allow_multiple = 1;
		}

		// whether to show public/private checkbox or not
		opts.show_private = !("is_private" in opts);

		// make private by default
		if (!("options" in opts) || ("options" in opts &&
			(opts.options && !opts.options.toLowerCase() == "public" && !opts.options.toLowerCase() == "image"))) {
			opts.is_private = 1;
		}

		var d = null;
		// create new dialog if no parent given
		if (!opts.parent) {
			d = new frappe.ui.Dialog({
				title: __('Upload Attachment'),
				primary_action_label: __('Attach'),
				primary_action() { }
			});

			opts.parent = d.body;
			opts.btn = d.get_primary_btn();
			d.show();
		}

		var $upload = $(frappe.render_template("upload", { opts: opts })).appendTo(opts.parent);
		var $file_input = $upload.find(".input-upload-file");
		var $uploaded_files_wrapper = $upload.find('.uploaded-filename');

		// bind pseudo browse button
		$upload.find(".btn-browse").on("click", function () {
			$file_input.click();
		});

		// restrict to images
		if (opts.restrict_to_images) {
			$file_input.prop('accept', 'image/*');
		}

		// dropzone upload
		const $dropzone = $('<div style="padding: 20px 10px 0px 10px;"/>');
		new frappe.ui.DropZone($dropzone, {
			drop(files) {
				$dropzone.hide();

				opts.files = opts.files ? [...opts.files, ...files] : files;

				$file_input.trigger('change');
			}
		});
		// end dropzone

		$upload.append($dropzone);

		$file_input.on("change", function () {
			if (this.files.length > 0 || opts.files) {
				var fileobjs = null;

				if (opts.files) {
					// files added programmatically
					fileobjs = opts.files;
					delete opts.files;
				} else {
					// files from input type file
					fileobjs = $upload.find(":file").get(0).files;
				}
				var file_array = $.makeArray(fileobjs);

				$upload.find(".web-link-wrapper").addClass("hidden");
				$upload.find(".btn-browse").removeClass("btn-primary").addClass("btn-default");
				$uploaded_files_wrapper.removeClass('hidden').empty();
				$uploaded_files_wrapper.css({ 'margin-bottom': '25px' });

				file_array = file_array.map(
					file => Object.assign(file, { is_private: opts.is_private ? 1 : 0 })
				);
				$upload.data('attached_files', file_array);

				// List of files in a grid
				$uploaded_files_wrapper.append(`
					<div class="list-item list-item--head">
						<div class="list-item__content list-item__content--flex-2">
							${__('Filename')}
						</div>
						${opts.show_private ? `<div class="list-item__content file-public-column">
							${__('Public')}
							</div>`: ''}
						<div class="list-item__content list-item__content--activity" style="flex: 0 0 32px">
						</div>
					</div>
				`);
				var file_pills = file_array.map(
					file => frappe.upload.make_file_row(file, opts)
				);
				$uploaded_files_wrapper.append(file_pills);
			} else {
				frappe.upload.show_empty_state($upload);
			}
		});

		if (opts.files && opts.files.length > 0) {
			$file_input.trigger('change');
		}

		// events
		$uploaded_files_wrapper.on('click', '.list-item-container', function (e) {
			var $item = $(this);
			var filename = $item.attr('data-filename');
			var attached_files = $upload.data('attached_files');
			var $target = $(e.target);

			if ($target.is(':checkbox')) {
				var is_private = !$target.is(':checked');

				attached_files = attached_files.map(file => {
					if (file.name === filename) {
						file.is_private = is_private ? 1 : 0;
					}
					return file;
				});
				$uploaded_files_wrapper
					.find(`.list-item-container[data-filename="${filename}"] .fa.fa-fw`)
					.toggleClass('fa-lock fa-unlock-alt');

				$upload.data('attached_files', attached_files);
			} else if ($target.is('.uploaded-file-remove, .fa-remove')) {
				// remove file from attached_files object
				attached_files = attached_files.filter(file => file.name !== filename);
				$upload.data('attached_files', attached_files);

				// remove row from dom
				$uploaded_files_wrapper
					.find(`.list-item-container[data-filename="${filename}"]`)
					.remove();

				if (attached_files.length === 0) {
					frappe.upload.show_empty_state($upload);
				}
			}
		});


		if (!opts.btn) {
			opts.btn = $('<button class="btn btn-default btn-sm attach-btn">' + __("Attach")
				+ '</div>').appendTo($upload);
		} else {
			$(opts.btn).unbind("click");
		}

		// Primary button handler
		opts.btn.click(function () {
			// close created dialog
			d && d.hide();

			// convert functions to values
			if (opts.get_params) {
				opts.args.params = opts.get_params();
			}

			// Get file url if input is visible
			var file_url = $upload.find('[name="file_url"]:visible');
			file_url = file_url.length && file_url.get(0).value;
			if (file_url) {
				opts.args.file_url = file_url;
				frappe.upload.upload_file(null, opts.args, opts);
			} else {
				var files = $upload.data('attached_files');
				frappe.upload.upload_multiple_files(files, opts.args, opts);
			}
		});
	},

	make_file_row(file, { show_private } = {}) {
		const safe_file_name = frappe.utils.xss_sanitise(file.name);
		var template = `
			<div class="list-item-container" data-filename="${safe_file_name}">
				<div class="list-item">
					<div class="list-item__content list-item__content--flex-2 ellipsis">
						<span>${safe_file_name}</span>
						<span style="margin-top: 1px; margin-left: 5px;"
							class="fa fa-fw text-warning ${file.is_private ? 'fa-lock' : 'fa-unlock-alt'}">
						</span>
					</div>
					${show_private ? `
						<div class="list-item__content file-public-column ellipsis">
							<input type="checkbox" ${!file.is_private ? 'checked' : ''}/>
						</div>
					`: ''}
					<div class="list-item__content list-item__content--activity ellipsis" style="flex: 0 0 32px;">
					<button class="btn btn-default btn-xs text-muted uploaded-file-remove">
							<span class="fa fa-remove"></span>
						</button>
					</div>
				</div>
			</div>`;

		return $(template);
	},

	show_empty_state($upload) {
		$upload.find(".uploaded-filename").addClass("hidden");
		$upload.find(".web-link-wrapper").removeClass("hidden");
		$upload.find(".private-file").addClass("hidden");
		$upload.find(".btn-browse").removeClass("btn-default").addClass("btn-primary");
	},

	upload_multiple_files(files /*FileData array*/, args, opts) {
		var i = -1;
		frappe.upload.total_files = files ? files.length : 0;
		// upload the first file
		upload_next();
		// subsequent files will be uploaded after
		// upload_complete event is fired for the previous file
		$(document).on('upload_complete', on_upload);

		function upload_next() {
			if (files) {
				i += 1;
				var file = files[i];
				args.is_private = file.is_private;
				if (!opts.progress) {
					frappe.show_progress(__('Uploading'), i, files.length);
				}
			}
			frappe.upload.upload_file(file, args, opts);
		}

		function on_upload(e, attachment) {
			if (!files || i === files.length - 1) {
				$(document).off('upload_complete', on_upload);
				frappe.hide_progress();
				return;
			}
			upload_next();
		}
	},

	upload_file(fileobj, args, opts) {
		if (!fileobj && !args.file_url) {
			if (opts.on_no_attach) {
				opts.on_no_attach();
			} else {
				frappe.msgprint(__("Please attach a file or set a URL"));
			}
			return;
		}

		if (fileobj) {
			frappe.upload.read_file(fileobj, args, opts);
		} else {
			// with file_url
			frappe.upload._upload_file(fileobj, args, opts);
		}
	},

	_upload_file(fileobj, args, opts, dataurl) {
		if (args.file_size) {
			frappe.upload.validate_max_file_size(args.file_size);
		}
		if (opts.on_attach) {
			opts.on_attach(args, dataurl, fileobj);
		} else {
			if (opts.confirm_is_private) {
				frappe.prompt({
					label: __("Private"),
					fieldname: "is_private",
					fieldtype: "Check",
					"default": 1
				}, function (values) {
					args["is_private"] = values.is_private;
					frappe.upload.upload_to_server(fileobj, args, opts);
				}, __("Private or Public?"));
			} else {
				if (!("is_private" in args) && "is_private" in opts) {
					args["is_private"] = opts.is_private;
				}

				frappe.upload.upload_to_server(fileobj, args, opts);
			}

		}
	},

	read_file(fileobj, args, opts) {
		args.filename = fileobj.name.split(' ').join('_');
		args.file_url = null;

		if (opts.options && opts.options.toLowerCase() == "image") {
			if (!frappe.utils.is_image_file(args.filename)) {
				frappe.msgprint(__("Only image extensions (.gif, .jpg, .jpeg, .tiff, .png, .svg) allowed"));
				return;
			}
		}

		let start_complete = frappe.cur_progress ? frappe.cur_progress.percent : 0;

		var upload_with_filedata = function () {
			let freader = new FileReader();
			freader.onload = function () {
				var dataurl = freader.result;
				args.filedata = freader.result.split(",")[1];
				args.file_size = fileobj.size;
				frappe.upload._upload_file(fileobj, args, opts, dataurl);
			};
			freader.readAsDataURL(fileobj);
		};

		const upload_config = frappe.boot.upload_config;

		if (fileobj.size > (1024 * 1024 * frappe.boot.upload_config.file_size_limit)) {
			frappe.msgprint({
				title: 'File Too Large',
				message: `File size upto ${frappe.boot.upload_config.file_size_limit} MB is allowed`,
				indicator: 'red',
			})
			return;
		}

		if (opts.on_attach || fileobj.size < upload_config.form_data_limit || upload_config.disable_socketio) {
			upload_with_filedata();
			return;
		}

		if (!frappe.upload.socket_io_stream_uploader) {
			frappe.upload.socket_io_stream_uploader = new frappe.upload.SocketIOStreamUploader();
		}

		frappe.upload.socket_io_stream_uploader.start({
			file: fileobj,
			filename: args.filename,
			is_private: args.is_private,
			doctype: args.doctype,
			docname: args.docname,
			fallback: () => {
				// if fails, use old filereader
				upload_with_filedata();
				console.log('Failed');
			},
			callback: (response) => {
				const data = response.message
				frappe.hide_progress();
				opts.callback(data, response);
				$(document).trigger("upload_complete", data);
			},
			on_progress: (percent_complete) => {
				let increment = (flt(percent_complete) / frappe.upload.total_files);
				frappe.show_progress(__('Uploading'),
					start_complete + increment);
			}
		});
	},

	upload_to_server(file, args, opts) {
		if (opts.start) {
			opts.start();
		}

		var ajax_args = {
			method: "latte.file_storage.file.uploadfile",
			args,
			callback(r) {
				if (!r._server_messages) {
					// msgbox.hide();
				}
				if (r.exc) {
					// if no onerror, assume callback will handle errors
					opts.onerror ? opts.onerror(r) : opts.callback(null, r);
					frappe.hide_progress();
					return;
				}
				var attachment = r.message;
				opts.loopcallback && opts.loopcallback();
				args.filename = attachment.file_name;
				args.file_url = attachment.file_url;
				opts.callback && opts.callback(attachment, r, args);
				$(document).trigger("upload_complete", attachment);
			},
			error(r) {
				// if no onerror, assume callback will handle errors
				opts.onerror ? opts.onerror(r) : opts.callback(null, null, r);
				frappe.hide_progress();
				return;
			}
		};

		// copy handlers etc from opts
		['queued', 'running', "progress", "always", "btn"].forEach(key => {
			if (opts[key]) ajax_args[key] = opts[key];
		});
		return frappe.call(ajax_args);
	},

	get_string(dataURI) {
		// remove filename
		var parts = dataURI.split(',');
		if (parts[0].indexOf(":") === -1) {
			var a = parts[2];
		} else {
			var a = parts[1];
		}

		return decodeURIComponent(escape(atob(a)));

	},

	validate_max_file_size(file_size) {
		var max_file_size = frappe.boot.max_file_size || 5242880;

		if (file_size > max_file_size) {
			// validate max file size
			frappe.throw(__("File size exceeded the maximum allowed size of {0} MB", [max_file_size / 1048576]));
		}
	},
	multifile_upload: function (fileobjs, args, opts = {}) {
		//loop through filenames and checkboxes then append to list
		var fields = [];
		for (var i = 0, j = fileobjs.length; i < j; i++) {
			var filename = fileobjs[i].name;
			fields.push({ 'fieldname': 'label1', 'fieldtype': 'Heading', 'label': filename });
			fields.push({ 'fieldname': filename + '_is_private', 'fieldtype': 'Check', 'label': 'Private', 'default': 1 });
		}

		var d = new frappe.ui.Dialog({
			'title': __('Make file(s) private or public?'),
			'fields': fields,
			primary_action() {
				var i = 0, j = fileobjs.length;
				d.hide();
				opts.loopcallback = function () {
					if (i < j) {
						args.is_private = d.fields_dict[fileobjs[i].name + "_is_private"].get_value();
						frappe.upload.upload_file(fileobjs[i], args, opts);
						i++;
					}
				};

				opts.loopcallback();
			}
		});
		d.show();
		opts.confirm_is_private = 0;
	}
};

// Name changed just to avoid naming conflicts
frappe.upload.SocketIOStreamUploader = class SocketIOStreamUploader {
	constructor() {
		frappe.socketio.socket.on('upload-file-request-chunk', (data) => {
			const place = data.currentSlice * this.chunk_size;
			const slice = this.file.slice(place, place + Math.min(this.chunk_size, this.file.size - place));

			if (this.on_progress) {
				// update progress
				this.on_progress(place / this.file.size * 100);
			}

			this.reader.readAsArrayBuffer(slice);
			this.started = true;
			this.keep_alive();
		});

		frappe.socketio.socket.on('upload-file-end', async (data) => {
			this.reader = null;
			this.file = null;
			frappe.call('latte.file_storage.file.upload_via_socketio', data).then(this.callback);
		});

		frappe.socketio.socket.on('upload-file-error', (data) => {
			this.disconnect(false);
			frappe.msgprint({
				title: __('Upload Failed'),
				message: data.error,
				indicator: 'red'
			});
		});

		frappe.socketio.socket.on('disconnect', () => {
			this.disconnect();
		});
	}

	async start({
		file = null, is_private = 0, filename = '', callback = null, on_progress = null,
		chunk_size = 24576, fallback = null,
		doctype = '',
		docname = '',
	} = {}) {
		const { message } = await frappe.call('latte.file_storage.file.authenticate_socketio_upload', {
			doctype,
			docname,
			is_private,
			filename,
		});
		this.upload_id = message;
		if (this.reader) {
			frappe.throw(__('File Upload in Progress. Please try again in a few moments.'));
		}

		function fallback_required() {
			return !frappe.boot.sysdefaults.use_socketio_to_upload_file || !frappe.socketio.socket.connected;
		}

		if (fallback_required()) {
			return fallback ? fallback() : frappe.throw(__('Socketio is not connected. Cannot upload'));
		}

		this.reader = new FileReader();
		this.file = file;
		this.chunk_size = chunk_size;
		this.callback = callback;
		this.on_progress = on_progress;
		this.fallback = fallback;
		this.started = false;

		this.reader.onload = () => {
			frappe.socketio.socket.emit('upload-file-upload-chunk', {
				upload_id: this.upload_id,
				is_private: is_private,
				name: filename,
				type: this.file.type,
				size: this.file.size,
				data: this.reader.result
			});
			this.keep_alive();
		};

		var slice = file.slice(0, this.chunk_size);
		this.reader.readAsArrayBuffer(slice);
	}

	keep_alive() {
		if (this.next_check) {
			clearTimeout(this.next_check);
		}
		this.next_check = setTimeout(() => {
			if (!this.started) {
				// upload never started, so try fallback
				if (this.fallback) {
					this.fallback();
				} else {
					this.disconnect();
				}
			}
			this.disconnect();
		}, 3000);
	}

	disconnect(with_message = true) {
		if (this.reader) {
			this.reader = null;
			this.file = null;
			frappe.hide_progress();
			if (with_message) {
				frappe.msgprint({
					title: __('File Upload'),
					message: __('File Upload Disconnected. Please try again.'),
					indicator: 'red'
				});
			}
		}
	}
}

frappe.ui.form.ControlAttach.prototype.set_upload_options = function() {
	var me = this;
	this.upload_options = {
		parent: this.dialog.get_field("upload_area").$wrapper,
		args: {},
		allow_multiple: 0,
		max_width: this.df.max_width,
		max_height: this.df.max_height,
		options: this.df.options,
		btn: this.dialog.set_primary_action(__("Upload")),
		on_no_attach: function() {
			// if no attachmemts,
			// check if something is selected
			var selected = me.dialog.get_field("select").get_value();
			if(selected) {
				me.parse_validate_and_set_in_model(selected);
				me.dialog.hide();
				me.frm.save();
			} else {
				frappe.msgprint(__("Please attach a file or set a URL"));
			}
		},
		callback: function(attachment) {
			me.on_upload_complete(attachment);
			me.dialog.hide();
		},
		onerror: function() {
			me.dialog.hide();
		}
	};

	if ("is_private" in this.df) {
		this.upload_options.is_private = this.df.is_private;
	}

	if(this.frm) {
		this.upload_options.args = {
			from_form: 1,
			doctype: this.frm.doctype,
			docname: this.frm.docname
		};
	} else {
		this.upload_options.on_attach = function(datauri_obj, dataurl, fileobj) {
			me.dialog.hide();
			me.fileobj = datauri_obj;
			me.file = fileobj;
			me.dataurl = dataurl;
			if(me.on_attach) {
				me.on_attach();
			}
			if(me.df.on_attach) {
				me.df.on_attach(datauri_obj, dataurl);
			}
			me.on_upload_complete();
		};
	}
}