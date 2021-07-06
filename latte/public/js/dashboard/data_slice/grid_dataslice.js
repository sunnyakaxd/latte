latte.Dashboard.DataSlice.Grid = class DashboardGridDataSlice extends latte.Dashboard.DataSlice {

    /**
     * Overriden default implementation for GridSlice
     */
    render() {
        super.render();

        this.report_settings = {};

        frappe.run_serially([
            () => this.set_grid_settings(),
            () => this.show_grid(),
            () => (() => {
                let obj = this;
                this.onclick = this.onclick || [];
                // Run Post JS
                this.run_post_js();
                
                let click_impl = Object.keys(obj.onclick);
                click_impl.forEach((click_ele) => {
                    let ele_index = (obj.datatable.columnmanager.getColumns().find((doc) => doc.fieldname == click_ele ) || {}).colIndex ;
                    Array.prototype.forEach.call(obj.chart_container.find('.dt-scrollable [data-col-index="' + ele_index + '"]'), (doc) => {
                        let rowIndex = $(doc).attr('data-row-index');
                        $(doc).click(() =>
                            obj.onclick[click_ele](
                                obj.datatable.getCell(ele_index, rowIndex).content,
                                (() => {
                                    let rows = {};
                                    obj.datatable.getRows()[rowIndex].forEach((it) => {
                                        rows[it.column.content] = it.content
                                    })
                                    return rows;
                                })()
                            ));
                    });
                });
            })(),
            () => (() => {
                const _that = this;
                latte.dashboard.grid.on('change', function (event, items) {
                    $.each(items, (i, ix) => {
                        if (($(ix.el).find('.ds-grid') || []).length > 0) {
                            _that.resize_grid(ix.el);
                        }
                    });
                });
            })()
        ])
    }

    set_grid_settings() {
        if (!this.doc.report) {
            return;
        }

        if (frappe.query_reports[this.doc.report]) {
            this.report_settings = frappe.query_reports[this.doc.report];
            return;
        }

        this._load_script = (new Promise(resolve => frappe.call({
            method: 'frappe.desk.query_report.get_script',
            args: { report_name: this.doc.report },
            callback: resolve
        }))).then(r => {
            frappe.dom.eval(r.message.script || '');
            return r;
        }).then(r => {
            return frappe.after_ajax(() => {
                this.report_settings = frappe.query_reports[this.doc.report];
                this.report_settings.html_format = r.message.html_format;
            });
        });

        return this._load_script;
    }

    show_grid() {
        var _that = this;
        if (!this.datamanager.data.response.columns) {
            this.data = this.datamanager.data.response.values;
            this.columns = this.datamanager.data.response.keys;
        } else
            this.columns = this.prepare_columns(this.datamanager.data.response.columns)
        this.data = this.prepare_data(this.datamanager.data.response.result)

        if ((this.columns).length < 10) {
            this.layout = 'fluid';
        }
        else {
            this.layout = 'fixed';
        }
        $.extend(this.datamanager.data.response, {
            checkboxColumn: true,
            layout: this.layout,
            noDataMessage: "<div class='nodata'>Nothing to show</div>",
            inlineFilters: true,
            dropdownButton: '<span class="fa fa-chevron-down"></span>',
            checkedRowStatus: true,
            dynamicRowHeight: true,
            columns: this.columns, //this.columns,
            data: this.data, //this.data,
            events: {
                onCheckRow(row) {
                    if (_that.chart_container.find('.datatable input:checkbox:checked').length > 0) {                       
                        _that.data_header.show_btns(true);
                    } else {
                        _that.data_header.show_btns(false);
                    }
                }
            }
        });

        if (this.data.length == 0) {
            this.is_empty(true)
        }

        this.datatable = new latte.DataTable(this.chart_container.find(".data-wrapper")[0], this.datamanager.data.response);
        if (this.doc.grid_download)
            this.data_header.set_download_grid();
        this.data_header.set_actions();
        this.resize_grid(this.chart_container);
    }

    prepare_data(data) {
        if (!data) return;
        return data.map(row => {
            let row_obj = {};
            if (Array.isArray(row)) {
                this.columns.forEach((column, i) => {
                    row_obj[column.id] = row[i] || null;
                });

                return row_obj;
            }
            return row;
        });
    }

    prepare_columns(columns) {
        return columns.map(column => {
            if (typeof column === 'string') {
                if (column.includes(':')) {
                    let [label, fieldtype, width] = column.split(':');
                    let options;

                    if (fieldtype.includes('/')) {
                        [fieldtype, options] = fieldtype.split('/');
                    }

                    column = {
                        label,
                        fieldname: label,
                        fieldtype,
                        width,
                        options
                    };
                } else {
                    column = {
                        label: column,
                        fieldname: column,
                        fieldtype: 'Data'
                    };
                }
            }

            const format_cell = (value, row, column, data) => {
                return frappe.format(value || '', column,
                    { for_print: false, always_show_decimals: true }, data);
            };

            let compareFn = null;
            if (column.fieldtype === 'Date') {
                compareFn = (cell, keyword) => {
                    if (!cell.content) return null;
                    if (keyword.length !== 'YYYY-MM-DD'.length) return null;

                    const keywordValue = frappe.datetime.user_to_obj(keyword);
                    const cellValue = frappe.datetime.str_to_obj(cell.content);
                    return [+cellValue, +keywordValue];
                };
            }

            return Object.assign(column, {
                id: column.fieldname,
                name: column.label,
                width: parseInt(column.width) || null,
                editable: false,
                compareValue: compareFn,
                format: (value, row, column, data) => {
                    if (this.report_settings.formatter) {
                        return this.report_settings.formatter(value, row, column, data, format_cell);
                    }
                    return format_cell(value, row, column, data);
                }
            });
        });
    }

    resize_grid(el) {
        this.datatable.refresh();
        const $el = $(el).closest('.grid-stack-item');
        const _grid_ht = $el.height();
        const _dataheader_ht = $el.find('.data-header-wrapper').height();
        const _dtheader_ht = $el.find('.data-wrapper .datatable .dt-header').height();
        $el.find('.dt-scrollable').width('auto')
            // .height($el.height()-$el.find('.data-header-wrapper').height()-72);
            .height(_grid_ht - _dataheader_ht - _dtheader_ht - 4);
    }

}


/**
 * TODO - Legacy Code
 */
latte.DashboardLegacy.DataSlice.Grid = class DashboardLegacyGridDataSlice extends latte.DashboardLegacy.DataSlice {
    render() {
        super.render();

        this.report_settings = {};

        frappe.run_serially([
            () => (() => {
                this.set_grid_title();
                this.add_grid_actions_container();
            })(),
            () => this.set_grid_settings(),
            () => this.show_grid(),
            () => (() => {
                let obj = this;
                obj.onclick = obj.onclick || [];
                // Can use obj.onclic['coulumn_name'] = fn
                eval(obj.doc.js || '');
                let click_impl = Object.keys(obj.onclick);
                click_impl.forEach((click_ele) => {
                    let ele_index = obj.datatable.columnmanager.getColumns().find((doc) => doc.fieldname == click_ele ).colIndex ;
                    Array.prototype.forEach.call(obj.chart_container.find('.dt-scrollable [data-col-index="' + ele_index + '"]'), (doc) => {
                        let rowIndex = $(doc).attr('data-row-index');
                        $(doc).click(() =>
                            obj.onclick[click_ele](
                                obj.datatable.getCell(ele_index, rowIndex).content,
                                (() => {                                    
                                    let rows = {};
                                    obj.datatable.getRows()[rowIndex].forEach((it) => {
                                        rows[it.column.content] = it.content
                                    })
                                    return rows;
                                })()
                            ));
                    });
                });
            })(),
            () => {
                $(document).trigger('grid-refreshed', [this.doc.data_slice_name]);
            }
        ])
    }

    set_grid_settings() {
        if (!this.doc.report) {
            return;
        }

        if (frappe.query_reports[this.doc.report]) {
            this.report_settings = frappe.query_reports[this.doc.report];
            return;
        }

        this._load_script = (new Promise(resolve => frappe.call({
            method: 'frappe.desk.query_report.get_script',
            args: { report_name: this.doc.report },
            callback: resolve
        }))).then(r => {
            frappe.dom.eval(r.message.script || '');
            return r;
        }).then(r => {
            return frappe.after_ajax(() => {
                this.report_settings = frappe.query_reports[this.doc.report];
                this.report_settings.html_format = r.message.html_format;
            });
        });

        return this._load_script;
    }

    show_grid() {
        var _that = this;
        if (!this.datamanager.data.response.columns) {
            this.data = this.datamanager.data.response.values;
            this.columns = this.datamanager.data.response.keys;
        } else
            this.columns =  this.prepare_columns(this.datamanager.data.response.columns)
        this.data = this.prepare_data(this.datamanager.data.response.result)

        if( (this.columns).length  < 10 ) {
            this.layout = 'fluid';
        }
        else {
            this.layout = 'fixed';
        }
        $.extend(this.datamanager.data.response, {
            checkboxColumn: true,
            layout: this.layout,
            noDataMessage: "<div class='nodata'>Nothing to show</div>",
            inlineFilters: true,
            dropdownButton: '<span class="fa fa-chevron-down"></span>',
            checkedRowStatus: true,
            columns: this.columns, //this.columns,
            data: this.data, //this.data,
            events: {
                onCheckRow(row) {
                    if(_that.chart_container.find('.datatable input:checkbox:checked').length > 0) {
                        _that.chart_container.find('.grid-btn.dt-acts button').show();
                        _that.chart_container.find('.btn-group.actions-btn-group button').show();
                        // _that.chart_container.find('.grid-btn.dt-dwn button').show();
                    } else {
                        _that.chart_container.find('.grid-btn.dt-acts button').hide();
                        _that.chart_container.find('.btn-group.actions-btn-group button').hide();
                        // _that.chart_container.find('.grid-btn.dt-dwn button').hide();
                    }
                }
            }
        });

        if (this.data.length == 0){
            this.is_empty(true)
        }

        this.datatable = new latte.DataTable(this.chart_container.find(".data-wrapper")[0], this.datamanager.data.response);
        if (this.doc.grid_view_port)
            this.chart_container.find('.datatable .dt-scrollable').css('height', `${this.doc.grid_view_port}vw`);
        
        // Empty grid-buttons
        if (this.doc.grid_download)
            this.set_download_grid();
        this.set_actions();
    }

    add_grid_actions_container() {
        this.chart_container.find(".data-header-wrapper .grid-buttons").remove();
        this.chart_container.find('.data-header-wrapper').prepend($('<div class="grid-buttons" style="display: flex; justify-content: flex-end; width: 100%"></div>'));
    }

    prepare_data(data) {
        if (!data) return;
        return data.map(row => {
            let row_obj = {};
            if (Array.isArray(row)) {
                this.columns.forEach((column, i) => {
                    row_obj[column.id] = row[i] || null;
                });

                return row_obj;
            }
            return row;
        });
    }

    prepare_columns(columns) {
        return columns.map(column => {
            if (typeof column === 'string') {
                if (column.includes(':')) {
                    let [label, fieldtype, width] = column.split(':');
                    let options;

                    if (fieldtype.includes('/')) {
                        [fieldtype, options] = fieldtype.split('/');
                    }

                    column = {
                        label,
                        fieldname: label,
                        fieldtype,
                        width,
                        options
                    };
                } else {
                    column = {
                        label: column,
                        fieldname: column,
                        fieldtype: 'Data'
                    };
                }
            }

            const format_cell = (value, row, column, data) => {
                return frappe.format(value || '', column,
                    {for_print: false, always_show_decimals: true}, data);
            };

            let compareFn = null;
            if (column.fieldtype === 'Date') {
                compareFn = (cell, keyword) => {
                    if (!cell.content) return null;
                    if (keyword.length !== 'YYYY-MM-DD'.length) return null;

                    const keywordValue = frappe.datetime.user_to_obj(keyword);
                    const cellValue = frappe.datetime.str_to_obj(cell.content);
                    return [+cellValue, +keywordValue];
                };
            }

            return Object.assign(column, {
                id: column.fieldname,
                name: column.label,
                width: parseInt(column.width) || null,
                editable: false,
                compareValue: compareFn,
                format: (value, row, column, data) => {
                    if (this.report_settings.formatter) {

                        return this.report_settings.formatter(value, row, column, data, format_cell);
                    }
                    return format_cell(value, row, column, data);
                }
            });
        });
    }


    set_download_grid() {

        let _that = this;
        let actions = [
            {
                label: __("CSV"),
                action: 'action-download-csv',
                handler: () => {
                    new utils.XlsExport(_that.getSelectedData(true)).exportToCSV();
                }
            },
            {
                label: __("Excel"),
                action: 'action-download-excel',
                handler: () => {
                    new utils.XlsExport(_that.getSelectedData(true)).exportToXLS();
                }
            }
        ];

        this.grid_dl = $(`
            <div class="grid-btn dt-dwn" style="z-index: 100; text-align: right; margin: 0px 15px 6px 0px;">
            ${actions.map(action =>
                `<button style="background-color: rgba(0, 0, 0, 0.8); margin-right: 2px;"
                        class="btn btn-primary btn-sm primary-action" data-action="${action.action}">
                    <i class="visible-xs icon-refresh"></i>
                    <span class="hidden-xs">${action.label} <i class="glyphicon glyphicon-arrow-down"></i></span>
                </button>`
            ).join('')} </div>
        `);
        this.grid_dl.find("button").each((i, o) => {
            const action = o.dataset.action;
            $(o).click(actions.find(a => a.action === action));
        });
        this.grid_dl.appendTo($(this.chart_container).find('.grid-buttons'));
        // this.chart_container.find('.grid-btn.dt-dwn button').hide();
    }

    set_actions() {
        // Check if Report Button reqd.
        // $(this.chart_container).parent('.row').find('.grid-btn.dt-acts').remote();
        if(this.doc.grid_action && this.doc.grid_action.length > 0) {
            let doc = this;
            let actions = this.doc.grid_action.map((ga) => {
                return {
                        label: __(ga.label),
                        action: `${ga.label}-butt`,
                        as_action: ga.as_action,
                        handler: () => {
                            Promise.resolve(eval(ga.script || ''))
                                .then(function(val) {
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

            const ind_actions = actions.filter(action => !action.as_action)
            const grp_actions = actions.filter(action => action.as_action)

            if(ind_actions.length) {
                this.action_bt = $(`<div class="grid-btn dt-acts" style="z-index: 100; top: 5rem;">
                    ${ind_actions.map(action => `
                    <button class="btn btn-primary btn-sm primary-action" data-action="${action.action}" style="margin-right: 2px;">
                        <span>${action.label}</span>`).join('')}
                    </button>
                </div>`);

                this.action_bt.prependTo($(this.chart_container).find('.grid-buttons'));
                this.action_bt.find("button[data-action]").each((i, o) => {
                    const action = o.dataset.action;
                    $(o).click(ind_actions.find(a => a.action === action));
                });
            }

            if(grp_actions.length) {
                this.action_drop_actions = $(`
                    <div class="btn-group actions-btn-group" style="margin-right:5px">
                    <button type="button" class="btn btn-danger btn-sm dropdown-toggle" data-toggle="dropdown" aria-expanded="false">
                        <span class="hidden-xs"> Actions
                            <span class="caret"></span>
                        </span>
                        <span class="visible-xs octicon octicon-check"></span>
                    </button>
                    <ul class="dropdown-menu custom-dialog-actions" role="menu">
                        ${grp_actions.map(action => `
                            <li class="user-action" data-action="${action.action}">
                                <a>${action.label}</a>`).join('')}
                            </li>
                    </ul>
                </div>`);

                this.action_drop_actions.prependTo($(this.chart_container).find('.grid-buttons'))
                this.action_drop_actions.find("li[data-action]").each((i, o) => {
                    const action = o.dataset.action;
                    $(o).click(grp_actions.find(a => a.action === action));
                });
            }

            this.chart_container.find('.grid-btn.dt-acts button').hide();
            this.chart_container.find('.btn-group.actions-btn-group button').hide();
        }
    }

    getSelectedData(as_dict) {
        // Checking if first checkbox checked. All is checked
        var sel_rows = this.datatable.rowmanager.getCheckedRows();

        if (!sel_rows.length) {
            return this.datamanager.data.response.data;
        }

        let values = []
        sel_rows.forEach((i) => {
            values.push(this.datamanager.data.response.data[i]);
        })

        return values
    }

}