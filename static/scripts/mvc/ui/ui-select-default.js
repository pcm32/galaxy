define(["utils/utils","mvc/ui/ui-buttons"],function(a,b){var c=Backbone.View.extend({initialize:function(b){var c=this;this.model=b&&b.model||new Backbone.Model({id:a.uid(),cls:"ui-select",error_text:"No options available",empty_text:"Nothing selected",visible:!0,wait:!1,multiple:!1,searchable:!0,optional:!1,disabled:!1,onchange:function(){}}).set(b),this.on("change",function(){c.model.get("onchange")(c.value())}),this.listenTo(this.model,"change:data",this._changeData,this),this.listenTo(this.model,"change:disabled",this._changeDisabled,this),this.listenTo(this.model,"change:wait",this._changeWait,this),this.listenTo(this.model,"change:visible",this._changeVisible,this),this.listenTo(this.model,"change:value",this._changeValue,this),this.listenTo(this.model,"change:multiple change:searchable change:cls change:id",this.render,this),this.render()},render:function(){var a=this;this.$el.empty().append(this.$select=$("<select/>")).append(this.$dropdown=$("<div/>")).append(this.$resize=$("<div/>").append(this.$resize_icon=$("<i/>"))),this.$el.addClass(this.model.get("cls")).attr("id",this.model.get("id")),this.$select.addClass("select").attr("id",this.model.get("id")+"_select").prop("multiple",this.model.get("multiple")).on("change",function(){a.value(a._getValue()),a.trigger("change")}),this.$dropdown.hide(),this.model.get("multiple")||this.$dropdown.show().on("click",function(){a.$select.select2&&a.$select.select2("open")}),this.$resize.hide(),this.model.get("multiple")&&!this.model.get("searchable")&&(this.$resize_icon.addClass("fa fa-angle-double-right fa-rotate-45"),this.$resize.show().removeClass().addClass("icon-resize").off("mousedown").on("mousedown",function(b){var c=b.pageY,d=a.$select.height();a.minHeight=a.minHeight||d,$("#dd-helper").show().on("mousemove",function(b){a.$select.height(Math.max(d+(b.pageY-c),a.minHeight))}).on("mouseup mouseleave",function(){$("#dd-helper").hide().off()})})),this.all_button=null,this.model.get("multiple")&&(this.model.get("searchable")?(this.all_button=new b.ButtonCheck({onclick:function(){var b=[];0!==a.all_button.value()&&_.each(a.model.get("data"),function(a){b.push(a.value)}),a.value(b),a.trigger("change")}}),this.$el.prepend(this.all_button.$el)):this.$el.addClass("ui-select-multiple")),this._changeData(),this._changeWait(),this._changeVisible()},_changeData:function(){var a=this;this.$select.find("option").remove(),!this.model.get("multiple")&&this.model.get("optional")&&this.$select.append(this._templateOption({value:"__null__",label:a.model.get("empty_text")})),_.each(this.model.get("data"),function(b){a.$select.append(a._templateOption(b))}),0==this.length()?this.$select.prop("disabled",!0).append(this._templateOption({value:"__null__",label:this.model.get("error_text")})):this.$select.prop("disabled",!1),this.$select.select2("destroy"),this.model.get("searchable")&&(this.$select.select2({closeOnSelect:!this.model.get("multiple")}),this.$(".select2-container .select2-search input").off("blur")),this._changeValue()},_changeDisabled:function(){this.$select.prop("disabled",this.model.get("disabled"))},_changeWait:function(){this.$dropdown.removeClass().addClass("icon-dropdown fa").addClass(this.model.get("wait")?"fa-spinner fa-spin":"fa-caret-down")},_changeVisible:function(){this.$el[this.model.get("visible")?"show":"hide"](),this.$select[this.model.get("visible")?"show":"hide"]()},_changeValue:function(){this._setValue(this.model.get("value")),null!==this._getValue()||this.model.get("multiple")||this.model.get("optional")||this._setValue(this.first());var a=this._getValue();this.all_button&&this.all_button.value($.isArray(a)?a.length:0,this.length())},value:function(a){return void 0!==a&&this.model.set("value",a),this._getValue()},first:function(){var a=this.$select.find("option").first();return a.length>0?a.val():null},exists:function(a){return this.$select.find('option[value="'+a+'"]').length>0},text:function(){return this.$select.find("option:selected").first().text()},show:function(){this.model.set("visible",!0)},hide:function(){this.model.set("visible",!1)},wait:function(){this.model.set("wait",!0)},unwait:function(){this.model.set("wait",!1)},disabled:function(){return this.model.get("disabled")},enable:function(){this.model.set("disabled",!1)},disable:function(){this.model.set("disabled",!0)},add:function(a,b){_.each(this.model.get("data"),function(b){!_.findWhere(a,b)&&a.push(b)}),b&&a&&a.sort(b),this.model.set("data",a)},update:function(a){this.model.set("data",a)},setOnChange:function(a){this.model.set("onchange",a)},length:function(){return $.isArray(this.model.get("data"))?this.model.get("data").length:0},_setValue:function(a){void 0!==a&&(a=null!==a?a:"__null__",this.$select.val(a),this.$select.select2&&this.$select.select2("val",a))},_getValue:function(){var b=this.$select.val();return a.isEmpty(b)?null:b},_templateOption:function(a){return $("<option/>").attr("value",a.value).html(_.escape(a.label))}});return{View:c}});
//# sourceMappingURL=../../../maps/mvc/ui/ui-select-default.js.map