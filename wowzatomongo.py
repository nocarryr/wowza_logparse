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
        self.file_doc = file_doc
    def __call__(self):
        if self.file_doc['parsed']:
            print('skipping file {}'.format(self.base_fn))
        else:
            print('parsing file {}'.format(self.base_fn))
            self.parser.filename = self.filename
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
    def __init__(self, client, first_entry=None, session_doc=None):
        self.client = client
        self.db = client.db
        self.first_entry = first_entry
        self.entry_coll = self.db.entries
        self.session_coll = self.db.sessions
        if session_doc is not None:
            self.session_doc = session_doc
            self.first_entry = self.entry_coll.find_one({
                '_id':session_doc['first_entry'],
            })
        else:
            self.session_doc = self.session_coll.find_one({
                'first_entry':self.first_entry['_id']
            })
            if self.session_doc is None:
                self.build_doc()
    @classmethod
    def create(cls, client, first_entry=None, session_doc=None):
        session = cls(client, first_entry, session_doc)
        session()
        return session
    @classmethod
    def build_sessions(cls, client, logfile=None):
        db = client.db
        session_coll = db.sessions
        entry_coll = db.entries
        entry_coll.create_index('c-client-id')
        entry_coll.create_index('session_id')
        session_coll.create_index([('start_datetime', pymongo.ASCENDING)])
        filt = {'session_parsed':{'$ne':True}, 'session_id':None}
        if logfile is not None:
            if logfile.file_doc.get('sessions_parsed'):
                return
            filt['file_id'] = logfile.file_id
        num_created = 0
        for event_name in ['connect', 'create', 'play']:
            filt['x-event'] = event_name
            entries = entry_coll.find(filt, sort=[('datetime', pymongo.ASCENDING)])
            entry_ids = entries.distinct('_id')
            print('searching event_name: {}, num_entries={}'.format(event_name, entries.count()))
            for entry_id in entry_ids:
                entry = entry_coll.find_one({'_id':entry_id})
                if entry.get('session_parsed'):
                    continue
                if not entry['c-client-id']:
                    continue
                session = cls.create(client, entry)
                num_created += 1
                if num_created % 100 == 0:
                    print('created {} sessions: {}'.format(num_created, session.session_doc['start_datetime']))
        logfile.file_coll.update_one(
            {'_id':logfile.file_id},
            {'$set':{'sessions_parsed':True}}
        )
        cls.finalize_incomplete_sessions(client)
    @classmethod
    def finalize_incomplete_sessions(cls, client):
        db = client.db
        session_coll = db.sessions
        sessions = session_coll.find({'populated':False})
        print('populating {} incomplete sessions'.format(sessions.count()))
        for doc in sessions:
            cls.create(client, session_doc=doc)
        sessions = session_coll.find({'complete':False, 'populated':True})
        print('updating {} populated sessions'.format(sessions.count()))
        for doc in sessions:
            session = cls(client, session_doc=doc)
            session.update_session()
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
            'populated':False,
            'entries':[self.first_entry['_id']],
        }
        r = self.session_coll.insert_one(d)
        d['_id'] = r.inserted_id
        self.session_doc = d
        self.add_entries(self.first_entry)
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
        else:
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
        return self.entry_coll.find({
            'session_id':doc['_id'],
            'session_parsed':{'$ne':True},
        })
    def add_entries(self, *entries, **kwargs):
        do_doc_update = kwargs.get('update_doc', True)
        doc = self.session_doc
        all_ids = [e['_id'] for e in entries]
        missing_ids = [e_id for e_id in all_ids if e_id not in doc['entries']]
        if len(missing_ids):
            doc['entries'].extend(missing_ids)
            if do_doc_update:
                self.update_doc()
        self.entry_coll.update_many(
            {'_id':{'$in':all_ids}},
            {'$set':{'session_id':doc['_id'], 'session_parsed':True}}
        )
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
        def iter_entries(_entries):
            for entry in _entries.sort('datetime', pymongo.ASCENDING):
                yield entry
                if entry['x-event'] in ['disconnect', 'destroy']:
                    doc['end_datetime'] = entry['datetime']
                    doc['populated'] = True
                    break
        self.add_entries(*iter_entries(entries), update_doc=False)
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
            entry['session_parsed'] = True

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
        lf()
        Session.build_sessions(client, lf)
    Session.finalize_incomplete_sessions(client)

def parse_sessions(path, **kwargs):
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
        Session.build_sessions(client, lf)
    Session.finalize_incomplete_sessions(client)

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
    if args.sessions_only:
        parse_sessions(args.path, **kwargs)
    else:
        parse_files(args.path, **kwargs)

if __name__ == '__main__':
    main()
