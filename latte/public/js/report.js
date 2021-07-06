function add_show_query(frm) {
  if (
    frm.doc.report_type === "Query Report" &&
    (frappe.user_roles.includes("System Manager") ||
      frappe.user_roles.includes("Developer"))
  ) {
    frm.add_custom_button("Show Query", () => {
      eval(frm.doc.javascript);
      frappe.prompt(
        [
          {
            fieldname: "__user",
            fieldtype: "Link",
            label: "User",
            reqd: 1,
            default: frappe.session.user,
            options: "User",
          },
        ].concat(frappe.query_reports[frm.doc.name]?.filters || []),
        (filters) => {
          filters.__blank_run = 1;
          frappe.call("frappe.desk.query_report.run", {
            report_name: frm.doc.name,
            filters: JSON.stringify(filters),
          });
        }
      );
    });
  }
}
frappe.ui.form.on("Report", {
  refresh(frm) {
    frm.remove_custom_button("Show Report");
    frm.add_custom_button(
      "Show Report",
      function () {
        switch (frm.doc.report_type) {
          case "Report Builder":
            frappe.set_route(
              "List",
              frm.doc.ref_doctype,
              "Report",
              frm.doc.name
            );
            break;
          case "Query Report":
            frappe.set_route("query-report", frm.doc.name);
            break;
          case "Script Report":
            frappe.set_route("query-report", frm.doc.name);
            break;
          case "Jupyter Report":
            frappe.set_route("query-report", frm.doc.name);
            break;
        }
      },
      "fa fa-table"
    );
    add_show_query(frm);
  },
});
