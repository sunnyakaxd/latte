latte.Dashboard.DataSlice.HTML = class DashboardHTMLDataSlice extends latte.Dashboard.DataSlice {
    render() {
        super.render();
        $(`<div class="${latte.dashboard.dashboard_doc.disable_position == 1 ? '': 'perfect-position'}">
            ${latte.DataMapper.generate_template_string(this.doc.html_template)({'doc': this.doc})}
            </div>`).appendTo(this.chart_container.find(".data-wrapper")[0]);
        $(this.chart_container.closest('.grid-stack-item-content'))
            .css({'background-color': this.doc.background_color || 'var(--dashboard-background-color)', 'color': this.doc.text_color || 'var(--dashboard-font-color)'});
    }
    refresh() {
        //this.chart_container.find('.chart-loading-state').removeClass('hide');
        //return new Promise((resolve) => resolve());
        this.render();
        this.run_post_js();
    }
}

/**
 * TODO - Legacy Code
 */
latte.DashboardLegacy.DataSlice.HTML = class DashboardHTMLDataSliceLegacy extends latte.DashboardLegacy.DataSlice {
    render() {
        super.render();
        $(`<div  style="background-color: ${this.doc.background_color || 'var(--dashboard-background-color)'}; color: ${this.doc.text_color || 'var(--dashboard-font-color)'}">
            ${latte.DataMapper.generate_template_string(this.doc.html_template)({'doc': this.doc})}
            </div>`).appendTo(this.chart_container.find(".data-wrapper")[0]);
    }
    refresh() {
        //this.chart_container.find('.chart-loading-state').removeClass('hide');
        //return new Promise((resolve) => resolve());
        this.render();
        let obj = this;
        eval(obj.doc.js || '');
    }
}