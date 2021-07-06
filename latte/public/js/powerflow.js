frappe.provide('latte');
latte.powerflow = latte.PowerFlow = class PowerFlow {
  constructor(frm) {
    this.frm = frm;
    if(this.frm.doc.__onload && this.frm.doc.__onload["__powerflow_meta"])
    {
      this.show_actions();
    }
  }

  hide_submit_cancel() {
    if (this.frm.is_dirty() !== 1 && !this.frm.doc.__islocal) {
      // hide submit and cancel, do not hide save
      this.frm.page.clear_actions();
    }
  }

  show_actions() {
    this.hide_submit_cancel();
    this.frm.page.clear_actions_menu();
    
    frappe.xcall('latte.business_process.powerflow.powerflow.get_current_actions', {
      doctype: this.frm.doc.doctype,
      docname: this.frm.doc.name,
    }).then((transitions) => {
      if(! transitions){
        return
      }
      
      transitions.forEach((transition) => {
       const me = this;
        this.frm.page.add_action_item(transition.action, () => {
          
          if (transition.is_reason_required) {
            const dialog = frappe.prompt([{
              fieldname: 'enter_manually',
              fieldtype: 'Check',
              label: 'Enter Manually',
              onchange() {
                if (dialog.get_value('enter_manually')) {
                  dialog.set_df_property('manual_reason', 'reqd', 1);
                  dialog.set_df_property('reason', 'reqd', 0);
                } else {
                  dialog.set_df_property('manual_reason', 'reqd', 0);
                  dialog.set_df_property('reason', 'reqd', 1);
                }
              },
            },
            {
              fieldname: 'reason',
              options: transition.valid_reason,
              fieldtype: 'Select',
              label: 'Reason',
              onchange() {
                dialog.fields_dict.manual_reason.set_input(undefined);
              },
              depends_on: 'eval:!doc.enter_manually',
              reqd: 1,
            },
            {
              fieldname: 'manual_reason',
              fieldtype: 'Data',
              label: 'Other Reason',
              reqd: 0,
              depends_on: 'eval:doc.enter_manually',
            },
            ], (values) => {
              let { reason } = values;
              if (values.enter_manually) {
                reason = values.manual_reason;
              }
              me.apply_powerflow(me.frm.doc, transition.action, reason);
            }, 'Please enter reason');
          }
          else
          {
            me.apply_powerflow(this.frm.doc, transition.action, '');
          }
        });
      });
    });
  }


  apply_powerflow(doc, action, reason) {
    frappe.dom.freeze(`Applying action: ${action}`);
    frappe.xcall('latte.business_process.powerflow.powerflow.execute_action', {
      doctype: this.frm.doc.doctype,
      docname: this.frm.doc.name,
      action,
      reason,
    }).then((response) => {
      this.frm.reload_doc()
      frappe.dom.unfreeze();
    }).catch((response_except) => {
      frappe.dom.unfreeze();
      this.frm.refresh();
    });
  }
};


for(const dt of frappe.boot.user.can_read) {
  frappe.ui.form.on(dt, {
    refresh(frm) {
      if (frm.doc.__onload && frm.doc.__onload.__powerflow_meta) {
        new latte.PowerFlow(frm);
      }
    }
  })
}
