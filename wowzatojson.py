import sys
import os.path
import datetime
import traceback
import json
import gc

from Bases import BaseObject, Config
from wowzaparser import WowzaEntry, WowzaLogParser

b = BaseObject()
b.GLOBAL_CONFIG['app_name'] = 'wowza-json'

DT_FMT_STR = WowzaEntry._datetime_fmt_str
DT_JSON_STR = '<datetime>'
def datetime_to_string(dt):
    return dt.strftime(DT_JSON_STR + DT_FMT_STR)
def string_to_datetime(s):
    return datetime.datetime.strptime(DT_JSON_STR + DT_FMT_STR)
class Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return datetime_to_string(obj)
        return json.JSONEncoder.default(obj)
    def iterencode(self, obj, _one_shot=False):
        if isinstance(obj, dict):
            newdict = obj.copy()
            changed = False
            for key in newdict.keys()[:]:
                if not isinstance(key, datetime.datetime):
                    continue
                newkey = datetime_to_string(key)
                print 'converting dtkey %s to "%s"' % (key, newkey)
                changed = True
                val = newdict[key]
                newdict[newkey] = val
                del newdict[key]
            if changed:
                obj = newdict
        return json.JSONEncoder.iterencode(self, obj, _one_shot)
class Decoder(json.JSONDecoder):
    def __init__(self, **kwargs):
        kwargs['object_pairs_hook'] = self._look_for_dt
        json.JSONDecoder.__init__(self, **kwargs)
    def _look_for_dt(self, parsed):
        for key in parsed.keys()[:]:
            val = parsed[key]
            newkey = None
            newval = None
            if isinstance(key, basestring) and DT_JSON_STR in key:
                newkey = string_to_datetime(key)
            if isinstance(val, basestring) and DT_JSON_STR in val:
                newval = string_to_datetime(val)
            if newval is not None:
                if newkey is None:
                    parsed[key] = newval
                else:
                    val = newval
            if newkey is not None:
                parsed[newkey] = val
                del parsed[key]
        return parsed
    
class WowzaToJson(BaseObject, Config):
    _confsection = 'LOGFILE_LOCATIONS'
    _jsonfile_dt_fmt_str = '_%Y-%m'
    def __init__(self, **kwargs):
        BaseObject.__init__(self, **kwargs)
        Config.__init__(self, **kwargs)
        self.log_source = os.path.expanduser(self.get_conf('log_source', '~/wmslogs/source'))
        self.output_path = os.path.expanduser(self.get_conf('output_path', '~/wmslogs/json'))
        self.log_names = self.get_conf('log_names', ['access', 'stats'])
        for log_name in self.log_names:
            self.process_log(log_name=log_name)
    def sort_logfiles(self, **kwargs):
        log_name = kwargs.get('log_name')
        base_dir = kwargs.get('base_dir', self.log_source)
        dt_parse_str = kwargs.get('dt_parse_str')
        def parse_dt_stat(fn):
            ts = os.stat(fn).st_mtime
            return datetime.datetime.fromtimestamp(ts)
        def parse_dt_fmtstr(fn):
            fn = os.path.splitext(os.path.basename(fn))[0]
            dtstr = fn.split(log_name)[1]
            dt = datetime.datetime.strptime(dt_parse_str)
            return dt
        if dt_parse_str is None:
            parse_dt = parse_dt_stat
        else:
            parse_dt = parse_dt_fmtstr
        filenames = []
        fn_by_dt = {}
        for fn in os.listdir(base_dir):
            if log_name not in fn:
                continue
            full_fn = os.path.join(base_dir, fn)
            filenames.append(fn)
            dt = parse_dt(full_fn)
            fn_by_dt[dt] = full_fn
        filenames.sort()
        filenames.reverse()
        #filenames.remove(log_name)
        #filenames = [log_name] + filenames
        return filenames, fn_by_dt
    def find_most_recent_file(self, **kwargs):
        filenames, fn_by_dt = self.sort_logfiles(**kwargs)
        if not len(fn_by_dt):
            return False
        dt = max(fn_by_dt.keys())
        return dt, fn_by_dt[dt]
    def process_log(self, **kwargs):
        log_name = kwargs.get('log_name')
        last_js_dt = self.find_most_recent_file(log_name=log_name, 
                                                base_dir=self.output_path, 
                                                dt_parse_str=self._jsonfile_dt_fmt_str)
        if last_js_dt is False:
            existing = {'entries':{}}
        else:
            existing = self.parse_json(filename=last_js_dt[1])
        #dt_list = [string_to_datetime(key) for key in existing['entries'].keys()]
        dt_list = existing['entries'].keys()
        if len(dt_list):
            last_dt = max(dt_list)
        else:
            last_dt = datetime.datetime(1970, 1, 1)
        filenames, fn_by_dt = self.sort_logfiles(**kwargs)
        new_fn_dt = sorted(fn_by_dt.keys())
        print new_fn_dt
        for dt in new_fn_dt[:]:
            if dt < last_dt:
                new_fn_dt.remove(dt)
        print new_fn_dt
        current_month = min(new_fn_dt).month
        print current_month
        for dt in new_fn_dt:
            if dt.month != current_month:
                existing = self.parse_json(log_name=log_name, 
                                           base_dir=self.output_path, 
                                           dt=dt)
                if existing is False:
                    existing = {'entries':{}}
                print 'new month %s, old was %s' % (dt.month, current_month)
                current_month = dt.month
            fn = fn_by_dt[dt]
            print 'processing file %s' % (os.path.basename(fn))
            p = WowzaLogParser()
            p.filename = fn
            for key, val in p.get_dict().iteritems():
                if key not in existing:
                    existing[key] = {}
                existing[key].update(val.copy())
            p = None
            kwargs['data'] = existing
            kwargs['dt'] = dt
            self.write_json(**kwargs)
            gc.collect()
        
    def build_filename(self, **kwargs):
        log_name = kwargs.get('log_name')
        dt = kwargs.get('dt')
        if dt is not None:
            dtstr = dt.strftime(self._jsonfile_dt_fmt_str)
        else:
            dtstr = '0'
        fn = '%s%s.json' % (log_name, dtstr)
        fn = os.path.join(self.output_path, fn)
        #fn = '%s.json' % (os.path.join(self.output_path, log_name))
        return fn
    def parse_json(self, **kwargs):
        fn = kwargs.get('filename')
        if fn is None:
            fn = self.build_filename(**kwargs)
        if not os.path.exists(fn):
            return False
        f = open(fn, 'r')
        d = False
        try:
            d = json.load(f, cls=Decoder)
        finally:
            f.close()
        return d
    def write_json(self, **kwargs):
        fn = self.build_filename(**kwargs)
        print 'writing to file %s' % (fn)
        data = kwargs.get('data')
        f = open(fn, 'w')
        try:
            json.dump(data, f, cls=Encoder)
        except:
            traceback.print_exc()
            #print data
            sys.exit(0)
        finally:
            f.close()

if __name__ == '__main__':
    wj = WowzaToJson()
