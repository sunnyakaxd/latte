// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// My HTTP Request

frappe.xcall = function (method, params, cache = false, type = "POST") {
  return new Promise((resolve, reject) => {
    frappe.call({
      method: method,
      args: params,
      type,
      callback: (r) => {
        resolve(r.message);
      },
      cache: cache,
      error: (r) => {
        reject(r.message);
      },
    });
  });
};

frappe.registerServiceWorker = async function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    const registration = await navigator.serviceWorker.getRegistration("/desk");
    navigator.serviceWorker
      .register("/assets/latte/js/latte-service-worker.js", {
        scope: "/desk",
      })
      .then(
        function (registration) {
          // Registration was successful
          console.log(
            "ServiceWorker registration successful with scope: ",
            registration.scope
          );
        },
        function (err) {
          // registration failed :(
          console.log("ServiceWorker registration failed: ", err);
        }
      );
  }
};

frappe.registerServiceWorker();

frappe.isServiceWorkerActive = async function () {
  try {
    if (window.isServiceWorkerActive) {
      return true;
    }
    const r = await navigator.serviceWorker.getRegistration("/desk");
    if (r) {
      window.isServiceWorkerActive = true;
      return true;
    } else {
      window.isServiceWorkerActive = false;
      return false;
    }
  } catch (e) {
    return e;
  }
};

// generic server call (call page, object)
frappe.GET_SET = new Set([
  "frappe.desk.doctype.desktop_icon.desktop_icon.get_module_icons",
  "frappe.model.db_query.get_list",
  "frappe.core.doctype.user_permission.user_permission.get_user_permissions",
  "frappe.client.get_value",
  "frappe.client.get",
  "frappe.desk.moduleview.get",
]);

frappe.call = function (opts) {
  // console.log("CALLLED", opts);
  // if (!frappe.is_online() || !frappe.isServiceWorkerActive()) {
  //   frappe.show_alert(
  //     {
  //       indicator: "orange",
  //       message: __("You are not connected to Internet. Retry after sometime."),
  //     },
  //     3
  //   );
  //   return;
  // }
  if (typeof arguments[0] === "string") {
    opts = {
      method: arguments[0],
      args: arguments[1],
      callback: arguments[2],
    };
  }

  if (opts.quiet) {
    opts.no_spinner = true;
  }
  var args = $.extend({}, opts.args);

  // cmd
  if (opts.module && opts.page) {
    args.cmd =
      opts.module + ".page." + opts.page + "." + opts.page + "." + opts.method;
  } else if (opts.doc) {
    $.extend(args, {
      cmd: "runserverobj",
      docs: frappe.get_doc(opts.doc.doctype, opts.doc.name),
      method: opts.method,
      args: opts.args,
    });
  } else if (opts.method) {
    args.cmd = opts.method;
  }

  var callback = function (data, response_text) {
    if (data.task_id) {
      // async call, subscribe
      frappe.socketio.subscribe(data.task_id, opts);

      if (opts.queued) {
        opts.queued(data);
      }
    } else if (opts.callback) {
      // ajax
      return opts.callback(data, response_text);
    }
  };

  if (args.cmd) {
    opts.url = `/api/method/${args.cmd}`;
    // console.log(args.cmd, frappe.GET_SET.has(args.cmd));
    if (frappe.GET_SET.has(args.cmd)) {
      opts.type = "GET";
    }
    delete args.cmd;
  }

  return frappe.request.call({
    type: opts.type || "POST",
    args: args,
    success: callback,
    error: opts.error,
    always: opts.always,
    btn: opts.btn,
    freeze: opts.freeze,
    freeze_message: opts.freeze_message,
    // show_spinner: !opts.no_spinner,
    async: opts.async,
    url: opts.url || frappe.request.url,
    cache: opts.cache,
  });
};

frappe.request.call = function (opts) {
  frappe.request.prepare(opts);

  var statusCode = {
    200: function (data, xhr) {
      opts.success_callback && opts.success_callback(data, xhr.responseText);
    },
    401: function (xhr) {
      if (
        frappe.app.session_expired_dialog &&
        frappe.app.session_expired_dialog.display
      ) {
        frappe.app.redirect_to_login();
      } else {
        frappe.app.handle_session_expired();
      }
    },
    404: function (xhr) {
      frappe.msgprint({
        title: __("Not found"),
        indicator: "red",
        message: __("The resource you are looking for is not available"),
      });
    },
    403: function (xhr) {
      if (frappe.get_cookie("sid") === "Guest") {
        // session expired
        frappe.app.handle_session_expired();
      } else if (xhr.responseJSON && xhr.responseJSON._error_message) {
        frappe.msgprint({
          title: __("Not permitted"),
          indicator: "red",
          message: xhr.responseJSON._error_message,
        });

        xhr.responseJSON._server_messages = null;
      } else if (xhr.responseJSON && xhr.responseJSON._server_messages) {
        var _server_messages = JSON.parse(xhr.responseJSON._server_messages);

        // avoid double messages
        if (_server_messages.indexOf(__("Not permitted")) !== -1) {
          return;
        }
      } else {
        frappe.msgprint({
          title: __("Not permitted"),
          indicator: "red",
          message: __(
            "You do not have enough permissions to access this resource. Please contact your manager to get access."
          ),
        });
      }
    },
    508: function (xhr) {
      frappe.utils.play_sound("error");
      frappe.msgprint({
        title: __("Please try again"),
        indicator: "red",
        message: __(
          "Another transaction is blocking this one. Please try again in a few seconds."
        ),
      });
    },
    413: function (data, xhr) {
      frappe.msgprint({
        indicator: "red",
        title: __("File too big"),
        message: __("File size exceeded the maximum allowed size of {0} MB", [
          (frappe.boot.max_file_size || 5242880) / 1048576,
        ]),
      });
    },
    417: function (xhr) {
      var r = xhr.responseJSON;
      if (!r) {
        try {
          r = JSON.parse(xhr.responseText);
        } catch (e) {
          r = xhr.responseText;
        }
      }

      opts.error_callback && opts.error_callback(r);
    },
    501: function (data, xhr) {
      if (typeof data === "string") data = JSON.parse(data);
      opts.error_callback && opts.error_callback(data, xhr.responseText);
    },
    500: function (xhr) {
      frappe.utils.play_sound("error");
      frappe.msgprint({
        message: __(
          "Server Error: Please check your server logs or contact tech support."
        ),
        title: __("Something went wrong"),
        indicator: "red",
      });
      try {
        opts.error_callback && opts.error_callback();
        frappe.request.report_error(xhr, opts);
      } catch (e) {
        frappe.request.report_error(xhr, opts);
      }
    },
    504: function (xhr) {
      frappe.msgprint(__("Request Timed Out"));
      opts.error_callback && opts.error_callback();
    },
    502: function (xhr) {
      frappe.msgprint(__("Internal Server Error"));
    },
  };

  var ajax_args = {
    url: opts.url || frappe.request.url,
    data: opts.args,
    type: opts.type,
    dataType: opts.dataType || "json",
    async: opts.async,
    headers: {
      "X-Frappe-CSRF-Token": frappe.csrf_token,
      Accept: "application/json",
      "X-Frappe-CMD": (opts.args && opts.args.cmd) || "" || "",
    },
    cache: opts.cache,
  };

  if (opts.args && opts.args.doctype) {
    ajax_args.headers["X-Frappe-Doctype"] = opts.args.doctype;
  }

  frappe.last_request = ajax_args.data;

  return $.ajax(ajax_args)
    .done(function (data, textStatus, xhr) {
      try {
        if (typeof data === "string") data = JSON.parse(data);

        // sync attached docs
        if (data.docs || data.docinfo) {
          frappe.model.sync(data);
        }

        // sync translated messages
        if (data.__messages) {
          $.extend(frappe._messages, data.__messages);
        }

        // callbacks
        var status_code_handler = statusCode[xhr.statusCode().status];
        if (status_code_handler) {
          status_code_handler(data, xhr);
        }
      } catch (e) {
        console.log("Unable to handle success response"); // eslint-disable-line
        console.trace(e); // eslint-disable-line
      }
    })
    .always(function (data, textStatus, xhr) {
      try {
        if (typeof data === "string") {
          data = JSON.parse(data);
        }
        if (data.responseText) {
          var xhr = data;
          data = JSON.parse(data.responseText);
        }
      } catch (e) {
        data = null;
        // pass
      }
      frappe.request.cleanup(opts, data);
      if (opts.always) {
        opts.always(data);
      }
    })
    .fail(function (xhr, textStatus) {
      try {
        var status_code_handler = statusCode[xhr.statusCode().status];
        if (status_code_handler) {
          status_code_handler(xhr);
        } else {
          // if not handled by error handler!
          opts.error_callback && opts.error_callback(xhr);
        }
      } catch (e) {
        console.log("Unable to handle failed response"); // eslint-disable-line
        console.trace(e); // eslint-disable-line
      }
    });
};
