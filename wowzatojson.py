import os.path
import datetime
import json

from Bases import BaseObject, Config
from wowzaparser import WowzaEntry, WowzaLogParser

b = BaseObject()
b.GLOBAL_CONFIG['app_name'] = 'wowza-json'

def datetime_to_string(dt):
    return dt.strftime(WowzaEntry._datetime_fmt_str)
def string_to_datetime(s):
    return datetime.datetime.strptime(WowzaEntry._datetime_fmt_str)
    
class WowzaToJson(BaseObject, Config):
    _confsection = 'LOGFILE_LOCATIONS'
    def __init__(self, **kwargs):
        BaseObject.__init__(self, **kwargs)
        Config.__init__(self, **kwargs)
        self.log_source = os.path.expanduser(self.get_conf('log_source', '~/wmslogs/source'))
        self.output_path = os.path.expanduser(self.get_conf('output_path', '~/wmslogs/json'))
        self.log_names = self.get_conf('log_names', ['access', 'error', 'stats'])
        for log_name in self.log_names:
            self.process_log(log_name=log_name)
    def sort_logfiles(self, **kwargs):
        log_name = kwargs.get('log_name')
        base_dir = self.log_source
        filenames = []
        fn_by_dt = {}
        for fn in os.listdir(basedir):
            if log_name not in fn:
                continue
            filenames.append(fn)
            ts = os.stat(os.path.join(basedir, fn)).st_ctime
            dt = datetime.datetime.fromtimestamp(ts)
            fn_by_dt[dt] = fn
        filenames.sort()
        filenames.reverse()
        filenames.remove(log_name)
        filenames = [log_name] + filenames
        return filenames, fn_by_dt
    def process_log(self, **kwargs):
        existing = self.parse_json(**kwargs)
        if existing is False:
            existing = {'entries':{}}
        dt_list = [string_to_datetime(key) for key in existing['entries'].keys()]
        if len(dt_list):
            last_dt = max(dt_list)
        else:
            last_dt = datetime.datetime(1970, 1, 1)
        filenames, fn_by_dt = self.sort_logfiles(**kwargs)
        new_fn_dt = sorted(fn_by_dt.keys())
        for dt in new_fn_dt[:]:
            if dt < last_dt:
                new_fn_dt.remove(dt)
        for dt in new_fn_dt:
            fn = fn_by_dt[dt]
            p = WowzaLogParser()
            p.filename = fn
            for key, val in p.get_dict().iteritems():
                if key not in existing:
                    existing[key] = {}
                existing[key].update(val)
        kwargs['data'] = existing
        self.write_json(**kwargs)
    def build_filename(self, **kwargs):
        log_name = kwargs.get('log_name')
        fn = '%s.json' % (os.path.join(self.output_path, log_name))
        return fn
    def parse_json(self, **kwargs):
        fn = self.build_filename(**kwargs)
        if not os.path.exists(fn):
            return False
        f = open(fn, 'r')
        d = False
        try:
            d = json.load(f)
        finally:
            f.close()
        return d
    def write_json(self, **kwargs):
        fn = self.build_filename(**kwargs)
        data = kwargs.get('data')
        f = open(fn, 'w')
        try:
            json.dump(data)
        finally:
            f.close()
        
if __name__ == '__main__':
    wj = WowzaToJson()
