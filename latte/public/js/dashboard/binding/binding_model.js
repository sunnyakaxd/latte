class BindingModel {
    constructor(handlers) {
        const callbacks = []
        const model = {
            add_callback: function add_callback(fn) {
                callbacks.push(fn)
            }
        }
        const proxy = new Proxy(model, {
            set: function (target, property, value) {
                target[property] = value;
                callbacks.forEach((callback) => callback())
                return true;
            }
        })
        return proxy;
    }
}

export default BindingModel;