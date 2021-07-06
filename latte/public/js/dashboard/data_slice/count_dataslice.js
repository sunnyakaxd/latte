import BindingModel from '../binding/binding_model.js';
import BindingNode from '../binding/binding_node.js';

latte.Dashboard.DataSlice.Count = class DashboardCountDataSlice extends latte.Dashboard.DataSlice {
    update_config() {
        this.config = $.extend({}, this.config, {
            'data_source': 'multiple',
            'dom_binding': 'async'
        })
    }

    render() {
        $(this.chart_container.find(".data-wrapper")).data('template', 
            `<div class="dashboard-count ${latte.dashboard.dashboard_doc.disable_position == 1 ? '': 'perfect-position'}">
                ${this.doc.html_template || ""}
            </div>`);
        $(this.chart_container.closest('.grid-stack-item-content'))
            .css({'background-color': this.doc.background_color || 'var(--dashboard-background-color)', 'color': this.doc.text_color || 'var(--dashboard-font-color)'});
        let obj = this;
        this.binding_node = new BindingNode(this.chart_container.find(".data-wrapper"));
        this.binding_model = new BindingModel();
        this.binding_model.add_callback(function () {
            obj.binding_node.update(obj.binding_model, obj.doc);
            obj.run_post_js();
        });
        this.binding_model.model = {}
    }
}

/**
 * TODO - Legacy Code
 */
latte.DashboardLegacy.DataSlice.Count = class DashboardCountDataSliceLegacy extends latte.DashboardLegacy.DataSlice {
    update_config() {
        this.config = $.extend({}, this.config, {
            'data_source': 'multiple',
            'dom_binding': 'async'
        })
    }

    refresh() {
        // debugger
        if(this.doc.results_from) {
            this.render_from_grid();
            return
        }

        super.refresh();
        // debugger
    }

    render_from_grid() {
        const grid_slice = Object.keys(latte.dashboard.dashboard_doc.data_slices).filter(sl => sl.endsWith(this.doc.results_from));

        if(grid_slice.length
            && latte.dashboard.dashboard_doc.data_slices[grid_slice[0]].dashobj
            && latte.dashboard.dashboard_doc.data_slices[grid_slice[0]].dashobj.datatable
        ) {
            this.doc.count = latte.dashboard.dashboard_doc.data_slices[grid_slice[0]].dashobj.datatable.datamanager.data.length;
        } else {
            this.doc.count = 0;
        }
        this.render()
    }


    render() {
        $(this.chart_container.find(".data-wrapper")).data('template', 
            `<div class="dashboard-count" style="background-color: ${this.doc.background_color || 'var(--dashboard-background-color)'}; color: ${this.doc.text_color || 'var(--dashboard-font-color)'}">
                ${this.doc.html_template || ""}
            </div>`);
        let obj = this;
        this.binding_node = new BindingNode(this.chart_container.find(".data-wrapper"));
        this.binding_model = new BindingModel();
        this.binding_model.add_callback(function () {
            obj.binding_node.update(obj.binding_model, obj.doc);
            eval(obj.doc.js || '');
        });
        this.binding_model.model = {}
        this.is_loading(false)
    }
}