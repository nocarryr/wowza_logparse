import datetime
import pytz
import json
try:
    from urllib.parse import unquote_plus, parse_qs
except ImportError:
    from urllib import unquote_plus
    from urlparse import parse_qs

from flask import Flask, request, render_template, g, url_for
from werkzeug.local import LocalProxy
import jsonfactory
from pymongo import MongoClient

from filters import QueryGroup

UTC = pytz.UTC
TZ = pytz.timezone('US/Central')
EPOCH = UTC.localize(datetime.datetime(1970, 1, 1))

DEBUG = True

app = Flask(__name__)
app.config.from_object(__name__)

client_conf = dict(
    host='localhost',
    port=27017,
    tz_aware=True,
    db_name='wowzalogs',
)

def build_backend():
    return mongo_storage.MongoStorage(config=BACKEND_CONFIG)

def get_db():
    c = getattr(g, '_mongo_client', None)
    if c is None:
        c = g._mongo_client = MongoClient(
            client_conf['host'],
            client_conf['port'],
            tz_aware=client_conf.get('tz_aware', True),
        )
    db = getattr(g, '_db', None)
    if db is None:
        db = g._db = c[client_conf['db_name']]
    return db

def slugify(s):
    for c in ' ./':
        s = '-'.join(s.split(c))
    return s


def build_query(filters=None, sorting=None):
    qgroup = QueryGroup()
    if filters is not None:
        qgroup.filter(**filters)
    if sorting is not None:
        for sort_spec in sorting:
            if isinstance(sort_spec, str):
                key = sort_spec
                reverse = False
            else:
                key, reverse = sort_spec
            qgroup.add_sort(key, reverse)
    return qgroup

def get_entries(context, **kwargs):
    db = get_db()
    coll = db.entries
    query = context.get('query')
    return query(coll, **kwargs)


def get_session_context(context=None):
    if context is None:
        context = {}
    db = get_db()
    query = context.get('query')
    if query is None:
        now = datetime.datetime.now()
        now = TZ.localize(now)
        start_dt = now - datetime.timedelta(days=90)
        query = build_query(
            sorting=[('datetime', True)],
        )
        context['query'] = query
    if 'field_names' not in context:
        context['field_names'] = sorted(db.entries.find_one().keys())
    if 'hidden_fields' not in context:
        context['hidden_fields'] = ['_id']
    return context


def parse_query_string(request):
    if '?' not in request.url:
        return None
    rdata = request.url.split('?')[1]
    rdata = unquote_plus(rdata)
    return parse_qs(rdata)

@app.route('/')
def log_collection():
    context = get_session_context()
    qdata = request.args.get('_QueryGroup_')
    if qdata is not None:
        context['query'] = jsonfactory.loads(qdata)
    results = get_entries(context)
    page_num = int(request.args.get('p', '0'))

    per_page = 50
    total_count = results.count()
    total_pages = total_count // per_page
    start_index = page_num * per_page
    end_index = start_index + per_page
    if end_index >= total_count:
        has_more = False
        end_index = total_count
    else:
        has_more = True
    url_fmt = '{base_url}?p={page}'
    qkwargs = dict(skip=start_index, limit=per_page)
    results = get_entries(context, **qkwargs)
    context.update(dict(
        has_more=has_more,
        page_num=page_num+1,
        per_page=per_page,
        total_pages=total_pages,
        prev_url=url_fmt.format(
            base_url=request.base_url,
            page=page_num-1,
        ),
        next_url=url_fmt.format(
            base_url=request.base_url,
            page=page_num+1,
        ),
        entry_iter=results,
        query_data=jsonfactory.dumps(context['query']),
    ))
    return render_template('log-collection.html', **context)


if __name__ == '__main__':
    app.run()
