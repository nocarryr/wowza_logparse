import traceback
import datetime

from Bases import logfileparser

LOGFILE_DATETIME_FMT_STR = '%Y-%m-%d %H:%M:%S.%f'

def parse_filename_dt(filename):
    if 'log.' in filename:
        filename = filename.split('log.')[1]
    filename += ' 11:59:59.99999'
    dt = datetime.datetime.strptime(filename, LOGFILE_DATETIME_FMT_STR)
    return dt
    
    
class WowzaEntry(logfileparser.W3CExtendedLogEntry):
    _datetime_fmt_str = '%Y-%m-%d %H:%M:%S.%f %z'
    def __init__(self, **kwargs):
        self._dt = None
        super(WowzaEntry, self).__init__(**kwargs)
        dt = self.dt
    @property
    def dt(self):
        dtutc = self.datetime_utc
        if dtutc is not None:
            return dtutc
        return self.datetime
    @dt.setter
    def dt(self, dt):
        if self.is_utc:
            self.datetime_utc = self.datetime = dt
        elif self.datetime_utc is not None:
            self.datetime_utc = dt
            self.datetime = self.tzinfo.normalize(dt)
        else:
            self.datetime = dt
    def dt_to_string(self):
        return self.dt.strftime(self._datetime_fmt_str)
    def get_dict(self):
        d = super(WowzaEntry, self).get_dict()
        d['id'] = self.dt_to_string()
        return d
        
class Session(object):
    def __init__(self, **kwargs):
        self.start_entry = kwargs.get('start_entry')
        start_index = kwargs.get('start_index')
        self.parser = kwargs.get('parser')
        self.id = self.start_entry.fields['c-client-id']
        d = self.parser.parsed['entries']
        keys = sorted(d.keys())
        self.entries = {}
        for key in keys[start_index:]:
            e = d[key]
            if e.fields['c-client-id'] != self.id:
                continue
            if e.fields['x-event'] == 'disconnect':
                self.end_entry = e
                break
            self.entries[e.id] = e
    def get_dict(self):
        return {'id':self.id, 'entry_ids':[e.dt_to_string() for e in self.entries.values()]}
        #return {'id':self.id, 'entry_ids':[e.id for e in self.entries.values()]}
        
class WowzaLogParser(logfileparser.W3CExtendedLogfileParser):
    entry_class = WowzaEntry
    def __init__(self, **kwargs):
        kwargs.setdefault('delimiter', 'tab')
        super(WowzaLogParser, self).__init__(**kwargs)
        self.use_utc = kwargs.get('use_utc', True)
        self.sessions = []
    def parse_file(self, **kwargs):
        super(WowzaLogParser, self).parse_file(**kwargs)
        self.build_sessions()
    def do_parse(self, **kwargs):
        d = super(WowzaLogParser, self).do_parse(**kwargs)
        by_dt = {}
        td = datetime.timedelta(microseconds=1)
        use_utc = self.use_utc
        for i in sorted(d['entries'].keys()):
            e = d['entries'][i]
            e.dt += td
            while e.dt in by_dt:
                e.dt += td
            if use_utc:
                e.id = e.dt
            else:
                e.id = e.datetime
            by_dt[e.id] = e
        d['entries'] = by_dt
        return d
    def build_entry(self, **kwargs):
        e = super(WowzaLogParser, self).build_entry(**kwargs)
        if getattr(e, 'dt', None) is None and 'field_names' in kwargs:
            print self.filename, kwargs['id'], kwargs['field_names']
        return e
    def build_sessions(self):
        sessions = self.sessions
        for i, key in enumerate(sorted(self.parsed['entries'].keys())):
            e = self.parsed['entries'][key]
            if e.fields['x-event'] != 'connect':
                continue
            cat = e.fields['x-category']
            if cat == 'session' or cat == 'cupertino':
                s = Session(start_entry=e, start_index=i, parser=self)
                #d[s.id] = s
                sessions.append(s)
    def get_dict(self):
        d = super(WowzaLogParser, self).get_dict()
        sessions = self.sessions
        #keys = sessions.keys()
        d['sessions'] = dict(zip([s.id for s in sessions], [s.get_dict() for s in sessions]))
        return d
