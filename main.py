import sys
import os.path
import argparse
import tempfile
import urllib
import urllib2
import datetime
import threading

from nomadic_recording_lib.Bases import BaseObject, logfileparser

from wowzaparser import WowzaLogParser, parse_filename_dt

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
    #print 'recv: ', s
    f.close()
    fd, filename = tempfile.mkstemp()
    tf = os.fdopen(fd, 'w')
    tf.write(s)
    tf.close()
    return filename




                
#parser = WowzaLogParser()
#parser = logfileparser.W3CExtendedLogfileParser(delimiter='tab')
def build_parser(filename, delete_file=False, **kwargs):
    kwargs.setdefault('delimiter', 'tab')
    parser = WowzaLogParser(**kwargs)
    parser.filename = filename
    if delete_file:
        os.remove(filename)
    return parser
    
#print parser.parsed['fields_by_key']
#print parser.sorted
#print str(parser.delimiter)


def run_gtk(**kwargs):
    from gtkui import run
    run(**kwargs)
    
if __name__ == '__main__':
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
    parser = build_parser(o['file'], DELETE_FILE)
    run_gtk(parser=parser)
    
