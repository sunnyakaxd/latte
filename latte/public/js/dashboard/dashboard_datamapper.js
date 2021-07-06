frappe.provide('latte')

latte.DataMapper = {
    map_dashboard_doc: function(data_slice_data) {
        // Function to Map Slice data to dashboard Document
        this.dashboard_doc.dashboard_data_slices.forEach((db) => {
            db.link_name = db.name;
            const sd = data_slice_data.find((sd) => sd.data_slice_id == db.link_name);
            //Object.assign(db, sd);
            Object.keys(sd).forEach((v) => {
                delete db[v];
            });
            $.extend(db, sd);
        });
    },
    reshape_dashboard_doc: function(doc) {
        this.dashboard_doc = (({title, layout_detail, dashboard_theme, disable_position, is_layout_fixed, data_slice_borders}) =>
            ({title, layout_detail, dashboard_theme, disable_position, is_layout_fixed, data_slice_borders}))
            (doc);
        //Reshape Perms
        this.dashboard_doc.role_permission = [];
        this.dashboard_doc.on_enter = doc.on_enter;
        this.dashboard_doc.project_template = doc.project_template;
        doc.role_permission.forEach((role) => {
            this.dashboard_doc.role_permission.push(role.role);
        });

        // TODO - Legacy Code
        // Reshape Layout 
        this.dashboard_doc.layouts = [];
        doc.dashboard_layout.forEach((layout) => {
            this.dashboard_doc.layouts.push({
                'layout_name': layout.layout_name,
                'parent_name': layout.parent_name,
                'type': layout.type,
                'height': layout.height,
                'width': layout.width,
                'is_filter': layout.is_filter
            });
        });
        // TODO - Legacy Code
        
        // Reshape Data Slices
        this.dashboard_doc.data_slices = this.dashboard_doc.data_slices || {};
        doc.dashboard_data_slices.forEach((ds) => {
            this.dashboard_doc.data_slices[`${ds.name}_${ds.dashboard_data_slice}`] =
                this.dashboard_doc.data_slices[`${ds.name}_${ds.dashboard_data_slice}`] || {};
            this.dashboard_doc.data_slices[`${ds.name}_${ds.dashboard_data_slice}`].link = {
                'id': ds.id,
                'name': ds.name,
                'slice_name': ds.dashboard_data_slice,
                'col_span': ds.col_span,
                'row_span': ds.row_span,
                'layout_name': ds.layout_name
            };
        });
        latte.dashboard.dashboard_doc = this.dashboard_doc;
    },
    template_cache: {},
    generate_template_string: function(template){
        var fn = this.template_cache[template];
        if (!fn){
            // Replace ${expressions} (etc) with ${map.expressions}.
            // var sanitized = template
            //     .replace(/\$\{([\s]*[^;\s\{]+[\s]*)\}/g, function(_, match){
            //         return `\$\{map.${match.trim()}\}`;
            //     })
            //     // Afterwards, replace anything that's not ${map.expressions}' (etc) with a blank string.
            //     .replace(/(\$\{(?!map\.)[^}]+\})/g, '');
            // fn = Function('obj', `return \`${sanitized}\``);
            fn = Function('obj',
                `
                obj = $.extend({'doc':{}, 'response': {'result': [[]]}}, obj);
                let getSafe = (fn, defaultVal) => {
                    try {
                        return fn();
                    } catch (e) {
                        return defaultVal || '-';
                    }
                }
                return \`${template}\``);
            this.template_cache[template] = fn;
        }
        return fn;
    }
}
