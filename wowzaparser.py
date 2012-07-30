import datetime

from Bases import logfileparser

class WowzaEntry(logfileparser.DelimitedLogEntry):
    def __init__(self, **kwargs):
        super(WowzaEntry, self).__init__(**kwargs)
        if None not in [self.fields.get(key) for key in ['date', 'time']]:
            ymd = [int(s) for s in self.fields['date'].split('-')]
            d = datetime.date(*ymd)
            #d = datetime.date.strptime(self.fields['date'], '%Y-%m-%d')
            hms = [int(s) for s in self.fields['time'].split(':')]
            #hms.append(1)
            t = datetime.time(*hms)
            #t = datetime.time.strptime(self.fields['time'], '%H:%M:%S')
            self.dt = datetime.datetime.combine(d, t)
        
        
class WowzaLogParser(logfileparser.W3CExtendedLogfileParser):
    entry_class = WowzaEntry
    def do_parse(self, **kwargs):
        d = super(WowzaLogParser, self).do_parse(**kwargs)
        by_dt = {}
        td = datetime.timedelta(microseconds=1)
        for i in sorted(d['entries'].keys()):
            e = d['entries'][i]
            while e.dt in by_dt:
                e.dt += td
            by_dt[e.dt] = e
        d['entries'] = by_dt
        return d
