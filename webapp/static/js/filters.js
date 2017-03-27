$(function(){
    var Selector = function(data){
        if (typeof(data) == 'undefined'){
            data = {};
        }
        if (typeof(data['_Selector_']) != 'undefined'){
            data = data['_Selector_'];
        }
        this.selector_key = data.selector_key || data._selector_key;
        this.values = data.values || [];
    };
    Selector.prototype = {
        serialize: function(){
            return {'_Selector_':{
                '_selector_key':this.selector_key,
                'values':this.values,
            }}
        },
    };

    var Query = function(data){
        var self = this;
        if (typeof(data) == 'undefined'){
            data = {};
        }
        if (typeof(data['_Query_']) != 'undefined'){
            data = data['_Query_'];
        }
        this.key = data.key;
        this.sort = data.sort || false;
        this.reverse = data.reverse || false;
        if (this.reverse){
            this.sort = true;
        }
        this.selectors = {};
        if (typeof(data.selectors) != 'undefined'){
            $.each(data.selectors, function(key, sdata){
                var selector = new Selector(sdata);
                self.selectors[key] = selector;
            });
        }
    };
    Query.prototype = {
        addSelector: function(selector_key){
            var sel = this.selectors[selector_key];
            if (typeof(sel) == 'undefined'){
                sel = new Selector({'selector_key':selector_key});
                this.selectors[selector_key] = sel;
            }
            return sel;
        },
        addFilter: function(value){
            var sel = this.addSelector('$in');
            sel.values.push(value);
            return sel;
        },
        addExclude: function(value){
            var sel = this.addSelector('$nin');
            sel.values.push(value);
            return sel;
        },
        serialize: function(){
            var d = {'_Query_':{
                key: this.key,
                sort: this.sort,
                reverse: this.reverse,
                selectors: {},
            }};
            $.each(this.selectors, function(key, sel){
                d._Query_.selectors[key] = sel.serialize();
            });
            return d;
        },
    };

    var QueryGroup = function(data){
        var self = this;
        if (typeof(data['_QueryGroup_']) != 'undefined'){
            data = data['_QueryGroup_'];
        }
        this.queries = {};
        this.query_order = [];
        $.each(data.query_order, function(i, qdata){
            var q = new Query(qdata);
            if (typeof(self.queries[q.key]) != 'undefined'){
                return;
            }
            self.queries[q.key] = q;
            self.query_order.push(q);
        });
    };
    QueryGroup.prototype = {
        addQuery: function(key){
            if (typeof(this.queries[key]) != 'undefined'){
                return this.queries[key];
            }
            var q = new Query({'key':key});
            this.queries[key] = q;
            this.query_order.push(q);
            return q;
        },
        serialize: function(){
            d = {'_QueryGroup_':{'query_order':[]}};
            $.each(this.query_order, function(i, q){
                d._QueryGroup_.query_order.push(q.serialize());
            });
            return d;
        },
    };

    window.QueryGroup = QueryGroup;

});
