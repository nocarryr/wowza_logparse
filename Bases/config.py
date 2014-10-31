#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# config.py
# Copyright (c) 2010 - 2011 Matthew Reid

import sys
import os
import os.path
import threading
import json
import traceback
import StringIO
from ConfigParser import SafeConfigParser
from urllib2 import urlopen
from urlparse import urlparse
from BaseObject import GLOBAL_CONFIG

#default_conf = os.path.expanduser('~/.openlightingdesigner.conf')
def build_conf_filename():
    cfilename = GLOBAL_CONFIG.get('conf_filename')
    if cfilename:
        return cfilename
    app = GLOBAL_CONFIG.get('app_name')
    if app is None:
        return False
        #app = sys.argv[0].split('.py')[0]
    return os.path.expanduser('~/.%s.conf' % (app))

class ConfigNeededException(Exception):
    def __init__(self, key, obj):
        self.key = key
        self.obj = obj
    def __str__(self):
        return repr({'obj':self.obj, 'key':self.key})

class Config(object):
    ConfigNeededException = ConfigNeededException
    def __init__(self, **kwargs):
        self.init_config_parser(**kwargs)
    def init_config_parser(self, **kwargs):
        conf_data = getattr(self, 'confparser_data', {})
        conf_data.update(kwargs.get('confparser_data', {}))
        if len(conf_data):
            self.__config_object_legacy = False
            conf_type = conf_data.get('confparser_type', 'INI')
            cls = CONFPARSER_TYPES.get(conf_type)
            self._confparser = cls(conf_data=conf_data)
        else:
            self.__config_object_legacy = True
            conf_type = kwargs.get('confparser_type', getattr(self, 'confparser_type', 'INI'))
            cls = CONFPARSER_TYPES.get(conf_type)
            _conf_filename = kwargs.get('_conf_filename', build_conf_filename())
            self._confsection = kwargs.get('confsection', getattr(self.__class__, '_confsection', None))
            self._save_config_file = kwargs.get('_save_config_file', True)
            conf_data = {'filename':_conf_filename, 
                         'section':self._confsection, 
                         'read_only':not self._save_config_file}
            self._confparser = cls(conf_data=conf_data)
        GLOBAL_CONFIG.bind(update=self._CONF_ON_GLOBAL_CONFIG_UPDATE)
    def get_conf(self, key=None, default=None):
        p = getattr(self, '_confparser', None)
        if p is None:
            return default
        return p.get_conf(key, default)
    def update_conf(self, **kwargs):
        p = getattr(self, '_confparser', None)
        if p is None:
            return
        p.update_conf(**kwargs)
    def remove_conf_options(self, options=None):
        p = getattr(self, '_confparser', None)
        if p is None:
            return
        p.remove_conf_options(options)
    def raise_conf_exception(self, key, obj=None):
        if obj is None:
            obj = self
        raise ConfigNeededException(key, obj)
    def _CONF_ON_GLOBAL_CONFIG_UPDATE(self, **kwargs):
        cfilename = build_conf_filename()
        p = getattr(self, '_confparser', None)
        if p is None:
            if not cfilename:
                return
            conf_type = getattr(self, 'confparser_type', 'INI')
            cls = CONFPARSER_TYPES.get(conf_type)
            conf_data = {'filename':cfilename, 
                         'section':self._confsection, 
                         'read_only':not getattr(self, '_save_config_file', True)}
            self._confparser = cls(conf_data=conf_data)
            return
        if cfilename == self._confparser._conf_data.get('filename'):
            return
        self._confparser.set_conf_data({'filename':cfilename})
    
class ConfParserBase(object):
    _conf_data_needed = []
    def __init__(self, **kwargs):
        self.items = {}
        self._conf_data = {}
        self.conf_source = None
        self.set_conf_data(kwargs.get('conf_data', {}))
    @property
    def is_conf_valid(self):
        if self.conf_source is None:
            return False
        return None not in [self._conf_data.get(key) for key in self._conf_data_needed]
    def set_conf_data(self, d):
        self._conf_data.update(d)
        #fn = d.get('filename')
        skwargs = self._conf_data.copy()
        srctype = None
        for key, val in CONF_SOURCE_TYPES.iteritems():
            if skwargs.get(key) is None:
                continue
            srctype = val
        if srctype is None:
            return
        skwargs['type'] = srctype
        #if isinstance(fn, basestring):
        #    skwargs['type'] = FilenameConfSource
        #    skwargs['filename'] = fn
        self.set_conf_source(**skwargs)
    def set_conf_source(self, **kwargs):
        if self.conf_source is not None:
            self.conf_source.close()
            self.conf_source = None
        cls = kwargs.get('type')
        if cls is None:
            return
        kwargs['parser'] = self
        src = cls(**kwargs)
        if src.valid:
            self.conf_source = src
            if src.read_only:
                self._conf_data['read_only'] = True
    def get_conf(self, key=None, default=None):
        items = self.items
        d = self._get_conf_items()
        items.update(d)
        if not items or key and key not in items:
            if key is None:
                default = {}
            return default
        if key is not None:
            return items.get(key, default)
        return items
    def update_conf(self, **kwargs):
        items = self._get_conf_items()
        for key, val in kwargs.iteritems():
            self._do_set_item(key, val)
        if not self._conf_data.get('read_only'):
            try:
                self.write_source()
            except:
                pass
    def remove_conf_options(self, options=None):
        items = self._get_conf_items()
        if options is None:
            options = items.keys()
        for key in options:
            if key not in items:
                continue
            self._do_remove_item(key)
        if not self._conf_data.get('read_only'):
            try:
                self.write_source()
            except:
                pass
    def _get_conf_items(self):
        return self.items
    def read_source(self):
        pass
    def write_source(self):
        pass
    def _do_set_item(self, key, value):
        self.items[key] = value
    def _do_remove_item(self, key):
        if key in self.items:
            del self.items[key]
            
class ConfParserINI(ConfParserBase):
    name = 'INI'
    _conf_data_needed = ['section']
    def __init__(self, **kwargs):
        self._parser = SafeConfigParser()
        super(ConfParserINI, self).__init__(**kwargs)
    def set_conf_data(self, d):
        super(ConfParserINI, self).set_conf_data(d)
        if not self.is_conf_valid:
            return
        self.read_source()
        section = self._conf_data['section']
        if not self._parser.has_section(section):
            self._parser.add_section(section)
    def _unformat_item(self, val):
        dict_chars = '{:}'
        if '__JSON_ENCODED__:' in val:
            val = json.loads(val.split('__JSON_ENCODED__:')[1])
        elif False not in [c in val for c in dict_chars]:
            try:
                d = eval(val)
                val = d
            except:
                pass
        elif ',' in val:
            val = val.split(',')
        return val
    def _format_item(self, val):
        if isinstance(val, list) or isinstance(val, tuple):
            slist = [str(element) for element in val]
            if len(slist) == 1:
                s = slist[0] + ','
            else:
                s = ','.join(slist)
        elif isinstance(val, dict):
            s = '__JSON_ENCODED__:%s' % (json.dumps(val))
        else:
            s = str(val)
        return s
    def _get_conf_items(self):
        if not self.is_conf_valid:
            return super(ConfParserINI, self)._get_conf_items()
        d = self._conf_data
        self.read_source()
        items = dict(self._parser.items(d['section']))
        for key in items.keys()[:]:
            val = self._unformat_item(items[key])
            items[key] = val
        return items
    def _do_set_item(self, key, val):
        val = self._format_item(val)
        self.items[key] = val
        if not self.is_conf_valid:
            return
        section = self._conf_data.get('section')
        if section is None:
            return
        self._parser.set(section, key, val)
    def _do_remove_item(self, key):
        super(ConfParserINI, self)._do_remove_item(key)
        section = self._conf_data.get('section')
        if section is None:
            return
        self._parser.remove_option(section, key)
    def read_source(self):
        if not self.is_conf_valid:
            return
        src = self.conf_source
        src.open('r')
        self._parser.readfp(src.fp)
        src.close()
    def write_source(self):
        if not self.is_conf_valid:
            return
        src = self.conf_source
        src.open('rw')
        self._parser.write(src.fp)
        src.close()
        
conftypes = (ConfParserINI, )
CONFPARSER_TYPES = dict(zip([cls.name for cls in conftypes], conftypes))
del conftypes

class BaseConfSource(object):
    read_only = False
    def __init__(self, **kwargs):
        self._fp_open = threading.Event()
        self._fp_closed = threading.Event()
        self._fp_closed.set()
        self.fp = None
    @property
    def valid(self):
        return self.check_valid()
    def check_valid(self):
        return True
    def build_fp(self, *args, **kwargs):
        pass
    def close_fp(self):
        pass
    def open(self, mode='rw'):
        self._fp_closed.wait()
        self.fp = self.build_fp(mode)
        self._fp_closed.clear()
        self._fp_open.set()
    def close(self):
        if self.fp is not None:
            self.close_fp()
            self.fp = None
        self._fp_open.clear()
        self._fp_closed.set()
    #def __enter__(self):
    #    self.open()
    #def __exit__(self, *args):
    #    self.close()
        
        
class FilenameConfSource(BaseConfSource):
    name = 'filename'
    def __init__(self, **kwargs):
        self.filename = kwargs.get('filename')
        super(FilenameConfSource, self).__init__(**kwargs)
    def check_valid(self):
        b = super(FilenameConfSource, self).check_valid()
        return b and isinstance(self.filename, basestring)
    def build_fp(self, mode):
        if not os.path.exists(self.filename):
            if mode == 'r':
                fp = StringIO.StringIO()
                return fp
            elif mode == 'rw':
                mode = 'w'
        fp = open(self.filename, mode)
        return fp
    def close_fp(self):
        self.fp.close()
        
class URLConfSource(BaseConfSource):
    name = 'url'
    read_only = True
    def __init__(self, **kwargs):
        self.url = kwargs.get('url')
        super(URLConfSource, self).__init__(**kwargs)
    def check_valid(self):
        if not isinstance(self.url, basestring):
            return False
        b = super(URLConfSource, self).check_valid()
        pr = urlparse(self.url)
        return b and pr.netloc != ''
    def build_fp(self):
        fp = urlopen(self.url)
        return fp
    def close_fp(self):
        self.fp.close()
    
srctypes = (FilenameConfSource, URLConfSource)
CONF_SOURCE_TYPES = dict(zip([cls.name for cls in srctypes], srctypes))
del srctypes
