import Chart from 'chart.js';
// import 'chartjs-plugin-labels';
import ChartDataLabels from 'chartjs-plugin-datalabels';

latte.Dashboard.DataSlice.Chart = class DashboardChartDataSlice extends latte.Dashboard.DataSlice {		
    update_config() {
        this.config = $.extend({}, this.config, {
            'data_source': 'single',
            'dom_binding': 'sync'
        });
        this.multiValueFieldHandlers = {}
        this.render_methods = {
            Line: this.render_line_chart,
            Bar: this.render_bar_chart,
            Pie: this.render_pie_chart
        }
        this.chart_config = {
            Line: {
                data_fields: [
                    {
                        "name": "labels",
                        "type": "Single",
                        "source": "Column"
                    },
                    {
                        "name": "datasets",
                        "type": "Multiple",
                        "fields": [
                            {
                                "name": "label",
                                "type": "Single",
                                "source": "Text"
                            },
                            {
                                "name": "borderColor",
                                "type": "Single",
                                "source": "ColorSelector"
                            },
                            {
                                "name": "backgroundColor",
                                "type": "Single",
                                "source": "ColorSelector"
                            },
                            {
                                "name": "fill",
                                "type": "Single",
                                "source": "Checkbox"
                            },
                            {
                                "name": "data",
                                "type": "Single",
                                "source": "Column"
                            },
                            {
                                "name": "yAxisID",
                                "type": "Single",
                                "source": "Text"
                            },
                            {
                                "name": "position",
                                "type": "Single",
                                "source": "Select",
                                "options": "left\nright"
                            },
                            {
                                "name": "drawOnChartArea",
                                "type": "Single",
                                "source": "Checkbox"
                            }
                        ]
                    }
                ],
                option_fields: [
                    {
                        "name": "responsive",
                        "type": "Single",
                        "source": "Checkbox"
                    },
                    {
                        "name": "stacked",
                        "type": "Single",
                        "source": "Checkbox"
                    },
                    {
                        "name": "title",
                        "type": "Single",
                        "source": "Text"
                    },
                    {
                        "name": "scaleStartValue",
                        "type": "Single",
                        "source": "Text"
                    },
                    {
                        "name": "scaleEndValue",
                        "type": "Single",
                        "source": "Text"
                    },                    
                    {
                        "name": "xAxisLabel",
                        "type": "Single",
                        "source": "Text"
                    },
                    {
                        "name": "yAxisLabel",
                        "type": "Single",
                        "source": "Text"
                    },
                    {
                        "name": "labelposition",
                        "type": "Single",
                        "source": "Select",
                        "options": "\ncentre\nend"
                    },
                    {
                        "name": "labelColor",
                        "type": "Single",
                        "source": "ColorSelector"
                    }
                ]
            },
            "Bar": {
                data_fields: [
                    {
                        "name": "labels",
                        "type": "Single",
                        "source": "Column"
                    },
                    {
                        "name": "datasets",
                        "type": "Multiple",
                        "fields": [
                            {
                                "name": "label",
                                "type": "Single",
                                "source": "Text"
                            },
                            {
                                "name": "backgroundColor",
                                "type": "Single",
                                "source": "ColorSelector"
                            },
                            {
                                "name": "borderColor",
                                "type": "Single",
                                "source": "ColorSelector"
                            },
                            {
                                "name": "borderWidth",
                                "type": "Single",
                                "source": "Text"
                            },
                            {
                                "name": "data",
                                "type": "Single",
                                "source": "Column"
                            }
                        ]
                    }
                ],
                option_fields: [
                    {
                        "name": "responsive",
                        "type": "Single",
                        "source": "Checkbox"
                    },
                    {
                        "name": "title",
                        "type": "Single",
                        "source": "Text"
                    },
                    {
                        "name": "position",
                        "type": "Single",
                        "source": "Select",
                        "options": "top\nbottom"
                    },
                    {
                        "name": "scaleStartValue",
                        "type": "Single",
                        "source": "Text"
                    },
                    {
                        "name": "scaleEndValue",
                        "type": "Single",
                        "source": "Text"
                    },
                    {
                        "name": "stacked",
                        "type": "Single",
                        "source": "Checkbox"
                    },
                    {
                        "name": "xAxisLabel",
                        "type": "Single",
                        "source": "Text"
                    },
                    {
                        "name": "yAxisLabel",
                        "type": "Single",
                        "source": "Text"
                    },
                    {
                        "name": "labelposition",
                        "type": "Single",
                        "source": "Select",
                        "options": "\ncentre\nend"
                    },
                    {
                        "name": "labelColor",
                        "type": "Single",
                        "source": "ColorSelector"
                    }
                ]
            },
            Pie: {
                data_fields: [
                    {
                        "name": "datasets",
                        "type": "Multiple",
                        "fields": [
                            {
                                "name": "label",
                                "type": "Single",
                                "source": "Text"
                            },
                            {
                                "name": "backgroundColor",
                                "type": "Single",
                                "source": "ColorSelector"
                            },
                            {
                                "name": "borderAlign",
                                "type": "Single",
                                "source": "Select",
                                "options": "center\ninner"
                            },
                            {
                                "name": "borderColor",
                                "type": "Single",
                                "source": "ColorSelector"
                            },
                            {
                                "name": "borderWidth",
                                "type": "Single",
                                "source": "Text"
                            },
                            {
                                "name": "data",
                                "type": "Single",
                                "source": "Column"
                            },
                            {
                                "name": "weight",
                                "type": "Single",
                                "source": "Text"
                            }
                        ] 
                    }
                ],
                option_fields: [
                    {
                        "name": "cutoutPercentage",
                        "type": "Single",
                        "source": "Text"
                    },
                    {
                        "name": "labelposition",
                        "type": "Single",
                        "source": "Select",
                        "options": "\ncentre\nend"
                    },
                    {
                        "name": "labelColor",
                        "type": "Single",
                        "source": "ColorSelector"
                    },
                    {
                        "name": "labeltype",
                        "type": "Single",
                        "source": "Select",
                        "options": "value\npercent"
                    }

                ]
            }
        }
    }
    
    generate_input_form(df, i=0){
        var html_string;
        switch(df.source){
            case "Text":
                html_string = `<div class="form-group" slicename="` + this.doc.name + `">
                    <label class="control-label col-sm-4" for="">` + df.name + `: </label>
                    <div class="col-sm-8">
                        <input class="form-control" id="data_field_` + this.doc.name + `_` + df.name + `_` + i + `">
                    </div>
                </div>`
                break;
            case "Checkbox":
                html_string= `<div class="form-group" slicename="` + this.doc.name + `">
                    <label class="control-label col-sm-4" for="">` + df.name + `: </label>
                    <div class="col-sm-8">
                    <label class="chkbox">
                        <input type="checkbox" id="data_field_` + this.doc.name + `_` + df.name + `_` + i + `">
                        <span class="checkmark"></span>
                    </label>
                    </div>
                  </div>`
                break;
            case "ColorSelector":
                html_string = `<div class="form-group" slicename="` + this.doc.name + `">
                    <label class="control-label col-sm-4" for="">` + df.name + `: </label>
                    <div class="col-sm-8">
                        <input type="color" class="form-control" id="data_field_` + this.doc.name + `_` + df.name + `_` + i + `">
                    </div>
                </div>`
                break;
            case "Column":
                var col_options_str = ""
                this.datamanager._data.response.columns.forEach((col=>{
                    col_options_str = col_options_str +
                        "<option>" + col + "</option>"
                }))
                html_string = `<div class="form-group" slicename="` + this.doc.name + `">
                    <label class="control-label col-sm-4" for="">` + df.name + `: </label>
                    <div class="col-sm-8">
                        <select class="form-control minimal" id="data_field_` + this.doc.name + `_` + df.name + `_` + i + `" >`
                        + col_options_str + 
                        `</select>
                    </div>
                </div>`
                break;
            case "Select":
                var options_str = ""
                df.options.split("\n").forEach((opt=>{
                    options_str = options_str +
                        "<option>" + opt + "</option>"
                }))
                html_string = `<div class="form-group" slicename="` + this.doc.name + `">
                    <label class="control-label col-sm-4" for="">` + df.name + `: </label>
                    <div class="col-sm-8">
                        <select class="form-control minimal" id="data_field_` + this.doc.name + `_` + df.name + `_` + i + `" >`
                        + options_str + 
                        `</select>
                    </div>
                </div>`
                break;
        }
        return(html_string)
    }

    render_chart_metadata(){
        $("[slicename='" + this.doc.name + "']").each((i, ele)=>{
            $(ele).off()
            $(ele).remove()
        })
        this["create_" + this.doc.name + "_datasets_counter"] = -1
        var chart_dropdown = document.getElementById("chart-type-" + this.doc.name);
        var selected_chart = chart_dropdown.options[chart_dropdown.selectedIndex].value;
        this.chart_config[selected_chart]["data_fields"].forEach((df)=>{
            if(df.type == "Single"){
                $(this.generate_input_form(df)).insertBefore("div[id='action-bar-" + this.doc.name + "']")
            }
            else if (df.type == "Multiple"){
                $(`<div id="container_` + this.doc.name + `_` + df.name + `" class="form-group" slicename="` + this.doc.name + `">
                    <label class="control-label col-sm-4" for=""></label>
                    <div class="col-sm-8">
                        <button type="button" class="erSecondaryBtn floatRight" id="field_creator_` + this.doc.name + 
                            `_` + df.name + `" create-sub-fields="dummy">Add ` + df.name + `</button>
                    </div>
                  </div>`).insertBefore("div[id='action-bar-" + this.doc.name + "']")
                
                let _obj = this
                this.multiValueFieldHandlers['create_' + this.doc.name + '_' + df.name] = function(){
                    var cnt  = 'create_' + _obj.doc.name + '_' + df.name + "_counter"
                    if (_obj[cnt] === undefined){_obj[cnt] = 0} else {_obj[cnt] = _obj[cnt] +1}
                        
                    df.fields.forEach((sf)=>{
                        $(_obj.generate_input_form(sf, _obj[cnt])).insertAfter("div[id='" + "container_" + _obj.doc.name + "_" + df.name + "']");
                    })
                }
                this.chart_container.find("button[create-sub-fields]").each((i, o) => {
                    let _that = this;
                    $(o).click(e => _that.multiValueFieldHandlers[e.target.id.replace('field_creator', 'create')]());
                });
            }
        })
        this.chart_config[selected_chart]["option_fields"].forEach((df)=>{
            $(this.generate_input_form(df)).insertBefore("div[id='action-bar-" + this.doc.name + "']")
        })
    }

    render_pie_chart(dashObj){
        let _obj = dashObj
        var col_id = _obj.datamanager._data.response.columns.indexOf($( "select[id='data_field_" + _obj.doc.name + "_labels_0'] option:selected" ).text())
        var x_axis_labels = []
        _obj.datamanager._data.response.result.forEach((row)=>{
            x_axis_labels.push(row[col_id])
        })
        var total_datasets = $("input[id*='data_field_" + _obj.doc.name + "_label']").length-1
        var data = []
        var bgColor = []
        var borderColor = []
        var borderWidth = []
        var labels = []
        for (var k=0; k < total_datasets; k++){
            var data_col_id = _obj.datamanager._data.response.columns.indexOf($("select[id='data_field_" + _obj.doc.name + "_data_" + k + "'] option:selected").text())
            data.push(_obj.datamanager._data.response.result[0][data_col_id])
            borderColor.push($("input[id='data_field_" + _obj.doc.name + "_borderColor_" + k + "']").val())
            bgColor.push($("input[id='data_field_" + _obj.doc.name + "_backgroundColor_" + k + "']").val())
            borderWidth.push($("input[id='data_field_" + _obj.doc.name + "_borderWidth_" + k + "']").val())
            labels.push($("input[id='data_field_" + _obj.doc.name + "_label_" + k + "']").val())
        }
        var canvas = document.getElementById('canvas-' + _obj.doc.name) 
        var ctx = canvas.getContext('2d');
        
        canvas.width = _obj.chart_container[0].offsetWidth*0.85;
        if($("select[id='data_field_" + _obj.doc.name + "_labelposition_0'] option:selected").val() == ""){
            var chart_labels = []
        }
        else{
            var chart_labels = [ChartDataLabels]
        }
        Chart.Doughnut(ctx, {
            plugins: chart_labels,
            data: {
                datasets:[{
                    label: "Pie Chart",
                    data: data,
                    borderColor: borderColor,
                    borderWidth: borderWidth,
                    backgroundColor: bgColor
                }],
                labels:labels
            },
            options: {
                cutoutPercentage: $("input[id='data_field_" + _obj.doc.name + "_cutoutPercentage_0']").val(),
                //rotation: $("input[id='data_field_" + _obj.doc.name + "_rotation_0']").val(),
                //circumference: $("input[id='data_field_" + _obj.doc.name + "_circumference_0']").val()
                plugins: {
                    datalabels: {
                        color: $("input[id='data_field_" + _obj.doc.name + "_labelColor_0']").val(),
                        formatter: (value, ctx) => {
                            let sum = 0;
                            let dataArr = ctx.chart.data.datasets[0].data;
                            dataArr.map(data => {
                                sum += data;
                            });
                            let percentage = (value*100 / sum).toFixed(2)+"%";
                            if($("select[id='data_field_" + _obj.doc.name + "_labeltype_0'] option:selected").val() == "percent"){
                                return percentage;
                            }
                            else{
                                return value
                            }
                        },
                        anchor: $("select[id='data_field_" + _obj.doc.name + "_labelposition_0'] option:selected").val(),
                        align: $("select[id='data_field_" + _obj.doc.name + "_labelposition_0'] option:selected").val()
                      }
                }
            }
        });	
        
    }

    render_line_chart(dashObj){
        let _obj = dashObj
        var col_id = _obj.datamanager._data.response.columns.indexOf($( "select[id='data_field_" + _obj.doc.name + "_labels_0'] option:selected" ).text())
        var x_axis_labels = []
        _obj.datamanager._data.response.result.forEach((row)=>{
            x_axis_labels.push(row[col_id])
        })
        var total_datasets = $("input[id*='data_field_" + _obj.doc.name + "_yAxisID']").length
        var datasets = []
        var y_axes_scales = []
        var y_ticks = {}
        
        if ($("input[id='data_field_" + _obj.doc.name + "_scaleStartValue_0']").val() != "" && $("input[id='data_field_" + _obj.doc.name + "_scaleEndValue_0']").val() != ""){
            y_ticks = {
                min: parseInt($("input[id='data_field_" + _obj.doc.name + "_scaleStartValue_0']").val()),
                max: parseInt($("input[id='data_field_" + _obj.doc.name + "_scaleEndValue_0']").val())
                }
        }
        else if ($("input[id='data_field_" + _obj.doc.name + "_scaleStartValue_0']").val() != ""){
            y_ticks = {
                min: parseInt($("input[id='data_field_" + _obj.doc.name + "_scaleStartValue_0']").val())
                }
        }
        else if ($("input[id='data_field_" + _obj.doc.name + "_scaleEndValue_0']").val() != ""){
            y_ticks = {
                max: parseInt($("input[id='data_field_" + _obj.doc.name + "_scaleEndValue_0']").val())
                }
        }
        
        for (var k=0; k < total_datasets; k++){
            var y_axis_col_id = _obj.datamanager._data.response.columns.indexOf($( "select[id='data_field_" + _obj.doc.name + "_data_" + k + "'] option:selected").text())
            var y_axis_data = []
            _obj.datamanager._data.response.result.forEach((row)=>{
                y_axis_data.push(row[y_axis_col_id])
            })
            
            datasets.push({
                "label": $("input[id='data_field_" + _obj.doc.name + "_label_" + k + "']").val(),
                "borderColor": $("input[id='data_field_" + _obj.doc.name + "_borderColor_" + k + "']").val(),
                "backgroundColor": $("input[id='data_field_" + _obj.doc.name + "_backgroundColor_" + k + "']").val(),
                "fill": $("input[id='data_field_" + _obj.doc.name + "_fill_" + k + "']").is(":checked"),
                "data": y_axis_data,
                "yAxisID": $("input[id='data_field_" + _obj.doc.name + "_yAxisID_" + k + "']").val(),
            })

            y_axes_scales.push({
                type: 'linear', // only linear but allow scale type registration. This allows extensions to exist solely for log scale for instance
                display: true,
                position: $("select[id='data_field_" + _obj.doc.name + "_position_" + k + "'] option:selected").val(),
                id: $("input[id='data_field_" + _obj.doc.name + "_yAxisID_" + k + "']").val(),
                gridLines: {
                    drawOnChartArea: $("input[id='data_field_" + _obj.doc.name + "_drawOnChartArea_" + k + "']").is(":checked")
                },
                ticks: y_ticks,
                scaleLabel: {
                    display: true,
                    labelString: $("input[id='data_field_" + _obj.doc.name + "_yAxisLabel_" + 0 + "']").val(),
                    font: {
                        size: 30,
                        weight: 'bold'
                    }
                }
            })
            
        }
        var lineChartData = {
            labels: x_axis_labels,
            datasets: datasets
        };

        var canvas = document.getElementById('canvas-' + _obj.doc.name) 
        var ctx = canvas.getContext('2d');
        
        canvas.width = _obj.chart_container[0].offsetWidth*0.85;
        if($("select[id='data_field_" + _obj.doc.name + "_labelposition_0'] option:selected").val() == ""){
            var chart_labels = []
        }
        else{
            var chart_labels = [ChartDataLabels]
        }
        Chart.Line(ctx, {
            plugins: chart_labels,
            data: lineChartData,
            options: {
                responsive: $("input[id='data_field_" + _obj.doc.name + "_responsive_" + k + "']").is(":checked"),
                //maintainAspectRatio: false,
                hoverMode: 'index',
                stacked: $("input[id='data_field_" + _obj.doc.name + "_stacked_" + k + "']").is(":checked"),
                title: {
                    display: true,
                    text: $("input[id='data_field_" + _obj.doc.name + "_title_0']").val()
                },
                scales: {
                    yAxes: y_axes_scales,
                    xAxes: [{
                        display: true,
                        scaleLabel: {
                            display: true,
                            labelString: $("input[id='data_field_" + _obj.doc.name + "_xAxisLabel_" + 0 + "']").val(),
                            font: {
                                size: 30,
                                weight: 'bold'
                            }
                        },
                    }]
                },
                plugins: {
                    datalabels: {
						color: $("input[id='data_field_" + _obj.doc.name + "_labelColor_0']").val(),
						font: {
							weight: 'bold'
						},
                        anchor: $("select[id='data_field_" + _obj.doc.name + "_labelposition_0'] option:selected").val(),
						align: $("select[id='data_field_" + _obj.doc.name + "_labelposition_0'] option:selected").val()
					}
                }
            }
        });	
     
    }
    
    render_bar_chart(dashObj){
        let _obj = dashObj
        var col_id = _obj.datamanager._data.response.columns.indexOf($( "select[id='data_field_" + _obj.doc.name + "_labels_0'] option:selected" ).text())
        var x_axis_labels = []
        _obj.datamanager._data.response.result.forEach((row)=>{
            x_axis_labels.push(row[col_id])
        })
        var total_datasets = $("select[id*='data_field_" + _obj.doc.name + "_data']").length
        var datasets = []
        
        for (var k=0; k < total_datasets; k++){
            var y_axis_col_id = _obj.datamanager._data.response.columns.indexOf($( "select[id='data_field_" + _obj.doc.name + "_data_" + k + "'] option:selected").text())
            var y_axis_data = []
            _obj.datamanager._data.response.result.forEach((row)=>{
                y_axis_data.push(row[y_axis_col_id])
            })
            
            datasets.push({
                "label": $("input[id='data_field_" + _obj.doc.name + "_label_" + k + "']").val(),
                "borderColor": $("input[id='data_field_" + _obj.doc.name + "_borderColor_" + k + "']").val(),
                "backgroundColor": $("input[id='data_field_" + _obj.doc.name + "_backgroundColor_" + k + "']").val(),
                "borderWidth": parseInt($("input[id='data_field_" + _obj.doc.name + "_borderWidth_" + k + "']").val()),
                "data": y_axis_data,
            })
            
        }
        var barChartData = {
            labels: x_axis_labels,
            datasets: datasets
        };

        var canvas = document.getElementById('canvas-' + _obj.doc.name) 
        var ctx = canvas.getContext('2d');
        
        canvas.width = _obj.chart_container[0].offsetWidth*0.85;
        var y_ticks = {}
        if ($("input[id='data_field_" + _obj.doc.name + "_scaleStartValue_0']").val() != "" && $("input[id='data_field_" + _obj.doc.name + "_scaleEndValue_0']").val() != ""){
            y_ticks = {
                min: parseInt($("input[id='data_field_" + _obj.doc.name + "_scaleStartValue_0']").val()),
                max: parseInt($("input[id='data_field_" + _obj.doc.name + "_scaleEndValue_0']").val())
                }
        }
        else if ($("input[id='data_field_" + _obj.doc.name + "_scaleStartValue_0']").val() != ""){
            y_ticks = {
                min: parseInt($("input[id='data_field_" + _obj.doc.name + "_scaleStartValue_0']").val())
                }
        }
        else if ($("input[id='data_field_" + _obj.doc.name + "_scaleEndValue_0']").val() != ""){
            y_ticks = {
                max: parseInt($("input[id='data_field_" + _obj.doc.name + "_scaleEndValue_0']").val())
                }
        }
        if($("select[id='data_field_" + _obj.doc.name + "_labelposition_0'] option:selected").val() == ""){
            var chart_labels = []
        }
        else{
            var chart_labels = [ChartDataLabels]
        }
        Chart.Bar(ctx, {
            plugins: chart_labels,
            data: barChartData,
            options: {
                responsive: $("input[id='data_field_" + _obj.doc.name + "_responsive_" + k + "']").is(":checked"),
                title: {
                    display: true,
                    text: $("input[id='data_field_" + _obj.doc.name + "_title_0']").val()
                },
                legend: {
                    position: $("select[id='data_field_" + _obj.doc.name + "_position_0'] option:selected").val(),
                },
                scales: {
                    yAxes: [{
                        display: true,
                        ticks: y_ticks,
                        stacked: $("input[id='data_field_" + _obj.doc.name + "_stacked_" + 0 + "']").is(":checked"),
                        scaleLabel: {
                            display: true,
                            font: {
                                size: 30,
                                weight: 'bold'
                            },
                            labelString: $("input[id='data_field_" + _obj.doc.name + "_yAxisLabel_" + 0 + "']").val(),

                        }
                    }],
                    xAxes: [{
                        display: true,
                        stacked: $("input[id='data_field_" + _obj.doc.name + "_stacked_" + 0 + "']").is(":checked"),
                        scaleLabel: {
                            display: true,
                            labelString: $("input[id='data_field_" + _obj.doc.name + "_xAxisLabel_" + 0 + "']").val(),
                            font: {
                                size: 30,
                                weight: 'bold'
                            }
                        }
                    }]
                },
                plugins: {
                    // Change options for ALL labels of THIS CHART
                    datalabels: {
						color: $("input[id='data_field_" + _obj.doc.name + "_labelColor_0']").val(),
						display: function(context) {
							return context.dataset.data[context.dataIndex] > 15;
						},
						font: {
							weight: 'bold'
						},
                        anchor: $("select[id='data_field_" + _obj.doc.name + "_labelposition_0'] option:selected").val(),
						align: $("select[id='data_field_" + _obj.doc.name + "_labelposition_0'] option:selected").val()
					}
                  }
            }
        });	
    }

    fieldtype_ui_operators(fieldtype, id, value=null){
        var ui_operators = {
            "Text": {
                "getter": `$("input[id='` + id + `']").val()`,
                "setter": `$("input[id='` + id + `']").val("` + value + `")`
            },
            "Checkbox": {
                "getter": `$("input[id='` + id + `']").is(":checked")`,
                "setter": `$("input[id='` + id + `']").prop('checked', ` + value + `);`
            },
            "ColorSelector": {
                "getter": `$("input[id='` + id + `']").val()`,
                "setter": `$("input[id='` + id + `']").val("` + value + `")`
            },
            "Column": {
                "getter": `$("select[id='` + id + `']").val()`,
                "setter": `$("select[id='` + id + `']").val("` + value + `")`
            },
            "Select": {
                "getter": `$("select[id='` + id + `']").val()`,
                "setter": `$("select[id='` + id + `']").val("` + value + `")`
            }
        }
        return ui_operators[fieldtype]
    }

    load_chart_defaults(){
        var default_config = JSON.parse(this.doc.chart_default_config)
        $("select[id='chart-type-" + this.doc.name + "']").val(default_config["Chart Type"])
        this.render_chart_metadata()
        for(var m =0; m < default_config["Datasets Counter"] + 1; m++){
            $("button[id='field_creator_" + this.doc.name + "_datasets']").click()
        }
        for(var single_key in default_config["Single"]){
            var id = "data_field_" + this.doc.name + "_" + single_key + "_0"
            eval(this.fieldtype_ui_operators(default_config["Single"][single_key]["type"], id, default_config["Single"][single_key]["value"])["setter"])
        }
        let _obj = this
        default_config["Multiple"].forEach((def_con, i)=>{
            for(var multi_key in def_con){
                var id = "data_field_" + _obj.doc.name + "_" + multi_key + "_" + i
                eval(_obj.fieldtype_ui_operators(def_con[multi_key]["type"], id, def_con[multi_key]["value"])["setter"])
            }
        })
    }

    save_chart_defaults(){
        let _obj = this
        var default_values = {
            "Single":{},
            "Multiple":[]
        }
        var current_chart_type = $("select[id='chart-type-" + this.doc.name + "']").val() || this.doc.chart_type
                
        this.chart_config[current_chart_type]["data_fields"].forEach((df) =>{
            if (df.type == "Single"){
                var id="data_field_" + _obj.doc.name + "_" + df.name + "_0"
                default_values["Single"][df.name] = {
                    "value": eval(_obj.fieldtype_ui_operators(df.source, id)["getter"]),
                    "type": df.source
                }
            }
            else if (df.type == "Multiple"){
                for (var k=0; k < _obj["create_" + _obj.doc.name +  "_datasets_counter"] + 1; k++){
                    var sub_data_fields = {}
                    df.fields.forEach((sf)=>{
                        var sid="data_field_" + _obj.doc.name + "_" + sf.name + "_" + k
                        sub_data_fields[sf.name] = {
                            "value": eval(_obj.fieldtype_ui_operators(sf.source, sid)["getter"]),
                            "type": sf.source
                        }
                    })
                default_values["Multiple"].push(sub_data_fields)	
                }
            }
        })
        this.chart_config[current_chart_type]["option_fields"].forEach((df) =>{
            if (df.type == "Single"){
                var id="data_field_" + _obj.doc.name + "_" + df.name + "_0"
                default_values["Single"][df.name] = {
                    value: eval(_obj.fieldtype_ui_operators(df.source, id)["getter"]),
                    type: df.source
                }
            }
            else if (df.type == "Multiple"){
                for (var k=0; k < _obj["create_" + _obj.doc.name +  "_datasets_counter"] + 1; k++){
                    var sub_data_fields = {}
                    df.fields.forEach((sf)=>{
                        var sid="data_field_" + _obj.doc.name + "_" + sf.name + "_" + k
                        sub_data_fields[sf.name] = {
                            "value": eval(_obj.fieldtype_ui_operators(sf.source, sid)["getter"]),
                            "type": sf.source
                        }
                    })
                default_values["Multiple"].push(sub_data_fields)	
                }
            }
        })
        default_values["Datasets Counter"] = _obj["create_" + _obj.doc.name +  "_datasets_counter"]
        default_values["Chart Type"] = $("select[id='chart-type-" + this.doc.name + "']").val();
        frappe.call({
            method: "latte.dashboard.doctype.dashboard_data_slice.save_chart_config",
            args: {
                data_slice: _obj.doc.name,
                config: JSON.stringify(default_values)
            },
            callback: function(response){
                frappe.msgprint("Default Saved Successfully")
            }
        })
    }

    render() {
        $(this.chart_container.find(".data-wrapper")).html( 
            `<div id="${this.doc.name}" class="dashboard-chart ${latte.dashboard.dashboard_doc.disable_position == 1 ? '': 'perfect-position'}">
            <style>	
                canvas {
                    -moz-user-select: none;
                    -webkit-user-select: none;
                    -ms-user-select: none;
                }
                
            </style>
            <div class="modal fade" id="modal-configure-${this.doc.name}" role="dialog">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h4 class="modal-title">
                            Advanced settings
                            </h4>
                        </div>
                        <div class="modal-body">
                            <div id="config-tab-${this.doc.name}">
                                <form class="form-horizontal" action="">
                                    <div class="form-group">
                                        <label class="control-label col-sm-4" for="">Chart Type: </label>
                                        <div class="col-sm-8">
                                            <select class="form-control minimal" id="chart-type-${this.doc.name}" select-chart-type="dummy">
                                                <option></option>
                                                <option value="Line">Line Chart</option>
                                                <option value="Bar">Bar Chart</option>
                                                <option value="Pie">Pie Chart</option>
                                            </select>
                                        </div>
                                    </div>
                                    <div id="action-bar-${this.doc.name}" class="row box-inner">
                                        <button class="erPrimaryBtn" id="update-chart-${this.doc.name}" update-chart="dummy">Refresh</button>
                                        <button type="button" class="erDefaultBtn" id="save-defaults-${this.doc.name}" save-chart="dummy">Save Default</button>
                                    </div>
                                </form>
                            </div>	
                        </div>
                        <div class="modal-footer">
                            
                        </div>
                    </div>
                </div>
            </div>
            
            <div class = "row">
                <div id="chart-holder-${this.doc.name}" class="col-md-11 col-sm-11">
                    <canvas id="canvas-${this.doc.name}"></canvas>
                </div>
                <div id="chart-config" class= "col-md-1 col-sm-1">
                    <div class="row">
                        <span class="glyphicon glyphicon-plus-sign slide-toggle" id="configure-${this.doc.name}" style="float:right"></span>
                    </div>
                </div>
            </div>
        </div>`);
        
        if(! frappe.utils.is_empty(this.doc.chart_default_config)){
            this.load_chart_defaults()
            var current_chart_type = $("select[id='chart-type-" + this.doc.name + "']").val() || this.doc.chart_type
            this.render_methods[current_chart_type](this)
        }
        
        $("span[id='configure-" + this.doc.name + "']").click(function(){
            $("div[id='modal-" + this.id + "']").modal('toggle')
        });

        this.chart_container.find("select[select-chart-type]").each((i, o) => {
            let _that = this;
            $(o).change(e => _that.render_chart_metadata());
        });
        this.chart_container.find("button[update-chart]").each((i, o) => {
            let _that = this;
            $(o).click((e) => {
                $("canvas[id='canvas-" + _that.doc.name + "']").remove()
                $("div[id='chart-holder-" + _that.doc.name + "']").append('<canvas id="canvas-' + _that.doc.name + '"></canvas>')
                var current_chart_type = $("select[id='chart-type-" + _that.doc.name + "']").val() || _that.doc.chart_type
                _that.render_methods[current_chart_type](_that)
            });
        });

        this.chart_container.find("button[save-chart]").each((i, o) => {
            let _that = this;
            $(o).click(e => _that.save_chart_defaults());
        });
        
        $(this.chart_container.find(".data-wrapper")).css('background-color', this.doc.background_color || 'var(--dashboard-background-color)');
        this.container.find('.chart-column-container').css('background-color', this.doc.background_color || 'var(--dashboard-background-color)');
        this.container.find('.chart-column-container').css('color', this.doc.text_color || 'var(--dashboard-font-color)');
        
        // Run Post JS
        this.run_post_js();
    }
}
