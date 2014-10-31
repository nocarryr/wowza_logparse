var MobileDetector = {
    os: null,
    userAgent: null,
    browser: null,
    browserVersion: null,
    searchStr: ['android', 'ipad', 'iphone', 'ipod'],
    detect: function(){
        var self = this;
        var uA = navigator.userAgent;
        var browserVer = null;
        var browser = null;
        self.userAgent = uA;
        uA = uA.toLowerCase();
        $.each(self.searchStr, function(i, sStr){
            if (uA.search(sStr) != -1){
                var f = self['detect_' + sStr];
                self.os = sStr;
                if (typeof(f) != "undefined"){
                    f();
                }
                return false;
            }
        });
        if (self.userAgent.search("Chrome")){
            browser = "Chrome";
            browserVer = self.userAgent.split("Chrome/")[1];
            browserVer = browserVer.split(" ")[0]
        }
        self.browser = browser;
        self.browserVersion = browserVer;
    },
    getData: function(){
        var self = this;
        var keys = ['os', 'userAgent', 'browser', 'browserVersion'];
        var data = self.data;
        if (typeof(data) == 'undefined'){
            data = {};
            self.data = data;
        }
        $.each(keys, function(i, key){
            data[key] = self[key];
        });
        return data;
    },
    detect_android: function(){
        var self = this;
        // do version detection
        self.version = 'not implemented';
    },
};

MobileDetector.detect();