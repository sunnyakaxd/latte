frappe.provide("latte");

async function capture_reason(document_type, _field, active_state) {
  // for new creation do not ask reason
  if (cur_frm.doc.__islocal) {
    return;
  }

  // check config with document
  const { message } = await frappe.db.get_value(document_type,{name: cur_frm.doc.name,},_field);
  const db_state = message[_field];
  if (db_state === cur_frm.doc[_field]) {
    // no change in state
    return;
  }

  var _disabled;
  const current_state = Boolean(cur_frm.doc[_field])
  if (current_state === active_state) {
    _disabled = 0
  }
  if (current_state === !active_state) {
    _disabled = 1
  }
  return new Promise((resolve, reject) => {
    const dialog = new frappe.ui.Dialog({
      title: __("Please enter a Reason"),
      fields: [
        {
          fieldname: "reason",
          options: "Enable Reason",
          fieldtype: "Link",
          label: "Reason",
          reqd: 1,
          get_query() {
            return {
              query: "latte.utils.doc_status_tracker.get_enable_disable_reason",
              filters: {
                disabled: _disabled,
                doctype: cur_frm.doc.doctype,
              },
            };
          },
        },
      ],
    });

    if (_disabled === 1) {
      dialog.set_df_property("reason", "options", "Disable Reason");
    } else {
      dialog.set_df_property("reason", "options", "Enable Reason");
    }

    dialog.set_primary_action(__("Add Reasons"), (values) => {
      dialog.hide();
      const { reason } = values;
      frappe
        .xcall("latte.utils.doc_status_tracker.apply_doc_status_tracker", {
          ref_doctype: cur_frm.doc.doctype,
          docname: cur_frm.doc.name,
          reason,
          disabled: _disabled,
        })
        .then((newDoc) => {
          cur_frm.refresh();
        });
      resolve(values);
    });

    dialog.show();
  });
}

setTimeout(
  () =>
    frappe.db
      .get_list("Doc Status Tracker", {
        fields: ["document_type", "is_active", "tracking_field", "active_state"],
        filters: {"is_active": 1},
        limit: 1000,
      })
      .then((doctypes) => {
        doctypes.forEach(i => {
          frappe.ui.form.on(i.document_type, {
            before_save() {
              return capture_reason(i.document_type, i.tracking_field, Boolean(i.active_state));
            },
          });
        });
      }),
  0
);

/**
 * Function for rendering from another page outside desk.
 * Updating the frappe.Application.prototype.startup in desk.js
 */
latte.fireUpDashboard = () => {
  frappe.Application.prototype.startup = function () {
    frappe.socketio.init();
    frappe.model.init();

    if (frappe.boot.status === "failed") {
      frappe.msgprint({
        message: frappe.boot.error,
        title: __("Session Start Failed"),
        indicator: "red",
      });
      throw "boot failed";
    }

    this.load_bootinfo();
    this.load_user_permissions();
    // this.make_nav_bar();
    this.set_favicon();
    this.set_fullwidth_if_enabled();
    this.setup_analytics();

    frappe.ui.keys.setup();
    this.set_rtl();

    if (frappe.boot) {
      if (localStorage.getItem("session_last_route")) {
        window.location.hash = localStorage.getItem("session_last_route");
        localStorage.removeItem("session_last_route");
      }
    }

    // page container
    this.make_page_container();

    // route to home page
    frappe.route();
    if (!frappe.get_route_str().startsWith("dashboard/"))
      frappe.set_route("dashboard");

    // trigger app startup
    $(document).trigger("startup");

    this.start_notification_updates();

    $(document).trigger("app_ready");

    if (frappe.boot.messages) {
      frappe.msgprint(frappe.boot.messages);
    }

    if (frappe.boot.change_log && frappe.boot.change_log.length) {
      this.show_change_log();
    } else {
      this.show_notes();
    }

    this.show_update_available();

    if (frappe.ui.startup_setup_dialog && !frappe.boot.setup_complete) {
      frappe.ui.startup_setup_dialog.pre_show();
      frappe.ui.startup_setup_dialog.show();
    }

    // listen to csrf_update
    frappe.realtime.on("csrf_generated", function (data) {
      // handles the case when a user logs in again from another tab
      // and it leads to invalid request in the current tab
      if (data.csrf_token && data.sid === frappe.get_cookie("sid")) {
        frappe.csrf_token = data.csrf_token;
      }
    });

    frappe.realtime.on("version-update", function () {
      var dialog = frappe.msgprint({
        message: __(
          "The application has been updated to a new version, please refresh this page"
        ),
        indicator: "green",
        title: __("Version Updated"),
      });
      dialog.set_primary_action(__("Refresh"), function () {
        location.reload(true);
      });
      dialog.get_close_btn().toggle(false);
    });

    // listen to build errors
    this.setup_build_error_listener();

    if (frappe.sys_defaults.email_user_password) {
      var email_list = frappe.sys_defaults.email_user_password.split(",");
      for (var u in email_list) {
        if (email_list[u] === frappe.user.name) {
          this.set_password(email_list[u]);
        }
      }
    }

    if (!frappe.boot.developer_mode) {
      setInterval(function () {
        frappe.call({
          method:
            "frappe.core.page.background_jobs.background_jobs.get_scheduler_status",
          callback: function (r) {
            if (r.message[0] == __("Inactive")) {
              frappe.msgprint({
                title: __("Scheduler Inactive"),
                indicator: "red",
                message: __(
                  "Background jobs are not running. Please contact Administrator"
                ),
              });
            }
          },
        });
      }, 300000); // check every 5 minutes
    }
  };
};
