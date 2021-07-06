frappe.ui.form.SuccessAction.prototype.show_alert = function show_alert() {
    const setting = this.setting;
    if (!setting) {
        return;
    }
    let message = setting.message;

    const $buttons = this.get_actions().map(action => {
        const $btn = $(`<button class="next-action"><span>${action.label}</span></button>`);
        $btn.click(() => action.action(this.form));
        return $btn;
    });

    const next_action_container = $(`<div class="next-action-container"></div>`);
    next_action_container.append($buttons);
    const html = next_action_container;

    frappe.show_alert({
        message: message,
        body: html,
        indicator: 'green',
    }, setting.action_timeout);
}