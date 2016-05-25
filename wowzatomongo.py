import os
import argparse

import pymongo
from pymongo import MongoClient
from bson import DBRef

from wowzaparser import WowzaLogParser

class Client(object):
    client_conf = dict(
        host='localhost',
        port=27017,
        tz_aware=True,
    )
    database = 'wowzalogs'
    def __init__(self, **kwargs):
        client_conf = kwargs.get('client_conf', self.client_conf)
        db_name = kwargs.get('database', self.database)
        self.client = MongoClient(
            client_conf['host'],
            client_conf['port'],
            tz_aware=client_conf.get('tz_aware', True),
        )
        self.db = self.client[db_name]

class LogFile(object):
    def __init__(self, client, filename):
        self.client = client
        self.db = client.db
        self.filename = filename
        self.parser = WowzaLogParser(enable_sessions=False)
        self.file_coll = self.db.logfiles
        self.base_fn = os.path.basename(filename)
        file_doc = self.file_coll.find_one({'filename':self.base_fn})
        if file_doc is None:
            file_doc = {
                'filename':self.base_fn,
                'parsed':False,
            }
            r = self.file_coll.insert_one(file_doc)
            self.file_id = r.inserted_id
        else:
            self.file_id = file_doc['_id']
        if file_doc['parsed']:
            print('skipping file {}'.format(self.base_fn))
        else:
            print('parsing file {}'.format(self.base_fn))
            self.parser.filename = filename
            added, skipped = self.add_entries()
            print('added {}, skipped {}'.format(added, skipped))
            self.file_coll.update_one(
                {'filename':self.base_fn},
                {'$set':{'parsed':True}})
    def add_entries(self):
        coll = self.db.entries
        coll.create_index([('file_id', pymongo.ASCENDING)])
        coll.create_index([
            ('datetime', pymongo.ASCENDING),
            ('datetime_subindex', pymongo.ASCENDING)])
        num_added = 0
        num_skipped = 0
        by_dt = self.parser.parsed['entries_by_dt']
        for e in by_dt.iter_flat():
            r = self.add_entry(e)
            if r:
                num_added += 1
            else:
                num_skipped += 1
        return num_added, num_skipped
    def add_entry(self, entry):
        coll = self.db.entries
        dt = entry.dt
        dt = dt.replace(microsecond=0)
        doc = {
            'file_id':self.file_id,
            'datetime':dt,
            'datetime_subindex':entry.dt_index,
        }
        existing = coll.find(doc)
        if existing.count():
            #raise Exception('doc {} exists: {}'.format(doc, [_doc for _doc in existing]))
            return False
        doc.update(entry.fields)
        coll.insert_one(doc)
        return True

def parse_files(path, **kwargs):
    client = Client(**kwargs)
    for fn in os.listdir(path):
        if fn.lower().endswith('log'):
            continue
        if 'log' not in fn.lower():
            continue
        if 'access' not in fn.lower():
            continue
        fn = os.path.join(path, fn)
        lf = LogFile(client=client, filename=fn)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('-s', dest='host', default='localhost')
    p.add_argument('-p', dest='port', type=int, default=27017)
    p.add_argument('-d', dest='database', default='wowzalogs')
    p.add_argument('path')
    args = p.parse_args()
    kwargs = {
        'client_conf':{'host':args.host, 'port':args.port},
        'database':args.database,
    }
    print(args.path, kwargs)
    parse_files(args.path, **kwargs)

if __name__ == '__main__':
    main()
