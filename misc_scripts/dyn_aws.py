#! /usr/bin/env python

import time
import os.path
import argparse
import urllib2
import logging
logging.basicConfig(filename=os.path.expanduser('~/.dyn_aws.log'), 
                    level=logging.INFO,
                    format='%(asctime)s\t%(levelname)s\t%(message)s')

from boto.route53.connection import Route53Connection

def LOG(*args):
    logging.info(' '.join([str(arg) for arg in args]))

class IPError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return self.value

OPTS = {
    'aws_access_key_id':None,
    'aws_secret_access_key':None,
    'aws_credentials_file':None,
    'zone':None,
    'record':None,
    'value':None,
    'ip_get_url':'http://curlmyip.com', 
    'test_mode':False
}

def get_inet_ip():
    u = urllib2.urlopen(OPTS['ip_get_url'])
    s = u.read()
    u.close()
    s = s.strip()
    if len(s.split('.')) != 4:
        raise IPError('could not find IP address: %s' % (s))
    return s

def load_aws_credentials():
    cfn = OPTS['aws_credentials_file']
    if not cfn:
        return
    with open(os.path.expanduser(cfn), 'r') as f:
        s = f.read()
    for key, val in zip(['aws_access_key_id', 'aws_secret_access_key'], s.splitlines()[:2]):
        val = val.strip()
        OPTS[key] = val
        
def process_opts(opts):
    for key, val in opts.iteritems():
        if val is None:
            continue
        OPTS[key] = val
    load_aws_credentials()
    if OPTS['zone'] not in OPTS['record']:
        OPTS['record'] = '.'.join([OPTS['record'], OPTS['zone']])
    if not OPTS['record'].endswith('.'):
        OPTS['record'] += '.'
    if not OPTS['value']:
        OPTS['value'] = get_inet_ip()

CONNECTION = None
def get_connection():
    global CONNECTION
    if CONNECTION is None:
        keys = ['aws_access_key_id', 'aws_secret_access_key']
        ckwargs = {}
        for key in keys:
            ckwargs[key] = OPTS[key]
        if None in ckwargs.values():
            ckwargs.clear()
        CONNECTION = Route53Connection(**ckwargs)
    return CONNECTION

def update_zone():
    c = get_connection()
    zone = c.get_zone(OPTS['zone'])
    record_name = OPTS['record']
    def wait_for_result(req):
        while req.status == u'PENDING':
            time.sleep(50)
            req.update()
        return True
    def create_record():
        LOG('creating record')
        if OPTS['test_mode']:
            LOG('test only, not really creating record')
            return False
        req = zone.add_record('A', record_name, OPTS['value'])
        result = wait_for_result(req)
        LOG('record creation: %s' % (result))
        return result
    def get_record():
        return zone.find_records(record_name, 'A')
    def get_or_create_record():
        record = get_record()
        if not record:
            create_record()
            record = get_record()
        return record
    def update_record():
        record = get_or_create_record()
        if record is False:
            LOG('record not found or created')
            return False
        if OPTS['value'] in record.resource_records:
            LOG('no update needed')
            return True
        if OPTS['test_mode']:
            LOG('update needed (test only)')
            return
        req = zone.update_record(record, OPTS['value'])
        result = wait_for_result(req)
        LOG('zone update: %s' % (result))
        return result
    return update_record()

def main():
    p = argparse.ArgumentParser()
    for key in OPTS.iterkeys():
        akwargs = {'dest':key}
        if key == 'test_mode':
            akwargs['action'] = 'store_true'
        p.add_argument('--%s' % (key), **akwargs)
    args, remaining = p.parse_known_args()
    o = vars(args)
    process_opts(o)
    if OPTS['test_mode']:
        LOG('options: %s' % (OPTS))
    update_zone()
    
if __name__ == '__main__':
    main()
