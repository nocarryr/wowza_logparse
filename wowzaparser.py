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
        super(WowzaEntry, self).__init__(**kwargs)
    @property
    def dt(self):
        return self.indexed_datetime
    def dt_to_string(self):
        return self.dt.strftime(self._datetime_fmt_str)
    def get_dict(self):
        d = super(WowzaEntry, self).get_dict()
        d['id'] = self.dt_to_string()
        return d
        
class Session(object):
    def __init__(self, **kwargs):
        self.start_entry = kwargs.get('start_entry')
        self.parser = kwargs.get('parser')
        self.id = self.start_entry.fields['c-client-id']
        self.entries = []
        self.is_complete = False
    def process_entry(self, entry):
        if self.is_complete:
            return False
        if entry.fields['c-client-id'] == self.id:
            if entry.fields['x-event'] == 'disconnect':
                self.end_entry = entry
                self.is_complete = True
                return False
            self.entries.append(entry)
        return True
    def get_dict(self):
        return {'id':self.id, 'entry_ids':[e.dt_to_string() for e in self.entries]}
        #return {'id':self.id, 'entry_ids':[e.id for e in self.entries.values()]}
        
class WowzaLogParser(logfileparser.W3CExtendedLogfileParser):
    entry_class = WowzaEntry
    def __init__(self, **kwargs):
        kwargs.setdefault('delimiter', 'tab')
        super(WowzaLogParser, self).__init__(**kwargs)
        self.enable_sessions = kwargs.get('enable_sessions', True)
        self.use_utc = kwargs.get('use_utc', True)
        self.sessions = []
    def parse_file(self, **kwargs):
        super(WowzaLogParser, self).parse_file(**kwargs)
        if self.enable_sessions:
            self.build_sessions()
#    def do_parse(self, **kwargs):
#        d = super(WowzaLogParser, self).do_parse(**kwargs)
#        by_dt = {}
#        td = datetime.timedelta(microseconds=1)
#        use_utc = self.use_utc
#        for i in sorted(d['entries'].keys()):
#            e = d['entries'][i]
#            e.dt += td
#            while e.dt in by_dt:
#                e.dt += td
#            if use_utc:
#                e.id = e.dt
#            else:
#                e.id = e.datetime
#            by_dt[e.id] = e
#        d['entries'] = by_dt
#        return d
    def build_entry(self, validate=False, **kwargs):
        e = super(WowzaLogParser, self).build_entry(validate, **kwargs)
        if not e:
            return e
        if getattr(e, 'dt', None) is None and 'field_names' in kwargs:
            print self.filename, kwargs['id'], kwargs['field_names']
        return e
    def build_sessions(self):
        sessions = self.sessions
        sessions_to_process = set()
        to_remove = set()
        by_dt = self.parsed['entries_by_dt']
        for e in by_dt.iter_flat():
            for s in sessions_to_process:
                r = s.process_entry(e)
                if r is False:
                    to_remove.add(s)
            for s in to_remove:
                sessions_to_process.discard(s)
            to_remove.clear()
            if e.fields['x-event'] != 'connect':
                continue
            cat = e.fields['x-category']
            if cat == 'session' or cat == 'cupertino':
                s = Session(start_entry=e, parser=self)
                #d[s.id] = s
                sessions.append(s)
                sessions_to_process.add(s)
    def get_dict(self):
        d = super(WowzaLogParser, self).get_dict()
        sessions = self.sessions
        #keys = sessions.keys()
        d['sessions'] = dict(zip([s.id for s in sessions], [s.get_dict() for s in sessions]))
        return d
