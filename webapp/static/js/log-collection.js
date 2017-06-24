$(function(){
    var query = new QueryGroup($(".log-table").data('query_data'));

    var storeFilters = function(){
        var fieldNames = [],
            storeKey = [$("table").data('collectionName'), 'filters'].join('_');
        $(".active-fields button:not(.active)").each(function(){
            fieldNames.push($(this).data('fieldName'));
        });
        localStorage.setItem(storeKey, JSON.stringify(fieldNames));
    };

    var getFilters = function(){
        var storeKey = [$("table").data('collectionName'), 'filters'].join('_'),
            fieldNames = localStorage.getItem(storeKey);
        if (fieldNames === null){
            fieldNames = [];
            // $(".field-header").each(function(){
            //     fieldNames.push($(this).data('fieldName'));
            // });
            localStorage.setItem(storeKey, JSON.stringify(fieldNames))
        } else {
            fieldNames = JSON.parse(fieldNames);
        }
        $(".active-fields button").each(function(){
            var $btn = $(this);
            if (fieldNames.indexOf($btn.data('fieldName')) != -1){
                $btn.removeClass('active')
                    .data('fieldHeader').trigger('setHidden', [true]);
            } else {
                $btn.addClass('active')
                    .data('fieldHeader').trigger('setHidden', [false]);
            }
        });
    };

    var setLocation = function(page_num){
        var current = window.location.href.split('?')[0],
            qdata = query.serialize(),
            qstr = ['_QueryGroup_', JSON.stringify(qdata)].join('=');

        if (typeof(page_num) != 'undefined'){
            page_num -= 1;
            qstr = [qstr, ['p', page_num.toString()].join('=')].join('&');
        }
        console.log(qdata);
        console.log(qstr);

        window.location = [current, qstr].join('?');
    };

    $(".pagination .next-page").click(function(e){
        e.preventDefault();
        setLocation($(".pagination").data('pageNum') + 1);
    });

    $(".pagination .prev-page").click(function(e){
        e.preventDefault();
        setLocation($(".pagination").data('pageNum') - 1);
    });

    $(".log-entry-field[data-field-name*=datetime]").each(function(){
        var $td = $(this),
            d = new Date($td.text());
        $td.text(d.toLocaleString()).data('fieldValue', d);
    });
    // $(".field-header-link").click(function(e){
    //     var $this = $(this),
    //         $i = $("i", $this),
    //         fieldName = $this.parent().data('fieldName'),
    //         query = {};
    //     e.preventDefault();
    //     if ($i.hasClass('fa-sort-up')){
    //         query.s = '-' + fieldName;
    //     } else if ($i.hasClass('fa-sort-down')){
    //         query.s = '';
    //     } else {
    //         query.s = fieldName;
    //     }
    //     setLocation(query);
    // });

    $(".active-fields").data('buttons', {});

    $(".active-fields button").each(function(){
        var $btn = $(this);
        $(".active-fields").data('buttons')[$btn.data('fieldName')] = $btn;
    }).click(function(){
        var $btn = $(this),
            $header = $btn.data('fieldHeader'),
            hidden = $btn.hasClass('active')
        $header.trigger('setHidden', [hidden]);
        $btn.toggleClass('active');
        storeFilters();
    });

    $(".log-entry-field").each(function(){
        var $this = $(this),
            $header = $("#F_header".replace('F', $this.data('fieldName'))),
            $filterBtn = $(".active-fields").data('buttons')[$this.data('fieldName')];
        $header
            .data('entryField', $this)
            .on('setHidden', function(e, hidden){
                if (hidden){
                    $this.addClass('hidden');
                } else {
                    $this.removeClass('hidden');
                }
            });
        $filterBtn.data('entryField', $this);
    });
    $(".field-header").each(function(){
        var $this = $(this),
            $filterBtn = $(".active-fields").data('buttons')[$this.data('fieldName')];
        $filterBtn.data('fieldHeader', $this);
        if ($this.hasClass('hidden')){
            $filterBtn.addClass('active');
        }
    }).on('setHidden', function(e, hidden){
        if (hidden){
            $(this).addClass('hidden');
        } else {
            $(this).removeClass('hidden');
        }
    });

    getFilters();


    $.contextMenu({
        selector: ".log-entry-field",
        items:{
            'filter':{
                name: 'Filter by this value',
                callback: function(key, opt){
                    var $td = opt.$trigger,
                        q = query.addQuery($td.data('fieldName'));
                    console.log(q);
                    q.addFilter($td.data('fieldValue'));
                    setLocation();
                },
            },
            'exclude':{
                name: 'Exclude this value',
                callback: function(key, opt){
                    var $td = opt.$trigger,
                        q = query.addQuery($td.data('fieldName'));
                    q.addExclude($td.data('fieldValue'));
                    setLocation();
                },
            },
            'search':{
                name: 'Search',
                type: 'text',
                events:{
                    keyup: function(e){
                        // console.log($(this));
                        // console.log(e);
                        if (e.keyCode != 13){
                            return;
                        }
                        var $inEl = $(this),
                            $td = e.data.$trigger,
                            q = query.addQuery($td.data('fieldName'));
                        q.addFilter($inEl.val());
                        setLocation();
                    },
                },
                // callback: function(key, opt){
                //     var txtVal = opt.$trigger.val();
                //     console.log('text input: ', txtVal);
                // },
            },
            'clearFilter':{
                name: 'Clear filters',
                callback: function(key, opt){
                    window.location = window.location.href.split('?')[0];
                    // console.log(getUrlQuery());
                    // // if (typeof(getUrlQuery().query.filter_field) != 'undefined'){
                    // //     return;
                    // // }
                    // setLocation({
                    //     p:0,
                    //     filter_field:'',
                    //     filter_value:'',
                    //     exclude_field:'',
                    //     exclude_value:'',
                    // });
                },
            },
            'uniques':{
                name:'Show all values for this field',
                callback: function(key, opt){
                    var $td = opt.$trigger;
                    window.location = $td.data('uniquesHref');
                },
            },
        },
    });

    $(".field-values li a").each(function(){
        var $this = $(this),
            query = {};
        query.filter_field = $(".field-values").data('fieldName');
        query.filter_value = $this.text();
        $this.attr('href', [$this.attr('href'), buildQueryStr(query)].join('?'));
    });

});
