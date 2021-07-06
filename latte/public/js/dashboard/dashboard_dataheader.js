
latte.Dashboard.DataSlice.DataHeader = class GenericDashboardDataHeader {
    constructor(data_slice, data_header) {
        this.data_slice = data_slice;
        this.data_header = data_header;
    }

    set_title() {
        const _ = this.data_header.find('.title');
        $(_).empty().html(this.data_slice.doc.title);
    }

    enable_edit() {
        this.ds_edit = $(`<div class="pull-right" style="padding-left: 5px;">
        <a><span class="glyphicon glyphicon-edit"></span>
        </a>
        </div>`);
        const _that = this;
        $(this.ds_edit).find('a').click(function() {
            frappe.set_route('Form', 'Dashboard Data Slice', _that.data_slice.doc.name)
        });
        if (this.data_header.find) {
            $(this.ds_edit).prependTo(this.data_header.find('.buttons'));
        } else {
            $(this.ds_edit).appendTo(this.data_slice.chart_container);
        }
    }
}

latte.Dashboard.DataSlice.ActionDataHeader = class DashboardActionDataHeader extends latte.Dashboard.DataSlice.DataHeader {
    constructor(data_slice, data_header) {
        super(data_slice, data_header);
    }

    set_download_grid() {
        $(this.data_header).find('.buttons').empty();
        let _that = this;
        let actions = [
            {
                label: __("CSV"),
                action: 'action-download-csv',
                handler: () => {
                    new utils.XlsExport(_that.getExportData()).exportToCSV();
                }
            },
            {
                label: __("Excel"),
                action: 'action-download-excel',
                handler: () => {
                    new utils.XlsExport(_that.getExportData()).exportToXLS();
                }
            }
        ];

        this.grid_dl = $(`
            <div class="grid-btn dt-dwn" style="display: inline-block;"></div>
            <div class="slice-menu-btn-group" style="float: right; ">
            <button type="button" class="btn btn-default btn-sm dropdown-toggle" data-toggle="dropdown" aria-expanded="false">       
            <i class="glyphicon glyphicon-arrow-down"></i></span>
            </button>
                <ul class="dropdown-menu" role="menu">
                    ${actions.map(action =>
                        `<li class="user-action"><a data-action="${action.action}" class="grey-link">${action.label}</a></li>`
                    ).join('')}
                </ul>
            </div>
        `);
        this.grid_dl.find("li a").each((i, o) => {
            const action = o.dataset.action;
            $(o).click(actions.find(a => a.action === action));
        });
        this.grid_dl.appendTo($(this.data_header).find('.buttons'));
    }

    set_actions() {
        // Check if Report Button reqd.
        if (this.data_slice.doc.grid_action && this.data_slice.doc.grid_action.length > 0) {
            $(this.data_header).find('.buttons .grid-btn').empty();
            let doc = this;
            let actions = this.data_slice.doc.grid_action.map((ga) => {
                return {
                    label: __(ga.label),
                    action: `${ga.label}-butt`,
                    handler: () => {
                        Promise.resolve(eval(`(() => {
                                let dashboard = latte.dashboard;
                                let slice = doc;
                                let action = this;
                                    ${ga.script || ''}
                                })()`)
                            ).then(function (val) {
                                latte.dashboard.set_filters({
                                    'key': '_updated',
                                    'value': new Date().getTime()
                                });
                                doc.refresh();
                            }).catch((err) => {
                                doc.refresh();
                                frappe.throw("Error Occurred while executing Action");
                            });
                    }
                }
            })
            this.action_bt = $(`<div class="grid-btn dt-acts">
                ${actions.map(action => `
                <button class="btn btn-sm" data-action="${action.action}" style="margin-right: 2px;">
                    <span>${action.label}</span>`).join('')}
                </button>
            </div>`);
            this.action_bt.find("button[data-action]").each((i, o) => {
                const action = o.dataset.action;
                $(o).click(actions.find(a => a.action === action));
            });

            this.action_bt.prependTo($(this.data_header).find('.buttons .grid-btn'));
            this.data_header.find('.grid-btn.dt-acts button').hide();
        }
    }

    show_btns(flag) {
        flag ? this.data_header.find('.grid-btn.dt-acts button').show() :
            this.data_header.find('.grid-btn.dt-acts button').hide();
    }

    getExportData() {
        return this.data_slice.datamanager.data.obj;
    }
}

latte.Dashboard.DataSlice.DataHeader.Grid = class DashboardGridActionDataHeader extends latte.Dashboard.DataSlice.ActionDataHeader {
    getExportData() {
        // Checking if first checkbox checked. All is checked
        var sel_rows = this.data_slice.datatable.rowmanager.getCheckedRows();
        if (!sel_rows.length) {
            return this.data_slice.datamanager.data.response.data;
        }
        let values = []
        sel_rows.forEach((i) => {
            values.push(this.data_slice.datamanager.data.response.data[i]);
        })
        return values
    }
}

latte.Dashboard.DataSlice.DataHeader.List = class DashboardListActionDataHeader extends latte.Dashboard.DataSlice.ActionDataHeader {

} 
