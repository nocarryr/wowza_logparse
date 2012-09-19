import datetime

from Bases import logfileparser

class WowzaEntry(logfileparser.DelimitedLogEntry):
    _datetime_fmt_str = '<datetime>%Y-%y-%d %H:%M:%S.%f'
    def __init__(self, **kwargs):
        super(WowzaEntry, self).__init__(**kwargs)
        if None not in [self.fields.get(key) for key in ['date', 'time']]:
            try:
                ymd = [int(s) for s in self.fields['date'].split('-')]
                d = datetime.date(*ymd)
                #d = datetime.date.strptime(self.fields['date'], '%Y-%m-%d')
                hms = [int(s) for s in self.fields['time'].split(':')]
                #hms.append(1)
                t = datetime.time(*hms)
                #t = datetime.time.strptime(self.fields['time'], '%H:%M:%S')
                self.dt = datetime.datetime.combine(d, t)
            except:
                self.dt = None
    def get_dict(self):
        d = super(WowzaEntry, self).get_dict()
        d['id'] = self.id.strftime(self._datetime_fmt_str)
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
        return {'id':self.id, 'entry_ids':self.entries.keys()}
        
class WowzaLogParser(logfileparser.W3CExtendedLogfileParser):
    entry_class = WowzaEntry
    def __init__(self, **kwargs):
        kwargs.setdefault('delimiter', 'tab')
        super(WowzaLogParser, self).__init__(**kwargs)
        self.sessions = []
    def parse_file(self, **kwargs):
        super(WowzaLogParser, self).parse_file(**kwargs)
        self.build_sessions()
    def do_parse(self, **kwargs):
        d = super(WowzaLogParser, self).do_parse(**kwargs)
        by_dt = {}
        td = datetime.timedelta(microseconds=1)
        for i in sorted(d['entries'].keys()):
            e = d['entries'][i]
            while e.dt in by_dt:
                e.dt += td
            e.id = e.dt
            by_dt[e.id] = e
        d['entries'] = by_dt
        return d
    def build_sessions(self):
        sessions = self.sessions
        for i, key in enumerate(sorted(self.parsed['entries'].keys())):
            e = self.parsed['entries'][key]
            if e.fields['x-category'] != 'session':
                continue
            if e.fields['x-event'] != 'connect':
                continue
            s = Session(start_entry=e, start_index=i, parser=self)
            #d[s.id] = s
            sessions.append(s)
    def get_dict(self):
        d = super(WowzaLogParser, self).get_dict()
        sessions = self.sessions
        #keys = sessions.keys()
        d['sessions'] = [session.get_dict() for session in sessions]
        return d
