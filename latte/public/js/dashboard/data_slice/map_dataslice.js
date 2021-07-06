import BindingModel from '../binding/binding_model.js';
import BindingNode from '../binding/binding_node.js';
import { GeoSearchControl, OpenStreetMapProvider } from 'leaflet-geosearch';
import 'leaflet-measure'
import 'leaflet-easyprint';
import 'leaflet-draw';
import 'leaflet-polylinedecorator';
import 'leaflet.heat'

latte.Dashboard.DataSlice.Map = class
DashboardCountDataSlice extends latte.Dashboard.DataSlice {
    update_config() {
        this.config = $.extend({}, this.config, {
            'data_source': 'multiple',
            'dom_binding': 'async'
        })
    }

    prepare_seq_data(_obj,color_column_index,ds_name){
        var test = []
        var point_array = []
        _obj.binding_model.data[ds_name].response.result.forEach((row)=>{
            if(test.includes(row[color_column_index])){
                point_array[test.indexOf(row[color_column_index])].push(row)
            }
            else{
                test.push(row[color_column_index]) 
                point_array.push([row])
            }
        })
        return point_array
    }

    col_to_categorical(_obj,color_column_index,ds_name){
        var unique_value = []
        var point_array = [] 
        var point = -1
        _obj.binding_model.data[ds_name].response.result.forEach((row)=>{
            if(unique_value.includes(row[color_column_index])){
                point_array.push(unique_value.indexOf(row[color_column_index]))
            }
            else{
                point = point + 1 
                unique_value.push(row[color_column_index]) 
                point_array.push(point)
            }
        })
        return point_array
    }

    plot_on_map(_obj,layers_count){
        var markerMapping = {}
        var count = 0
        var map_layer = _obj.mapObj

        $(".leaflet-control-layers-selector").each(function() {
            if($(this).is(":checked")){
                $(".leaflet-control-layers-selector").trigger('click')
            }
        });
        $('.leaflet-control-layers').remove();
        var first_data_source = $(`select[id='data-source-1-${_obj.doc.name}']`).val()
        var lat =  _obj.binding_model.data[first_data_source].response.result[0][_obj.binding_model.data[first_data_source].response.columns.indexOf($(`select[id='latitude-1-${_obj.doc.name}']`).val())]
        var long =  _obj.binding_model.data[first_data_source].response.result[0][_obj.binding_model.data[first_data_source].response.columns.indexOf($(`select[id='longitude-1-${_obj.doc.name}']`).val())]
        map_layer.panTo(new L.LatLng(lat, long));
        var layer_dict ={}
        map_layer.on('draw:created', function(e) {
            $(`table[id='points-inside-polygon-table-${_obj.doc.name}']`).html(``)
            var type = e.layerType,
            layer = e.layer;
            if (type === 'polygon') {
                for (var k = 1; k < layers_count+1; k++){
                    var current_data_source = $(`select[id='data-source-${k}-${_obj.doc.name}']`).val()
                    if ($(`select[id='map-type-${k}-${_obj.doc.name}']`).val() != 'Heat Map'){
                        var poly_boundry=[];
                        var points_in_poly=[];
                        layer._latlngs.forEach((n)=>{n.forEach((m)=>{poly_boundry.push(Object.values(m))})})
                        Object.values(markerMapping[k]).forEach((m)=>{
                            if(_obj.point_inside_polygon(Object.values(m._latlng), poly_boundry)){
                                points_in_poly.push(m._popup._content)	
                            }
                        })
                        var thead = "<thead>"
                    var current_data_source = $(`select[id='data-source-${k}-${_obj.doc.name}']`).val()
                        for (var i = 0; i < _obj.binding_model.data[current_data_source].response.columns.length; i++) {
                            thead += "<th>"+_obj.binding_model.data[current_data_source].response.columns[i]+"</th>"
                        }
                        thead = thead+"</thead>"
                        var tbody = "<tbody>"
                        for (var i = 0; i < points_in_poly.length; i++) {
                            tbody += "<tr>"
                            for (var j = 0; j < _obj.binding_model.data[current_data_source].response.columns.length; j++){
                                tbody += "<td>"+ points_in_poly[i].split("<br/>")[j].split(":")[1].trim() + "</td>"
                            }
                            tbody += "</tr>"
                        }
                        tbody = tbody+"</tbody>"
                        $(`table[id='points-inside-polygon-table-${_obj.doc.name}']`).append(thead)
                        $(`table[id='points-inside-polygon-table-${_obj.doc.name}']`).append(tbody)
                    }
                }
            }
            _obj.drawLayer.addLayer(layer);
        })
        for (var k = 1; k < layers_count+1; k++){
            var current_data_source = $(`select[id='data-source-${k}-${_obj.doc.name}']`).val()
            var color_column_index = _obj.binding_model.data[current_data_source].response.columns.indexOf($(`select[id='color-column-${k}-${_obj.doc.name}']`).val())
            var latitude_column_index = _obj.binding_model.data[current_data_source].response.columns.indexOf($(`select[id='latitude-${k}-${_obj.doc.name}']`).val())
            var longitude_column_index = _obj.binding_model.data[current_data_source].response.columns.indexOf($(`select[id='longitude-${k}-${_obj.doc.name}']`).val())
            if($(`select[id='map-type-${k}-${_obj.doc.name}']`).val()=="Sequential Map"){
                markerMapping[k] = {}
                var routing_data = _obj.prepare_seq_data(_obj, color_column_index,current_data_source)
                var marker_layer = L.layerGroup()
                var color_array = ["red","green","blue","yellow","black", "cyan", "white"]
                for (var i = 0; i < routing_data.length; i++) {
                    var coordinate_array = []
                    for (var j = 0; j < routing_data[i].length; j++) {
                        var pop_up = ""
                        _obj.binding_model.data[current_data_source].response.columns.forEach((opt,s)=>{
                            pop_up = pop_up +
                            '<b>'+ opt +'</b> : '+ routing_data[i][j][s] + '<br/>'
                        })
                        coordinate_array.push([routing_data[i][j][latitude_column_index],routing_data[i][j][longitude_column_index]])
                        var marker = L.marker(L.latLng(routing_data[i][j][latitude_column_index], routing_data[i][j][longitude_column_index]),
                        {
                            icon: L.divIcon({
                                className: "location-sprite l" + (j+1),
                                iconSize: [24, 41],
                                shadowsize: [41, 41],
                                iconAnchor: [12, 41]
                            })
                        }).bindPopup(pop_up)
                        count = count + 1
                        markerMapping[k][count] = marker
                        marker_layer.addLayer(marker);
                    }
                    var arrow = L.polyline(coordinate_array, {color: color_array[i%7]}).addTo(marker_layer);
                    L.polylineDecorator(arrow, {
                        patterns: [{
                            offset: 0,
                            repeat: 20,
                            symbol: L.Symbol.arrowHead({
                                pixelSize: 10,
                                pathOptions: {color: color_array[i%7],fillOpacity: 1, weight: 0}
                            })
                        }]
                    }).addTo(marker_layer);
                }
                layer_dict[current_data_source+k] = marker_layer
            }
            else if ($(`select[id='map-type-${k}-${_obj.doc.name}']`).val()=="Point Map"){
                var marker_layer = L.layerGroup()
                markerMapping[k] = {}
                var data_to_render = JSON.parse(JSON.stringify(_obj.binding_model.data[current_data_source].response.result))
                var cat_color_column = _obj.col_to_categorical(_obj,color_column_index, current_data_source)
                for (var i = 0; i < cat_color_column.length; i++) {
                    data_to_render[i].push(cat_color_column[i])
                }
                data_to_render.forEach((row)=>{
                    var pop_up = ""
                    _obj.binding_model.data[current_data_source].response.columns.forEach((opt,i)=>{
                        pop_up = pop_up +
                        '<b>'+ opt +'</b> : '+ row[i] + '<br/>'
                    })
                    var marker = L.marker(L.latLng(row[latitude_column_index], row[longitude_column_index]),
                    {
                        icon: L.divIcon({
                            html: '<i class="fa fa-'+$(`select[id='icon-type-${k}-${_obj.doc.name}']`).val()+' color' + (row[data_to_render[0].length-1] % 10) + '" style="font-size: 25px"></i>',
                            iconSize: [40, 40],
                            className: 'myDivIcon'
                        })
                    }).bindPopup(pop_up)
                    count=count+1
                    markerMapping[k][count] = marker
                    marker_layer.addLayer(marker);
                })
                layer_dict[current_data_source+k] = marker_layer
            } 
            else if ($(`select[id='map-type-${k}-${_obj.doc.name}']`).val()=="Heat Map") {
                var locations = []
                var counts_arr = []
                _obj.datamanager._data[current_data_source].response.result.forEach((r)=>{
                    locations.push([r[latitude_column_index], r[longitude_column_index], r[color_column_index]])
                    counts_arr.push(r[color_column_index])
                })
                counts_arr = counts_arr.sort(function(a, b){return a - b});
                var heat = L.heatLayer(locations, {
                    radius: 35,
                    max: counts_arr[Math.floor(counts_arr.length*0.95)],
                    gradient: {0.4: 'blue', 0.65: 'lime', 0.9: 'red'}
                });
                layer_dict[$("select[id='data-source-"+k+"-"+_obj.doc.name+"']").val()+k]=heat
            }
        }
        var layerscontrol = L.control.layers(null, layer_dict).addTo(map_layer);
        $(".leaflet-control-layers-selector").trigger('click')
    }

    point_inside_polygon(point, vs) {
        var x = point[0], y = point[1];
        var point_inside_polygon = false;
        for (var i = 0, j = vs.length - 1; i < vs.length; j = i++) {
            var xi = vs[i][0], yi = vs[i][1];
            var xj = vs[j][0], yj = vs[j][1];
    
            var intersect = ((yi > y) != (yj > y))
                && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
            if (intersect) point_inside_polygon = !point_inside_polygon;
        }
        return point_inside_polygon;
    };

    load_slice_defaults(){
        let obj = this
        if(obj.doc.chart_default_config != ""){
            var default_config = JSON.parse(obj.doc.chart_default_config)
            default_config.forEach((layer, i)=>{
                var config_html = `<form class="form-horizontal" action="">`
                Object.keys(layer).forEach((fg, j)=>{
                    var opt_str = ""
                    layer[fg]['options'].forEach((opt)=>{
                        if(layer[fg]['selected_option'] == opt){
                            opt_str = opt_str + `<option value='${opt}' selected>${opt}</option>` 
                        } else {
                            opt_str = opt_str + `<option value='${opt}'>${opt}</option>` 
                        }
                    });         
                    config_html = config_html + `<div class="form-group">
                            <label class="control-label col-sm-4" for="">${fg}</label>
                            <div class="col-sm-8">
                                <select id='${layer[fg]['select_id']}' class="form-control minimal${j==0? ' datasource-options': ''}" id="data-source-${i}-${obj.doc.name}" source>
                                ${opt_str}
                                </select>
                            </div>
                        </div>`
                })
                config_html = config_html + '</form><hr style="border: 1px dashed black;">'
                $("div[id='config-tab-" + obj.doc.name + "']").append(config_html)
                obj.layer_cnt = i+1
            })
            obj.plot_on_map(obj,default_config.length)
        }
    }

    save_slice_defaults(){
        let _obj = this
        var current_configuration = []
        $(`div[id='config-tab-${_obj.doc.name}']`).children('form').each((f)=>{
            var layer = {}
            $(`div[id='config-tab-${_obj.doc.name}']`).children('form').eq(f).children('div').each((s)=> {
                var select_options = []
                var selected_option = null
                var select_id = $(`div[id='config-tab-${_obj.doc.name}']`).children('form').eq(f).children('div').eq(s).find('select').attr('id')
                $(`div[id='config-tab-${_obj.doc.name}']`).children('form').eq(f).children('div').eq(s).find('select option').each((o)=>{
                    select_options.push($(`div[id='config-tab-${_obj.doc.name}']`).children('form').eq(f).children('div').eq(s).find('select option').eq(o).val())
                    $(`div[id='config-tab-${_obj.doc.name}']`).children('form').eq(f).children('div').eq(s).find('select option').eq(o).prop('selected') ? selected_option = $(`div[id='config-tab-${_obj.doc.name}']`).children('form').eq(f).children('div').eq(s).find('select option').eq(o).val() : ""
                })
                var label = $(`div[id='config-tab-${_obj.doc.name}']`).children('form').eq(f).children('div').eq(s).find('label').text()
                layer[label] = {
                    options: select_options,
                    selected_option: selected_option,
                    select_id: select_id
                }
            })
            current_configuration.push(layer)
        })
        frappe.call({
            method: "latte.dashboard.doctype.dashboard_data_slice.save_chart_config",
            args: {
                data_slice: _obj.doc.name,
                config: JSON.stringify(current_configuration)
            },
            callback: function(response){
                frappe.msgprint("Default Saved Successfully")
            }
        })
    }

    render() {
        $(this.chart_container.find(".data-wrapper")).data('template',  
            `<div id="${this.doc.name}" class="dashboard-chart">
            <style>	
                canvas {
                    -moz-user-select: none;
                    -webkit-user-select: none;
                    -ms-user-select: none;
                }
            </style>
            <div class="modal fade" id="modal-filter-button-${this.doc.name}" role="dialog">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h4 class="modal-title">
                            Filters
                            </h4>
                        </div>
                        <div id="action-bar-${this.doc.name}" class="row box-inner">
                            <button type="button" style="float:right; margin-right:20px" class="erDefaultBtn" id="add-layer-${this.doc.name}" add-layer-${this.doc.name}` + `="dummy">Add Layer ` + `</button>
                        </div>
                        <div class="modal-body">
                            <div id="config-tab-${this.doc.name}" style="max-height:400px;overflow-y:scroll;">
                            
                            </div>
                            <div id="action-bar-${this.doc.name}" class="row box-inner">
                                <button type="button" style="float:right;" class="erDefaultBtn map-view" id="render-map-${this.doc.name}" render-map` + `="dummy">Submit ` + `</button>
                                <button type="button" style="float:right; margin-right:20px" class="erDefaultBtn map-save" id="save-default-${this.doc.name}">Save Default ` + `</button>
                            </div>
                        </div>
                        <div class="modal-footer">
                            
                        </div>
                    </div>
                </div>
            </div>
            <div class="modal fade" id="modal-view-selected-points-button-${this.doc.name}" role="dialog">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h4 class="modal-title">
                            Selected Points
                            </h4>
                        </div>
                        <div class="modal-body">
                            <div class="col-md-12 visTable">
                                <table class="table" id="points-inside-polygon-table-${this.doc.name}">
                                </table>
                            </div>
                        </div>
                        <div class="modal-footer">
                            
                        </div>
                    </div>
                </div>
            </div>        
            <div class = "row">
                <div id="map-holder">
                    <div id="map" style="width: 100%; height: 590px;z-index:1;"></div>
                </div>
            </div>
        </div>`);

            
        let obj = this;
        this.binding_node = new BindingNode(this.chart_container.find(".data-wrapper"));
        this.binding_model = new BindingModel();
        this.binding_model.add_callback(function () {
            obj.binding_node.update(obj.binding_model, obj.doc);
            var layers = []
            var layers_options_str = '<option value=""></option>'
            obj.doc.dashboard_datasource.forEach((l)=>{
                layers.push(l.data_source_name)
                layers_options_str = layers_options_str + `<option value='${l.data_source_name}'>${l.data_source_name}</option>`
            })
            var updated_datasources = Object.keys(obj.binding_model.data)
            if (layers.every(function(val) { return updated_datasources.indexOf(val) >= 0; })){
                obj.chart_container.find(`button[id='add-layer-${obj.doc.name}']`).each((i, o) => {
                    $(o).click((e) => {
                        obj.layer_cnt = obj.layer_cnt || 0
                        obj.layer_cnt += 1
                        $("div[id='config-tab-" + obj.doc.name + "']").append(`<form class="form-horizontal" action="">
                        <div class="form-group">
                                <label class="control-label col-sm-4" for="">Data Source: </label>
                                <div class="col-sm-8">
                                    <select class="form-control minimal datasource-options" id="data-source-${obj.layer_cnt}-${obj.doc.name}" source>
                                    </select>
                                </div>
                            </div>
                            <div class="form-group">
                                <label class="control-label col-sm-4" for="">Map Type: </label>
                                <div class="col-sm-8">
                                    <select class="form-control minimal" id="map-type-${obj.layer_cnt}-${obj.doc.name}" select-map-type="dummy">
                                        <option></option>
                                        <option value="Point Map">Point Map</option>
                                        <option value="Sequential Map">Sequential Map</option>
                                        <option value="Heat Map">Heat Map</option>
                                    </select>
                                </div>
                            </div>
                            <div class="form-group">
                                <label class="control-label col-sm-4" for="">Icon Type: </label>
                                <div class="col-sm-8">
                                    <select class="form-control minimal" id="icon-type-${obj.layer_cnt}-${obj.doc.name}" select-map-type="dummy">
                                        <option></option>
                                        <option value="map-marker-alt">Location</option>
                                        <option value="map-pin">Map-Pin</option>
                                        <option value="location-arrow">Arrows</option>
                                    </select>
                                </div>
                            </div>
                            <div class="form-group">
                                <label class="control-label col-sm-4" for="">Lattitude: </label>
                                <div class="col-sm-8">
                                    <select class="form-control minimal opt"id="latitude-${obj.layer_cnt}-${obj.doc.name}" select-column-${obj.layer_cnt}-${obj.doc.name}>
                                    </select>
                                </div>
                            </div>
                            <div class="form-group">
                                <label class="control-label col-sm-4" for="">Longitude: </label>
                                <div class="col-sm-8">
                                    <select class="form-control minimal opt"id="longitude-${obj.layer_cnt}-${obj.doc.name}" select-column-${obj.layer_cnt}-${obj.doc.name}>
                                    </select>
                                </div>
                            </div>
                            <div class="form-group">
                                <label class="control-label col-sm-4" for="">Color / Count: </label>
                                <div class="col-sm-8">
                                    <select class="form-control minimal opt"id="color-column-${obj.layer_cnt}-${obj.doc.name}" select-column-${obj.layer_cnt}-${obj.doc.name}>
                                    </select>
                                </div>
                            </div>
                        </form>
                        <hr style="border: 1px dashed black;" />`)
                    obj.chart_container.find(`select[id='data-source-${obj.layer_cnt}-${obj.doc.name}']`).html(layers_options_str)
                    
                    })
                })

                $(obj.chart_container).on('change',`.datasource-options`, function (){
                    var num = $(this).attr("id").split("-")[2]
                    var ids = $(this).attr("id")
                    if($("select[id='"+ids+"']").val() != ""){
                        var options_str = ""
                        obj.binding_model.data[$("select[id='"+ids+"']").val()].response.columns.forEach((opt=>{
                            options_str = options_str +
                            "<option>" + opt + "</option>"
                        }))
                        $(`select[id='latitude-${num}-${obj.doc.name}']`).html(options_str)
                        $(`select[id='longitude-${num}-${obj.doc.name}']`).html(options_str)
                        $(`select[id='color-column-${num}-${obj.doc.name}']`).html(options_str)
                    }
                })
                var blank_map_layer = L.map('map', { center: [18.311124,74.792989], zoom: 8 });
                var measureControl = new L.Control.Measure({
                    position: 'topright',
                    primaryLengthUnit: 'kilometers',
                    primaryAreaUnit: 'sqmeters',
                    activeColor: '#000000',
                    completedColor: '#ADD8E6' 
                });
                measureControl.addTo(blank_map_layer);
                const provider = new OpenStreetMapProvider();

                const searchControl = new GeoSearchControl({
                    provider: provider,
                    style: 'button',
                    showMarker: true, // optional: true|false  - default true
                    showPopup: true, // optional: true|false  - default false
                    marker: {
                        icon: new L.Icon.Default(),
                        draggable: false,
                    },
                    popupFormat: ({ query, result }) => result.label, // optional: function    - default returns result label
                    maxMarkers: 10, // optional: number      - default 1
                    retainZoomLevel: false, // optional: true|false  - default false
                    animateZoom: true, // optional: true|false  - default true
                    autoClose: true, // optional: true|false  - default false
                    searchLabel: 'Enter address / lat-lng', // optional: string      - default 'Enter address'
                    keepResult: true, // optional: true|false  - default false
                });

                blank_map_layer.addControl(searchControl);
                
                var printPlugin = L.easyPrint({
                    title: 'Download Map',
                    position: 'topleft',
                    sizeModes: ['Current','A4Portrait', 'A4Landscape'],
                    exportOnly: true
                }).addTo(blank_map_layer);
                var editableLayers = new L.FeatureGroup();
                blank_map_layer.addLayer(editableLayers);
                var drawPluginOptions = {
                    position: 'topright',
                    draw: {
                        polygon: {
                            allowIntersection: false, // Restricts shapes to simple polygons
                            drawError: {
                                color: '#e1e100', // Color the shape will turn when intersects
                                message: '<strong>Oh snap!<strong> you can\'t draw that!' // Message that will show when intersect
                            },
                            shapeOptions: {
                                color: '#97009c'
                            }
                        },
                        // disable toolbar item by setting it to false
                        polyline: true,
                        circlemarker:false,
                        circle: true, // Turns off this drawing tool
                        rectangle: true,
                        marker: true,
                    },
                    edit: {
                        featureGroup: editableLayers, //REQUIRED!!
                        remove: true,
                        enable: true
                    }
                };
                // Initialise the draw control and pass it the FeatureGroup of editable layers
                var drawControl = new L.Control.Draw(drawPluginOptions);
                blank_map_layer.addControl(drawControl);
                
                L.Control.ConfigureSlice = L.Control.extend({
                    onAdd: function(map) {
                        var spn = L.DomUtil.create('span');
                        spn.id = `filter-button-${obj.doc.name}`
                        spn.classList.add('glyphicon')
                        spn.classList.add('glyphicon-plus-sign')
                        spn.classList.add('slide-toggle')
                        spn.style.width = '200px';
                
                        return spn;
                    },
                
                    onRemove: function(map) {
                        // Nothing to do here
                    }
                });
                
                L.control.configureslice = function(opts) {
                    return new L.Control.ConfigureSlice(opts);
                }
                
                L.control.configureslice({position: 'bottomleft'}).addTo(blank_map_layer);
                
                L.Control.SelectView = L.Control.extend({
                    onAdd: function(map) {
                        var spn = L.DomUtil.create('span');
                        spn.id = `view-selected-points-button-${obj.doc.name}`
                        spn.classList.add('glyphicon')
                        spn.classList.add('glyphicon-list-alt')
                        spn.classList.add('slide-toggle')
                        spn.style.width = '200px';
                
                        return spn;
                    },
                
                    onRemove: function(map) {
                        // Nothing to do here
                    }
                });
                
                L.control.selectview = function(opts) {
                    return new L.Control.SelectView(opts);
                }
                
                L.control.selectview({ position: 'bottomleft' }).addTo(blank_map_layer);

                L.tileLayer('https://{s}.tile.osm.org/{z}/{x}/{y}.png', { attribution: '� OpenStreetMap contributors' }).addTo(blank_map_layer);
                $("span[id='filter-button-" + obj.doc.name + "']").click(function(){
                    $("div[id='modal-" + this.id + "']").modal('toggle')
                });

                $("span[id='view-selected-points-button-" + obj.doc.name + "']").click(function(){
                    $("div[id='modal-" + this.id + "']").modal('toggle')
                });

                $(obj.chart_container).on('click',`.map-save`, function (){
                    obj.save_slice_defaults()
                })

                obj.mapObj = blank_map_layer
                obj.drawLayer = editableLayers
                $(obj.chart_container).on('click',`.map-view`, function (){
                    $("div[id='modal-filter-button-"+ obj.doc.name + "']").modal('toggle')
                    obj.plot_on_map(obj,obj.layer_cnt)
                })
                obj.load_slice_defaults()
            }           
        });

        this.run_post_js();
    }
} 