import os.path
import argparse
import tempfile
import urllib
import urllib2
import datetime
import threading
from Bases import BaseObject, logfileparser

b = BaseObject()
b.GLOBAL_CONFIG['app_name'] = 'wowza-logparse'
b.GLOBAL_CONFIG['app_id'] = 'wowza-logparse.app'

def get_file_from_url(url, query=None):
    if query is None:
        query = {}
    querystr = urllib.urlencode(query)
    print 'querystr: ', querystr
    if len(querystr):
        url = '?'.join([url, querystr])
    r = urllib2.Request(url)
    print r.get_full_url()
    f = urllib2.urlopen(r)
    #f = urllib2.urlopen(url, querystr)
    s = f.read()
    print 'recv: ', s
    f.close()
    fd, filename = tempfile.mkstemp()
    tf = os.fdopen(fd, 'w')
    tf.write(s)
    tf.close()
    return filename

p = argparse.ArgumentParser()
p.add_argument('-f', dest='file', help='Log Filename')
p.add_argument('-u', dest='url', help='Log URL')
p.add_argument('-q', dest='query', help='URL Query (key=value)', 
               action='append')
args, remaining = p.parse_known_args()
o = vars(args)

DELETE_FILE = False

def format_query(querystr):
    if ',' in querystr:
        l = [s.strip(' ') for s in querystr.split(',')]
    else:
        l = [querystr]
    d = {}
    for q in l:
        k, v = [s.strip(' ') for s in q.split('=')]
        d[k] = v
    return d

if o['url']:
    query = {}
    if o['query'] is not None:
        for q in o['query']:
            query.update(format_query(q))
            #k, v = [s.strip(' ') for s in q.split('=')]
            #query[k] = v
        print 'query: ', query
    o['file'] = get_file_from_url(o['url'], query)
    DELETE_FILE = True

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
#parser.filename = os.path.join(path, 'logs', 'bigstatslog.log')
parser.filename = o['file']
if DELETE_FILE:
    os.remove(o['file'])
#print parser.parsed['fields_by_key']
#print parser.sorted
#print str(parser.delimiter)

def run_gtk(**kwargs):
    from gtkui import run
    run(**kwargs)
    
run_gtk(parser=parser)
    
