class BindingNode {
    constructor(node) {
        this.template = $(node).data('template');
        this.node = node
    }

    update(model) {
        let temp_template = this.template.slice(0)
        this.node.innerHTML = temp_template.replace(/\{\{\s?(\w+)\s?\}\}/g, (match, variable) => {
             return model[variable] || ''
        })
    }

    update(model, doc, upds="single") {
        let temp_template = this.template.slice(0);
        let html_template = latte.DataMapper
                .generate_template_string(temp_template || "");
        try {
            upds === 'multiple' ?
                (() => {
                    //$(this.node).html();
                    //debugger
                    // $(this.node).html(generated_html);
                    model.data.obj.forEach((item, index) => {
                        let generated_html = html_template(
                            (() => {
                                let obj = {'doc': doc};
                                try {
                                    obj.data = item;
                                } catch (err) {
                                }
                                return obj;
                            })()
                        );
                        let ele = $(this.node).find(`.sub-ele-${index}`);
                        if (ele.length != 0) {
                            $(ele).html(generated_html);
                        } else {
                            $(this.node).append(`<div class="sub-ele-${index}">${generated_html}</div>`);
                        }
                    })
                    
                    
                })():
                (() => {
                    let generated_html = html_template(
                        (() => {
                            let obj = {'doc': doc};
                            try {
                                obj.data = model.data;
                                obj.response = model.data.response;
                            } catch (err) {
                            }
                            return obj;
                        })()
                    );
                    $(this.node).html(generated_html);
                })();
        } catch (error) {
            console.error(`Error occurred while updating model. ${doc.name}`);
            console.error(error);
        }        		
    }
}

export default BindingNode;