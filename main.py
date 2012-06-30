import datetime
import threading
from Bases import logfileparser

class WowzaLogParser(logfileparser.DelimitedFileParser):
    def __init__(self, **kwargs):
        kwargs.setdefault('delimiter', 'tab')
        kwargs.setdefault('header_line_num', 4)
        kwargs.setdefault('line_strip_chars', '#Fields:')
        super(WowzaLogParser, self).__init__(**kwargs)
    def do_sort(self, parsed):
        d = {}
        dt_fmt = '%Y-%m-%d %H:%M:%S'
        for field_index, fields in parsed['fields_by_line'].iteritems():
            print field_index, fields
            dtstr = ' '.join([fields['date'], fields['time']])
            dt = datetime.datetime.strptime(dtstr, dt_fmt)
            d[dt] = fields
        return d
                
parser = WowzaLogParser()
parser.filename = '/home/nocarrier/programs/wowza-logparse/logs/wowzamediaserver_access.log'
#print parser.parsed['fields_by_key']
print parser.sorted
print str(parser.delimiter)
print 'done'

print threading.enumerate()
print parser.fileobj
