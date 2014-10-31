#!/usr/bin/env python


import cgi
import cgitb
cgitb.enable()
import os.path
import pwd
import datetime
import gzip
import tarfile
import tempfile
import StringIO
from ConfigParser import ConfigParser

logfiledata = {'wowza': {'root':'/usr/local/WowzaMediaServer/logs/',
                         'filename_fmt':'wowzamediaserver_%s.log',
                         'filenames':['access', 'error', 'stats']},
               'apache':{'root':'/var/log/apache2/',
                         'filename_fmt':'%s.log',
                         'filenames':['access','error']}}
def parse_conf(fn):
    def parse_ini(fn):
        p = ConfigParser()
        p.read(fn)
        d = {}
        for key in p.sections():
            items = p.items(key)
            itemdict = {}
            for optkey, optval in items:
                if ',' in optval:
                    optval = [v.strip() for v in optval.split(',')]
                itemdict[optkey] = optval
            d[key] = itemdict
        return d
    parsed = parse_ini(fn)
    for lkey, lval in parsed.iteritems():
        d = logfiledata.get(lkey)
        if lkey not in logfiledata:
            logfiledata[lkey] = {}
        logfiledata[lkey].update(lval)
        
def write_conf(fn, conftype='INI'):
    def write_ini(fn, d):
        p = ConfigParser()
        for lkey, lval in d.iteritems():
            p.add_section(lkey)
            for optkey, optval in lval.iteritems():
                if isinstance(optval, list):
                    optval = ','.join(optval)
                p.set(lkey, optkey, optval)
        f = open(fn, 'wb')
        p.write(f)
        f.close()
    if conftype == 'INI':
        write_ini(fn, logfiledata)
    
conf_fn = '.getlog.conf'
conf_paths = [pwd.getpwuid(os.stat(os.getcwd()).st_uid).pw_dir, 
              pwd.getpwuid(os.geteuid()).pw_dir,
              '~', 
              os.getcwd()]
conf_write_path = None
conf_parse_path = None
for conf_path in conf_paths:
    conf_path = os.path.expanduser(conf_path)
    if not os.access(conf_path, os.F_OK | os.R_OK | os.W_OK):
        continue
    full_fn = os.path.join(conf_path, conf_fn)
    if os.path.exists(full_fn):
        parse_conf(full_fn)
        conf_parse_path = full_fn
        conf_write_path = False
        break
    elif conf_write_path is None:
        conf_write_path = full_fn
if conf_write_path:
    write_conf(conf_write_path)

def wrapdochtml(body, head=None):
    if head is None:
        head = ''
    return '<html>\n<head>%s</head>\n<body>\n%s\n</body>\n</html>' % (head, body)

#def get_logfiles(app, filetype, wraphtml, getall):
def get_logfiles(**kwargs):
    app = kwargs.get('app')
    filetype = kwargs.get('file')
    wraphtml = kwargs.get('wraphtml')
    getall = kwargs.get('getall')
    datestart = kwargs.get('datestart')
    dateend = kwargs.get('dateend')
    basepath, basefn = os.path.split(findlogfilename(app, filetype))
    if getall:
        filenames, fn_by_dt = find_all_logfiles(**kwargs)
        if dateend is not None:
            filenames = []
            for dt in reversed(sorted(fn_by_dt.keys())):
                if dt.date() < dateend.date():
                    #print 'date end: fn=%s, date=%s' % (fn_by_dt[dt], dt.date())
                    break
                if dt.date() >= datestart.date():
                    #print 'before datestart: fn=%s, date=%s' % (fn_by_dt[dt],  dt.date())
                    continue
                #print 'added fn=%s, date=%s' % (fn_by_dt[dt], dt.date())
                filenames.append(fn_by_dt[dt])
        logs = []
        for i, fn in enumerate(filenames):
            fullpath = os.path.join(basepath, fn)
            s = getlogfile(fullpath)
            if wraphtml:
                s = wraploghtml(s, '%s-%s' % (filetype, i))
            logs.append({'filename':fn, 
                         'stats':os.stat(fullpath), 
                         'contents':s})
        return logs, basefn
        outfile = build_archive(logs)
        #outfile = logs
        outfilename = '.'.join([basefn, 'tar.gz'])
        return outfile, outfilename
    filename = findlogfilename(app, filetype)
    s = getlogfile(filename)
    if wraphtml:
        s = wraploghtml(s, filetype)
    return s, basefn
        
#def find_all_logfiles(app, filetype):
def find_all_logfiles(**kwargs):
    app = kwargs.get('app')
    filetype = kwargs.get('file')
    filename = findlogfilename(app, filetype)
    basedir, basefn = os.path.split(filename)
    filenames = []
    fn_by_dt = {}
    for fn in os.listdir(basedir):
        if basefn not in fn:
            continue
        filenames.append(fn)
        ts = os.stat(os.path.join(basedir, fn)).st_ctime
        dt = datetime.datetime.fromtimestamp(ts)
        fn_by_dt[dt] = fn
    filenames.sort()
    filenames.reverse()
    filenames.remove(basefn)
    filenames = [basefn] + filenames
    return filenames, fn_by_dt

def findlogfilename(app, filetype):
    data = logfiledata[app]
    filename = os.path.join(data['root'], data['filename_fmt'] % filetype)
    return filename

def getlogfile(filename):
    filename = os.path.expanduser(filename)
    ext = os.path.splitext(filename)[1]
    if ext == '.gz':
        file = gzip.open(filename, 'rb')
    else:
        file = open(filename, 'r')
    s = file.read()
    file.close()
    return s
        
def wraploghtml(logstr, div_id, line_breaks=True):
    if line_breaks:
        logstr = '<br>'.join(logstr.splitlines())
    return '<div id=%s>%s</div>' % (div_id, logstr)

def build_archive(logs):
    fd = tempfile.SpooledTemporaryFile()
    tar = tarfile.open(mode='w:gz', fileobj=fd)
    bufs = []
    for logdata in logs:
        tinf = tarfile.TarInfo(logdata['filename'])
        tinf.mtime = logdata['stat'].st_mtime
        tinf.mode = logdata['stat'].st_mode
        buf = StringIO()
        buf.write(logdata['contents'])
        buf.seek(0)
        bufs.append(buf)
        tinf.size = len(buf.buf)
        tar.addfile(tinf, fileobj=buf)
    tar.close()
    for buf in bufs:
        buf.close()
    fd.seek(0)
    s = fd.read()
    fd.close()
    return s


def parse_to_bool(s):
    if type(s) == bool:
        return s
    return s.lower() in ['true', 'yes']

form = cgi.FieldStorage()
formdefaults = dict(app=None, file=None, wraphtml=True, getall=False, 
                    datestart=None, dateend=None)
formdata = {}
for key, default in formdefaults.iteritems():
    val = form.getfirst(key, default)
    if type(default) == bool:
        val = parse_to_bool(val)
    formdata[key] = val

#logapp = form.getfirst('app', None)
#logfile = form.getfirst('file', None)
#wraphtml = parse_to_bool(form.getfirst('wraphtml', 'true'))
#getall = parse_to_bool(form.getfirst('getall', 'false'))
def parse_datetime(s):
    fmt_str = '%Y%m%d'
    return datetime.datetime.strptime(s, fmt_str)
    
for key in ['datestart', 'dateend']:
    if formdata[key] is not None:
        formdata[key] = parse_datetime(formdata[key])
        formdata['getall'] = True
if formdata['datestart'] is None:
    formdata['datestart'] = datetime.datetime.now()

content_type = 'text/html'
if formdata['getall']:
    formdata['wraphtml'] = False
    #content_type = 'application/x-tar-gz'
if not formdata['wraphtml']:
    content_type = 'text/plain'
    
#logdiv, logfilename = findlogfile(logapp, logfile, wraphtml)
print 'Content-Type: %s' % (content_type)
print

logfileresult, logfilename = get_logfiles(**formdata)
#logfileresult, logfilename = ('blahstuff', 'blahname')

if formdata['wraphtml']:
    body = '<h1>%s</h1>%s' % (logfilename, logfileresult)
    print wrapdochtml(body)
else:
    #print 'Content-Disposition: attachment; filename=%s' % (logfilename)
    #print
    if formdata['getall']:
        #print '# %s' % ([ld['filename'] for ld in logfileresult])
        for logdata in logfileresult:
            print logdata['contents']
    else:
        print logfileresult

