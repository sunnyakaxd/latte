import BindingModel from '../binding/binding_model.js';
import BindingNode from '../binding/binding_node.js';

latte.Dashboard.DataSlice.List = class DashboardListDataSlice extends latte.Dashboard.DataSlice {
    update_config() {
        this.config = $.extend({}, this.config, {
            'data_source': 'multiple',
            'dom_binding': 'async'
        })
    }

    render() {
        $(this.chart_container.find(".data-wrapper")).data('template', 
            `<div class="dashboard-list" style="background-color: ${this.doc.background_color || 'var(--dashboard-background-color)'}; color: ${this.doc.text_color || 'var(--dashboard-font-color)'}">
                ${this.doc.html_template || ""}
            </div>`);	
        let obj = this;
        this.binding_node = new BindingNode(this.chart_container.find(".data-wrapper"));
        this.binding_model = new BindingModel();
        this.binding_model.add_callback(function () {
            obj.binding_node.update(obj.binding_model, obj.doc, 'multiple');
            obj.run_post_js();
        });
        
        if (this.doc.grid_download)
            this.data_header.set_download_grid();
    }
}

/**
 * TODO - Legacy Code
 */
latte.DashboardLegacy.DataSlice.List = class DashboardLegacyListDataSlice extends latte.DashboardLegacy.DataSlice {
    update_config() {
        this.config = $.extend({}, this.config, {
            'data_source': 'multiple',
            'dom_binding': 'async'
        })
    }
    render() {
        $(this.chart_container.find(".data-wrapper")).data('template', 
            `<div class="dashboard-count" style="background-color: ${this.doc.background_color || 'var(--dashboard-background-color)'}; color: ${this.doc.text_color || 'var(--dashboard-font-color)'}">
                ${this.doc.html_template || ""}
            </div>`);	
        let obj = this;
        this.set_grid_title();
        this.binding_node = new BindingNode(this.chart_container.find(".data-wrapper"));
        this.binding_model = new BindingModel();
        this.binding_model.add_callback(function () {
            obj.binding_node.update(obj.binding_model, obj.doc, 'multiple');
            eval(obj.doc.js || '');
        });
    }
}