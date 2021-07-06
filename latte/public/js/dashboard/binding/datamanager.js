
class DataManager {
    constructor(dt, config={'type': 'single'}) {
        this.config = config;
        this._data = {};
        this._data.response = dt.resp.response;
        this.addDSObj(dt);
        let {result, columns} = this._data.response;
        this._data.obj = this.objectifyData(result, columns);
    }

    get data() {
        return this._data;
    }

    set data(dt) {   
        if (!this._data || this._data.length <= 0) {
            this._data = {}
            this._data.response = dt.resp.response;
            this.addDSObj(dt);
            let {result, columns} = this._data.response;
            this._data.obj = this.objectifyData(result, columns);
        } else {
            if (this.config.type != 'multiple')
                throw "Cannot Add Source Data to already existing Data with multiple type";
            else { 
                if (!this.config.joinField) 
                    throw "Multiple Source Data should have a join field set";
                else {
                    this.addDSObj(dt);
                    this.mergeData(dt);
                } 
            }      
        }
    }

    objectifyData(result, columns) {
        try {
            return result.map((resp, index) => {
                let obj = {}
                resp.forEach((res, index) => {
                    obj[columns[index].split(':')[0]] = res
                });
                return obj;
            });   
        } catch (error) {
            return result;
        }
    }

    addDSObj(dt) {
        if (dt.ds) {
            this._data[dt.ds] = {};
            this._data[dt.ds].response = dt.resp.response;
        }
    }

    mergeData(dt) {
        this._data.obj = (this._data.obj)
            .map(aitem => 
                Object.assign({}, aitem, 
                    this.objectifyData(dt.resp.response.result, dt.resp.response.columns).find(
                        bitem => aitem[this.config.joinField] === bitem[this.config.joinField]
                    )));
    }
}

export default DataManager; 