import os.path
import datetime
import threading
from Bases import BaseObject, logfileparser

b = BaseObject()
b.GLOBAL_CONFIG['app_name'] = 'wowza-logparse'
b.GLOBAL_CONFIG['app_id'] = 'wowza-logparse.app'

class WowzaLogParser(logfileparser.W3CExtendedLogfileParser):
    def __init__(self, **kwargs):
        kwargs.setdefault('delimiter', 'tab')
        super(WowzaLogParser, self).__init__(**kwargs)
    def do_sort(self, parsed):
        d = {}
        dt_fmt = '%Y-%m-%d %H:%M:%S'
        for field_index, fields in parsed['fields_by_line'].iteritems():
            #print field_index, fields
            dtstr = ' '.join([fields['date'], fields['time']])
            dt = datetime.datetime.strptime(dtstr, dt_fmt)
            fields = fields.copy()
            fields['datetime'] = dt
            d[field_index] = fields
        return d
                
#parser = WowzaLogParser()
parser = logfileparser.W3CExtendedLogfileParser(delimiter='tab')
#parser = logfileparser.W3CExtendedLogfileRollingParser(delimiter='tab')
path = os.getcwd()
parser.filename = os.path.join(path, 'logs', 'wowzamediaserver_access.log')
#print parser.parsed['fields_by_key']
#print parser.sorted
#print str(parser.delimiter)

def run_gtk(**kwargs):
    from gtkui import run
    run(**kwargs)
    
run_gtk(parser=parser)
