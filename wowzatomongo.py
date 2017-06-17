import os
import argparse
import datetime

import pymongo
from pymongo import MongoClient
from bson import DBRef
from bson.objectid import ObjectId

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

def combined_datetime(dt, datetime_subindex):
    dt = dt.replace(microsecond=0)
    dt += datetime.timedelta(microseconds=datetime_subindex*1000)
    return dt

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
        coll.create_index([('datetime', pymongo.ASCENDING)])
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
        dt = combined_datetime(entry.dt, entry.dt_index)
        doc = {
            'file_id':self.file_id,
            'datetime':dt,
        }
        existing = coll.find(doc)
        if existing.count():
            #raise Exception('doc {} exists: {}'.format(doc, [_doc for _doc in existing]))
            return False
        doc.update(entry.fields)
        coll.insert_one(doc)
        return True

session_model = {
    'start_datetime':datetime.datetime,
    'end_datetime':datetime.datetime,
    'first_entry':ObjectId,
    'parse_complete':bool,
    'duration_seconds':float,
    'sc_bytes':int,
    'cs_bytes':int,
    'entries':list,
}

class Session(object):
    def __init__(self, client, first_entry):
        self.client = client
        self.db = client.db
        self.first_entry = first_entry
        self.entry_coll = self.db.entries
        self.session_coll = self.db.sessions
        self.session_doc = self.session_coll.find_one({'first_entry':self.first_entry['_id']})
        if self.session_doc is None:
            self.session_doc = self.build_doc()
    @classmethod
    def create(cls, client, first_entry):
        session = cls(client, first_entry)
        session()
        return session
    @classmethod
    def build_sessions(cls, client):
        db = client.db
        session_coll = db.sessions
        entry_coll = db.entries
        entry_coll.create_index('c-client-id')
        entry_coll.create_index('session_id')
        sessions = session_coll.find({'complete':False})
        print('updating {} incomplete sessions'.format(sessions.count()))
        for doc in sessions:
            entry = entry_coll.find_one({'_id':doc['first_entry']})
            cls.create(client, entry)
        filt = {'session_parsed':{'$ne':True}}
        num_created = 0
        for event_name in ['connect', 'create', 'play']:
            filt['x-event'] = event_name
            entries = entry_coll.find(filt, sort=[('datetime', pymongo.ASCENDING)])
            print('searching event_name: {}, num_entries={}'.format(event_name, entries.count()))
            for entry in entries:
                entry = entry_coll.find_one({'_id':entry['_id']})
                if entry.get('session_parsed'):
                    continue
                if not entry['c-client-id']:
                    continue
                session = cls.create(client, entry)
                num_created += 1
                if num_created % 100 == 0:
                    print('created {} sessions: {}'.format(num_created, session.session_doc['start_datetime']))
    def __call__(self):
        doc = self.session_doc
        if doc['complete']:
            return
        complete = self.populate()
        if not complete:
            return
        try:
            self.update_session()
        except:
            self.update_doc({'complete':False})
            raise
    def build_doc(self):
        d = {
            'start_datetime':self.first_entry['datetime'],
            'first_entry':self.first_entry['_id'],
            'complete':False,
            'entries':[self.first_entry['_id']],
        }
        r = self.session_coll.insert_one(d)
        d['_id'] = r.inserted_id
        self.entry_coll.update_one(
            {'_id':self.first_entry['_id']},
            {'$set':{'session_id':d['_id'], 'session_parsed':True}}
        )
        return d
    def update_doc(self, data=None):
        def build_update(_doc):
            keys = (k for k in _doc.keys() if k != '_id')
            return {'$set':{k:_doc[k] for k in keys}}
        doc = self.session_doc
        if data is not None:
            doc.update(data)
            self.session_coll.update_one(
                {'_id':doc['_id']},
                build_update(data),
            )
        self.session_coll.update_one(
            {'_id':doc['_id']},
            build_update(doc),
        )
    def get_entries_filter(self):
        start_dt = self.first_entry['datetime']
        end_dt = start_dt + datetime.timedelta(days=7)
        return {
            'c-client-id':self.first_entry['c-client-id'],
            'datetime':{'$gte':start_dt, '$lt':end_dt},
        }
    def get_entries(self):
        filt = self.get_entries_filter()
        return self.entry_coll.find(filt)
    def get_session_entries(self):
        doc = self.session_doc
        return self.entry_coll.find({'session_id':doc['_id']})
    def populate(self):
        doc = self.session_doc
        if doc.get('end_datetime') is not None:
            return True
        filt = self.get_entries_filter()
        filt['_id'] = {'$nin':doc['entries']}
        entries = self.entry_coll.find(filt)
        if not entries.count():
            return False
        complete = False
        for entry in entries.sort('datetime', pymongo.ASCENDING):
            doc['entries'].append(entry['_id'])
            if entry['x-event'] in ['disconnect', 'destroy']:
                doc['end_datetime'] = entry['datetime']
                complete = True
        self.entry_coll.update_many(
            {'_id':{'$in':doc['entries']}},
            {'$set':{'session_id':doc['_id'], 'session_parsed':True}}
        )
        doc['complete'] = complete
        self.update_doc()
        return complete
    def update_session(self):
        fieldmap = {'user_agent':'c-user-agent', 'app_name':'x-app',
                    'stream_name':'x-sname', 'protocol':'c-proto',
                    'client_ip':'c-ip', 'stream_id':'x-stream-id'}

        doc = self.session_doc
        start_dt = doc['start_datetime']
        data = {'sc_bytes':0, 'cs_bytes':0, 'end_datetime':start_dt}
        entries = self.get_session_entries()

        for entry in entries.sort('datetime', pymongo.ASCENDING):
            if entry['datetime'] > data['end_datetime']:
                data['end_datetime'] = entry['datetime']
            current_duration = entry['datetime'] - start_dt
            entry['current_duration'] = current_duration.total_seconds()

            if entry['sc-bytes'] is not None:
                b = int(entry['sc-bytes'])
                if b > data['sc_bytes']:
                    data['sc_bytes'] = b
                if entry['current_duration'] > 0:
                    entry['sc-bytes-avg'] = data['sc_bytes'] / entry['current_duration']
                else:
                    entry['sc-bytes-avg'] = data['sc_bytes']
            if entry['cs-bytes'] is not None:
                b = int(entry['cs-bytes'])
                if b > data['cs_bytes']:
                    data['cs_bytes'] = b
                if entry['current_duration'] > 0:
                    entry['cs-bytes-avg'] = data['cs_bytes'] / entry['current_duration']
                else:
                    entry['cs-bytes-avg'] = data['cs_bytes']

            update_data = {k:v for k, v in entry.items() if k != '_id'}
            self.entry_coll.update_one({'_id':entry['_id']}, {'$set':update_data})

            for doc_key, entry_key in fieldmap.items():
                if doc_key in data:
                    continue
                if not entry[entry_key]:
                    continue
                data[doc_key] = entry[entry_key]

        data['complete'] = True
        self.update_doc(data)


def parse_files(path, **kwargs):
    client = Client(**kwargs)
    for fn in sorted(os.listdir(path)):
        if fn.lower().endswith('log'):
            continue
        if 'log' not in fn.lower():
            continue
        if 'access' not in fn.lower():
            continue
        fn = os.path.join(path, fn)
        lf = LogFile(client=client, filename=fn)

def parse_sessions(**kwargs):
    client = Client(**kwargs)
    Session.build_sessions(client)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('-s', dest='host', default='localhost')
    p.add_argument('-p', dest='port', type=int, default=27017)
    p.add_argument('-d', dest='database', default='wowzalogs')
    p.add_argument('--sessions-only', dest='sessions_only', action='store_true')
    p.add_argument('path')
    args = p.parse_args()
    kwargs = {
        'client_conf':{'host':args.host, 'port':args.port},
        'database':args.database,
    }
    print(args.path, kwargs)
    if not args.sessions_only:
        parse_files(args.path, **kwargs)
    parse_sessions(**kwargs)

if __name__ == '__main__':
    main()
