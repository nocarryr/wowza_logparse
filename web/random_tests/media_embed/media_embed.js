var media_embed = {
    embed_type_map: {
        "rtmp": ["http", "jwplayer.rss"],
        "hls": ["http", "playlist.m3u8"],
        "vidtag": ["http", "playlist.m3u8"],
        "videojs":["http", "playlist.m3u8"],
        "strobe":["http", "manifest.f4m"],
    },
    initialized: false,
    player_size: [640, 360],
    player_max_width: 1280,
    aspect_ratio: [16, 9],
    initialize: function(){
        var self = this;
        if (self.initialized){
            return;
        }
        self.data = {"base_url": "",
                     "app_name": "",
                     "stream_name": "",
                     "embed_type": "rtmp",
                     "stream_url": ""};
        $("input", $("#stream_input_fieldset")).on('keyup focusout', function(){
            var $this = $(this);
            var key = $this.attr("id").split("_input")[0];
            self.data[key] = $this.val();
            self.buildUrl();
        });
        $("input", $("#embedtype_fieldset")).change(function(){
            var $this = $(this);
            self.data.embed_type = $this.val();
            self.buildUrl();
        });
        $("#stream_url_input").on('keyup focusout', function(){
            var $this = $(this);
            var value = $this.val();
            if (value == ""){
                return;
            }
            if (!self.data.stream_url){
                return;
            }
            if (value == self.data.stream_url){
                return;
            }
            self.clearForm();
            self.data.stream_url = value;
            if ($this.val() != value){
                $this.val(value);
            }
        });
        $("input", $("#player_size_fieldset")).on('change focusout', function(){
            var $this = $(this);
            var key = $this.attr('id').split('_')[1];
            var size = null;
            var i = null;
            if (!$this.data('value_initialized')){
                return;
            }
            if (key == 'width'){
                i = 0;
            } else {
                i = 1;
            }
            size = parseInt($this.val());
            if (size == self.player_size[i]){
                return;
            }
            $("#player_size_fieldset").data('hasChanged', true);
            self.player_size[i] = size;
            //$("#player-container").css(key, size);
        });
        self.player_size = self.calcPlayerSize();
        $.each(['width', 'height'], function(i, key){
            var $elem = $("#" + ['player', key, 'input'].join('_'));
            $elem.val(self.player_size[i].toString());
            $elem.data('value_initialized', true);
        });
        $("#start-btn").on("click", function(){
            try{
                self.doEmbed();
            } catch (e){
                showDebug([e.fileName, e.lineNumber, e.message]);
            }
        });
        $("#stop-btn").on("click", function(){
            self.doStop();
        });
        $("#clear-btn").on("click", function(){
            self.clearForm();
        });
        $(window).on("orientationchange", function(){
            var player = null;
            if (self.data.embed_type != 'vidtag'){
                return;
            }
            self.player_size = self.calcPlayerSize();
            if (!$("#player").length){
                return;
            }
            if ($("video").length){
                player = $("video");
                player.width(self.player_size[0].toString() + 'px');
                player.height(self.player_size[1].toString() + 'px');
            }
        });
        self.loadJWScript();
        self.displayMediaSupport();
        self.initialized = true;
    },
    loadJWScript: function(){
        // jwtoken.js must declare the var "JWP_TOKEN" as is required by jwplayer6
        var jsUrl = "http://jwpsrv.com/library/TOKEN.js";
        var tkUrl = "jwtoken.js"
        $.getScript(tkUrl, function(){
            jsUrl = jsUrl.replace("TOKEN", JWP_TOKEN);
            $.getScript(jsUrl);
        });
    },
    buildUrl: function(){
        var self = this;
        var url = self.data.stream_url;
        if (self.data.base_url != ""){

            url = self.embed_type_map[self.data.embed_type][0] + "://";
            url += [self.data.base_url,
                    self.data.app_name, "_definst_",
                    self.data.stream_name].join("/");
                    //self.embed_type_map[self.data.embed_type][1]].join("/");
            self.data.stream_url = url;
            //$("#stream_url_input").val(url);
        }
        self.updateFormFields();
    },
    updateFormFields: function(){
        var self = this;
        $.each(self.data, function(key, val){
            var $elem = $("[name=KEY]".replace('KEY', key));
            if (key == 'embed_type'){
                $("[value=VAL]".replace('VAL', val), $elem).trigger('click');
                $elem.checkboxradio('refresh');
            }
            if (!$elem.length){
                return;
            }
            if ($elem.val() == val){
                return;
            }
            $elem.val(val);
        });
    },
    clearForm: function(){
        var self = this;
        $.each(['stream_url', 'base_url', 'app_name', 'stream_name', 'embed_type'], function(i, key){
            var newData = "";
            var $elem = $("#" + key + "_fieldset");
            if (!$elem.length){
                $elem = $("#" + key + "_input");
            }
            if (key == 'embed_type'){
                newData = "rtmp"
            }
            self.data[key] = newData;
            $elem.val(newData);
        });
    },
    doEmbed: function(){
        var self = this;
        var container = $("#player-container");
        self.doStop();
        if (!self.data.stream_url){
            return;
        }
        if (self.data.embed_type != 'videojs' && MobileDetector.os == "android"){
            var androidMethodSet = false;
            if (MobileDetector.browser == "Chrome"){
                var bversion = MobileDetector.browserVersion.split(".")[0]
                bversion = parseInt(bversion);
                if (bversion >= 34){
                    self.data.embed_type = "vidtag";
                    self.updateFormFields();
                    androidMethodSet = true;
                    //container.append('<a href="URL">Click to Play</a>'.replace('URL', [self.data.stream_url, 'playlist.m3u8'].join('/')));
                }
            }
            if (!androidMethodSet){
                self.insertAndroidFallbacks(container);
            }
        }
        var player = $('<div id="player"></div>');
        container.append(player);
        self.player_size = self.calcPlayerSize();
        container.width(self.player_size[0]);
        container.height(self.player_size[1]);
        if (self.data.embed_type == 'videojs'){
            var vidtag = $('<video id="vidjs" class="video-js vjs-default-skin"></video');
            var vidjsOpts = {'controls':true,
                             'autoplay':true};
            self.data.player_size = self.calcPlayerSize();
            vidjsOpts['width'] = self.data.player_size[0].toString();
            vidjsOpts['height'] = self.data.player_size[1].toString();
            vidtag.append('<source src="URL" type="application/vnd.apple.mpegurl">'.replace('URL', [self.data.stream_url, 'playlist.m3u8'].join('/')));
            container.append(vidtag);
            videojs('vidjs', vidjsOpts, function(){
                var $this = $(this);
                console.log('vidjs load: ', $this);
            });
        } else if (self.data.embed_type == 'strobe'){
            var strobeOpts = {
                'width':self.player_size[0],
                'height':self.player_size[1],
                'src':[self.data.stream_url, 'manifest.f4m'].join('/'),
                'swf':'strobe-media/StrobeMediaPlayback.swf',
                'expressInstallSwfUrl': 'strobe-media/expressInstall.swf',
            };
            strobeOpts = $.fn.adaptiveexperienceconfigurator.adapt(strobeOpts);
            player.strobemediaplayback(strobeOpts);
        } else if (self.data.embed_type != "vidtag"){
            jwplayer("player").setup({
                width: self.player_size[0].toString(),
                height: self.player_size[1].toString(),
                sources: [{
                    file: [self.data.stream_url, "jwplayer.smil"].join("/"),
                }, {
                    file: [self.data.stream_url, "playlist.m3u8"].join("/"),
                }],
                fallback: false,
            });
        } else {
            var vidtag = $('<video controls="true" autoplay="true"></video>');
            vidtag.append('<source src="URL" type="application/vnd.apple.mpegurl">'.replace('URL', [self.data.stream_url, 'playlist.m3u8'].join('/')));
            container.append(vidtag);
            vidtag.width(self.player_size[0].toString() + 'px');
            vidtag.height(self.player_size[1].toString() + 'px');
            vidtag[0].load();
        }
    },
    doStop: function(){
        if ($("div", $("#player-container")).length){
            $("#player-container").empty();
        }
    },
    calcPlayerSize: function(container){
        var self = this;
        if ($("#player_size_fieldset").data('hasChanged') == true){
            return self.player_size;
        }
        if (typeof(container) == "undefined"){
            container = $("#player-container");
        }
        var complete = null;
        var x = container.innerWidth();
        var xMin = x * 0.5;
        var y = null;
        var ratio = self.aspect_ratio[0] / self.aspect_ratio[1];
        function integersFound(_x, _y){
            if (Math.floor(_x) != _x){
                return false;
            }
            if (Math.floor(_y) != _y){
                return false;
            }
        }
        y = x / ratio;
        complete = integersFound(x, y);
        while (!complete){
            x -= 1;
            y = x / ratio;
            complete = integersFound(x, y);
            if (!complete && x <=xMin){
                x = container.innerWidth();
                y = x / ratio;
                y = Math.floor(y);
                break;
            }
        }
        return [x, y];
    },
    insertAndroidFallbacks: function(container){
        var self = this;
        var rtspUrl = self.data.stream_url;
        var hlsUrl = [self.data.stream_url, 'playlist.m3u8'].join('/');
        rtspUrl = ['rtsp', rtspUrl.split('://')[1]].join('://');
        container.append('<p><a href="RTSPURL">Click to watch using RTSP</a></p>'.replace('RTSPURL', rtspUrl));
        container.append('<p><a href="HLSURL">Click to watch using HLS</a></p>'.replace('HLSURL', hlsUrl));
    },
    displayMediaSupport: function(container){
        var vidElem, mimeTypes, data, tableDiv, tblHead, tblBody;
        mimeTypes = ['application/x-mpegurl',
                     'application/vnd.apple.mpegurl',
                     'video/mp4',
                     'video/webm',
                     'video/ogg',
                     'audio/ogg',
                     'audio/mpeg',
                     'application/ogg'];
        if (typeof(container) == "undefined"){
            container = $("[data-role=content]");
        }
        data = {};
        vidElem = $('<video id="video-test-element"></video>');
        container.append(vidElem);
        tableDiv = $('<div id="media-support-table" class="ui-mini" style="text-align:center;width:50%"></div>');
        tableDiv.data('support', data);
        tblHead = $('<div class="ui-grid-a"></div>');
        tableDiv.append(tblHead);
        tblHead.append('<div class="ui-block-a"><div class="ui-bar ui-bar-a">MIME Type</div></div>');
        tblHead.append('<div class="ui-block-b"><div class="ui-bar ui-bar-a">Support</div></div>');
        $.each(mimeTypes, function(i, mType){
            var rowDiv = $('<div class="ui-grid-a"></div>');
            var supportStr = vidElem[0].canPlayType(mType);
            if (supportStr == ""){
                supportStr = "null";
            }
            rowDiv.append('<div class="ui-block-a"><div class="ui-bar ui-bar-a">M</div></div>'.replace('M', mType));
            rowDiv.append('<div class="ui-block-b"><div class="ui-bar ui-bar-a">R</div></div>'.replace('R', supportStr));
            tableDiv.append(rowDiv);
            data[mType] = supportStr;
        });
        vidElem.remove();
        container.append(tableDiv);
        container.enhanceWithin();
    },
};

$("[data-role=page]").on("pagecreate", function(){
    media_embed.initialize();
});

$("form").submit(function(e){
    e.preventDefault();
});
