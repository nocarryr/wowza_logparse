(function($){
    var playerEmbedder = {
        embed_methods: ['auto', 'html5', 'videojs', 'strobe'],
        html5_embed_method: 'html5',
        libRootUrls: {
            'videojs':'/videojs',
            'strobe':'/strobe-media',
        },
        cssUrls: {
            'videojs':[
                '//vjs.zencdn.net/4.5/video-js.css',
            ],
            //'strobe':[
                //'_ROOTURL_STROBE_/jquery.strobemediaplayback.css',
            //],
        },
        scriptUrls: {
            'videojs':[
                '//vjs.zencdn.net/4.5/video.js',
                //'_ROOTURL_VIDEOJS_/videojs.hls.min.js',
            ],
            'strobe':[
                '//ajax.googleapis.com/ajax/libs/swfobject/2.2/swfobject.js',
                //'_ROOTURL_STROBE_/jquery.strobemediaplayback.js',
            ],
        },
        debugMode: false,
        debugOutputFunction: null,
        debugSaveDataEnable: false,
        debugData: [],
        debug: function(){
            if (!this.debugMode){
                return;
            }
            if (typeof(this.firstDebugTimestamp) == 'undefined'){
                this.firstDebugTimestamp = new Date();
            }
            var args = [new Date() - this.firstDebugTimestamp, 'playerEmbedder'];
            $.each(arguments, function(i, arg){
                args.push(arg);
            });
            if (this.debugOutputFunction == 'console'){
                console.log(args);
            } else if (this.debugOutputFunction){
                this.debugOutputFunction(args);
            }
            if (this.debugSaveDataEnable){
                this.debugData.push(args);
            }
        },
        formatLibUrl: function(url){
            var self = this;
            var replTxt = null;
            var lib = null;
            var libUrl = null;
            if (url.indexOf('_ROOTURL_') == -1){
                return url;
            }
            lib = url.split('_ROOTURL_')[1].split('_')[0];
            replTxt = ['', 'ROOTURL', lib, ''].join('_');
            libUrl = self.libRootUrls[lib.toLowerCase()];
            return url.replace(replTxt, libUrl);
        },
        loadSources: function(libName){
            var self = this;
            var cssComplete = false;
            var scriptsComplete = false;
            var loadedSources = $("body").data('player_embedder_sources_loaded');
            self.debug('loading sources');
            if (typeof(loadedSources) == 'undefined'){
                loadedSources = {};
                $("body").data('player_embedder_sources_loaded', loadedSources);
            } else {
                self.debug('sources already loaded: ', loadedSources);
            }
            function loadCss(){
                var numResponse = 0;
                var urls = self.cssUrls[libName];
                if (!urls || urls.length == 0){
                    $("body").trigger('player_embedder_css_loaded');
                    return;
                }
                self.debug('loading css');
                $.each(urls, function(i, url){
                    if (!url){
                        return;
                    }
                    url = self.formatLibUrl(url);
                    $.get(url, function(data){
                        var s = $('<style type="text/css"></style');
                        s.text(data);
                        $("body").append(s);
                        numResponse += 1;
                        if (numResponse == urls.length){
                            $("body").trigger('player_embedder_css_loaded');
                        }
                    });
                });
            }
            function loadJs(){
                var numResponse = 0;
                var urls = self.scriptUrls[libName];
                if (!urls || urls.length == 0){
                    $("body").trigger('player_embedder_scripts_loaded');
                    return;
                }
                self.debug('loading js');
                $.each(urls, function(i, url){
                    if (!url){
                        return;
                    }
                    url = self.formatLibUrl(url);
                    $.getScript(url, function(){
                        numResponse += 1;
                        if (numResponse == urls.length){
                            $("body").trigger('player_embedder_scripts_loaded');
                        }
                    });
                });
            }
            function doComplete(){
                loadedSources[libName] = true;
                if (cssComplete && scriptsComplete){
                    self.debug('all sources loaded');
                    $("body").trigger('player_embedder_sources_loaded');
                }
            }
            if (loadedSources[libName]){
                cssComplete = true;
                scriptsComplete = true;
                doComplete();
                return;
            }
            $("body").one('player_embedder_css_loaded', function(){
                self.debug('css loaded');
                cssComplete = true;
                doComplete();
            });
            $("body").one('player_embedder_scripts_loaded', function(){
                self.debug('js loaded');
                scriptsComplete = true;
                doComplete();
            });
            loadCss();
            loadJs();
        },
        streamSrc: function(base_url){
                var d = {};
                d.base_url = base_url
                d.hls_url = [base_url, 'playlist.m3u8'].join('/')
                d.hds_url = [base_url, 'manifest.f4m'].join('/')
                return d;
        },
        embedDataDefaults: {
            streamSrc: '',
            playerId: 'player',
            playerClasses: [],
            embed_method: 'auto',
            size: null,
            sizeWithContainer: false,
            sizeByCSS: false,
            maxWidth: 640,
            aspect_ratio: [16, 9],
            container: null,
            swfUrl: '_ROOTURL_STROBE_/StrobeMediaPlayback.swf',
            expressInstallSwfUrl: '_ROOTURL_STROBE_/expressInstall.swf',
        },
        embedData: function(data){
            d = {}
            $.each(playerEmbedder.embedDataDefaults, function(key, val){
                if (typeof(data[key]) != 'undefined'){
                    val = data[key];
                }
                if (key == 'streamSrc'){
                    val = playerEmbedder.streamSrc(val);
                } else if (key == 'swfUrl' || key == 'expressInstallSwfUrl'){
                    val = playerEmbedder.formatLibUrl(val);
                }
                d[key] = val;
            });
            return d;
        },
        addPlayerClasses: function(player, data){
            if (data.playerClasses.length == 0){
                return;
            }
            player.addClass(data.playerClasses.join(' '));
        },
        buildFallbackContent: function(data){
            var cdiv = $('<ul style="margin-top:25%;text-align:center;font-size:1.5em;"></ul>'),
                ua = navigator.userAgent,
                isDesktop = false;
            this.debug('building fallback content');
            try {
                if (typeof(window.orientation) == 'undefined'){
                    isDesktop = true;
                }
            } catch(e) {
                this.debug('window.orientation check failed: ');
                this.debug(e);
            }
            if (isDesktop){
                cdiv.append('<li><p>Flash Player plugin either not installed or out of date.</p></li>');
                cdiv.append('<li><a href="//www.adobe.com/software/flash/about/‎" taget="_blank">Click Here to update or install Flash</a></li>');
            } else {
                cdiv.append('<li><a href="URL" type="application/vnd.apple.mpegurl">Click here to open in your mobile device</a></li>'.replace('URL', data.streamSrc.hls_url));
            }
            if (ua.toLowerCase().search('android') != -1){
                data.isAndroid = true;
            //    cdiv.append('<li><a href="URL">Click here to open in the video player app on you mobile device</a></li>'.replace('URL', data.streamSrc.hls_url));
            }
            if (data.fallbackContentFunction){
                cdiv = data.fallbackContentFunction(cdiv);
            } else {
                data.container.one('player_embed_complete', function(){
                    $("a", cdiv).each(function(){
                        var $this = $(this),
                            s = $this.attr('href'),
                            firstUnicodeChar;
                        for (i=1; i<s.length; i++){
                            if (s.charCodeAt(i) > 255){
                                firstUnicodeChar = i;
                                break;
                            }
                        }
                        if (firstUnicodeChar){
                            s = s.slice(0, firstUnicodeChar);
                            $this.attr('href', s);
                        }
                    });
                });
            }
            this.debug('fallback content built');
            return cdiv;
        },
        testHLSSupport: function(data){
            this.debug('testing HLS capabilities');
            var result = false,
                vidtag = $('<video></video>');
            try {
                data.container.append(vidtag);
                if (vidtag[0].canPlayType('application/vnd.apple.mpegurl') != ''){
                    result = true;
                    this.debug('HLS supported');
                } else {
                    this.debug('HTML5 supported, but no HLS');
                    vidtag.remove();
                }
            } catch(e) {
                this.debug('HTML5 error:', e);
                result = false;
            }
            return result;
        },
        doEmbed: function(data){
            var self = this;
            var embed_fn = null;
            if (typeof(data) == 'string'){
                data = {'streamSrc':data};
            }
    /*
            if (typeof(data.container.jquery) == 'undefined'){
                data.container = $(data.container);
                if (data.container.length == 0){
                    data.container = $("#" + data.container);
                }
            }
    */
            if (typeof(data.container) == 'undefined' || data.container == null){
                data.container = $("body");
            }
            data = self.embedData(data);
            if (!data.size){
                self.calcPlayerSize(data);
                self.debug('calculated player size: ', data.size);
            }
            data.container.data('embedData', data);
            self.debug('embedding now. data: ', data);
            embed_fn = self['doEmbed_' + data.embed_method];
            return embed_fn(data);
        },
        doEmbed_auto: function(data){
            var self = playerEmbedder,
                hlsSupported = self.testHLSSupport(data),
                embed_fn;

            if (hlsSupported){
                data.embed_method = self.html5_embed_method;
                embed_fn = self['doEmbed_' + data.embed_method];
                data = embed_fn(data);
            } else {
                data.embed_method = 'strobe';
                data = self.doEmbed_strobe(data);
            }
            return data;
        },
        doEmbed_html5: function(data){
            var self = playerEmbedder;
            var vidtag = $("video", data.container);
            if (vidtag.length == 0){
                vidtag = $('<video></video>');
                data.container.append(vidtag);
            }
            vidtag.attr('id', data.playerId);
            if (data.sizeWithContainer == true){
                data.size = ['100%', '100%'];
                data.sizeByCSS = true;
            }
            vidtag.attr('width', data.size[0]);
            vidtag.attr('height', data.size[1]);
            self.addPlayerClasses(vidtag, data);
            vidtag[0].controls = true;
            vidtag.append('<source src="URL" type="application/vnd.apple.mpegurl">'.replace('URL', data.streamSrc.hls_url));
            data.player = vidtag;
            fbdiv = self.buildFallbackContent(data);
            if (data.isAndroid){
                data.container.parent().append(fbdiv);
            }
            data.container.trigger('player_embed_complete');
            return data;
        },
        doEmbed_videojs: function(data){
            var self = playerEmbedder;
            $("body").one('player_embedder_sources_loaded', function(){
                var vidtag = $("video", data.container);
                var opts = {
                    'controls': true,
                    'autoplay': true,
                    'width':data.size[0],
                    'height':data.size[1],
                    'nativeControlsForTouch': false,
                };
                if (vidtag.length == 0){
                    vidtag = $('<video></video>');
                    data.container.append(vidtag);
                }
                self.addPlayerClasses(vidtag, data);
                vidtag.addClass('video-js vjs-default-skin');
                vidtag.attr('id', data.playerId);
                vidtag.append('<source src="URL" type="application/vnd.apple.mpegurl">'.replace('URL', data.streamSrc.hls_url));
                videojs(data.playerId, opts, function(){
                    data.player = this;
                    data.container.trigger('player_embed_complete');
                });
            });
            self.loadSources('videojs');
            return data
        },
        doEmbed_strobe: function(data){
            var self = playerEmbedder,
                embedDataKeys = ['swf', 'id', 'width', 'height', 'minimumFlashPlayerVersion', 'expressInstallSwfUrl'],
                embedData = [],
                flashVars = {
                    'width': data.size[0],
                    'height': data.size[1],
                    'src': data.streamSrc.hds_url,
                    'autoPlay': true,
                    'loop': false,
                    'controlBarMode': 'docked',
                    'poster': '',
                    'swf': data.swfUrl,
                    'expressInstallSwfUrl':data.expressInstallSwfUrl,
                    'minimumFlashPlayerVersion': '9',
                    'javascriptCallbackFunction': 'playerEmbedder.strobeCallback',
                },
                params = {
                    'allowFullScreen': 'true',
                    'wmode':'direct',
                },
                attrs = {
                    'id': data.playerId,
                    'name': data.playerId,
                },
                embedCallback = function(event){
                    if (event.success){
                        data.player = $("#" + event.id);
                    }
                    data.container.trigger('player_embed_complete');
                };
                embedStatic = function(playerWrapper){
                    self.debug('embedding using static method (PS3)');
                    var player = $('<object classid="clsid:D27CDB6E-AE6D-11cf-96B8-444553540000"></object>'),
                        innerObj = $('<object type="application/x-shockwave-flash"></object>');
                    player.attr({'id': data.playerId, 'width': data.size[0], 'height': data.size[1]});
                    params.movie = flashVars.swf;
                    params.flashvars = flashVars;
                    function buildParams($objElem){
                        $.each(params, function(key, val){
                            if (key == 'flashvars'){
                                val = $.param(val);
                            } else {
                                val = val.toString();
                            }
                            $objElem.append('<param name="KEY" value="VAL" />'.replace('KEY', key).replace('VAL', val));
                        });
                    };
                    buildParams(player);
                    innerObj.attr({'data':flashVars.swf, 'width':data.size[0], 'height':data.size[1]});
                    player.append(innerObj);
                    buildParams(innerObj);
                    innerObj.append(self.buildFallbackContent(data));
                    playerWrapper.append(player);
                    data.container.append(playerWrapper);
                    self.debug('static content built... registering with swfobject');
                    try {
                        swfobject.registerObject(data.playerId, flashVars.minimumFlashPlayerVersion);
                    } catch(e) {
                        self.debug('swfobject error: ', e);
                    }
                },
                embedDynamic = function(playerWrapper){
                    self.debug('embedding using dynamic method');
                    var player = $('<div></div>');
                    player.attr('id', data.playerId);
                    player.append(self.buildFallbackContent(data));
                    playerWrapper.append(player);
                    data.container.append(playerWrapper);
                    try {
                        swfobject.embedSWF.apply(swfobject.embedSWF, embedData);
                    } catch(e) {
                        self.debug('swfobject error: ', e);
                    }
                };
            $.each(embedDataKeys, function(i, key){
                var val = flashVars[key];
                if (typeof(val) == 'undefined'){
                    val = attrs[key];
                }
                embedData.push(val);
            });
            embedData.push(flashVars, params, attrs, embedCallback);
            $("body").one('player_embedder_sources_loaded', function(){
                self.debug('beginning swfobject embed');
                var playerWrapper = $('<div id="ID-wrapper"></div>'.replace('ID', data.playerId)),
                    flashVer,
                    flashVerStr = [];
                self.debug('testing Flash version...');
                try {
                    flashVer = swfobject.getFlashPlayerVersion();
                } catch(e) {
                    self.debug('Flash detection error: ', e);
                    flashVer = null;
                }
                if (flashVer){
                    $.each(['major', 'minor', 'release'], function(i, n){
                        flashVerStr.push(flashVer[n].toString());
                    });
                    flashVerStr = flashVerStr.join('.');
                    self.debug('Flash version: ', flashVerStr);
                }
                self.addPlayerClasses(playerWrapper, data);
                if (navigator.userAgent.search('PLAYSTATION') != -1){
                    embedStatic(playerWrapper);
                } else {
                    embedDynamic(playerWrapper);
                }
            });
            self.debug('loading strobe sources');
            self.loadSources('strobe');
            return data;
        },
        doResize: function(container, newSize){
            var self = this;
            var data = container.data('embedData');
            var resizeFn = playerEmbedder['doResize_' + data.embed_method];
            if (data.sizeByCSS == true){
                return;
            }
            if (!data.player){
                return;
            }
            if (!newSize){
                hasChanged = self.calcPlayerSize(data);
                if (!hasChanged){
                    return;
                }
            } else {
                if (data.size[0] == newSize[0] && data.size[1] == newSize[1]){
                    return;
                }
                data.size = newSize;
            }
            resizeFn(container, data);
        },
        doResize_html5: function(data){
            data.player.width(data.size[0]);
            data.player.height(data.size[1]);
        },
        doResize_videojs: function(data){
            data.player.width(data.size[0]);
            data.player.height(data.size[1]);
        },
        doResize_strobe: function(data){
            // need to look at api docs
        },
        calcPlayerSize: function(data){
            if (data.sizeByCSS == true){
                return false;
            }
            function getMaxWidth(){
                var width = data.container.innerWidth();
                if (width > data.maxWidth){
                    width = data.maxWidth;
                }
                return width;
            }
            var complete = null;
            var hasChanged = false;
            var x = getMaxWidth();
            var xMin = x * 0.5;
            var y = null;
            var ratio = data.aspect_ratio[0] / data.aspect_ratio[1];
            if (data.sizeWithContainer == true){
                x = data.container.innerWidth();
                y = data.container.innerHeight();
                if (data.size){
                    if (data.size[0] == x || data.size[1] == y){
                        return false;
                    }
                    data.size[0] = x;
                    data.size[1] = y;
                    return true;
                } else {
                    data.size = [x, y]
                    return true;
                }
            }
            if (data.size){
                // size hasn't changed so don't waste time
                if (x == data.size[0]){
                    return false;
                }
            }
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
                    x = getMaxWidth();
                    y = x / ratio;
                    y = Math.floor(y);
                    break;
                }
            }
            if (!data.size){
                data.size = [x, y];
                hasChanged = true;
            } else {
                if (data.size[0] != x){
                    data.size[0] = x;
                    hasChanged = true;
                }
                if (data.size[1] != y){
                    data.size[1] = y;
                    hasChanged = true;
                }
            }
            return hasChanged;
        },
    };

    playerEmbedder.strobeCallback = function(id, eventName, updatedProperties){
        playerEmbedder.debug('strobe callback: ', id, eventName, updatedProperties);
    };
    window.playerEmbedder = playerEmbedder;
    $(document).trigger('playerEmbedderReady');
})(jQuery);
