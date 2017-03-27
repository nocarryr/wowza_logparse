import operator
import datetime

import pytz
import pymongo
import jsonfactory

UTC = pytz.UTC

class SubclassIterator(object):
    @classmethod
    def _iter_subclasses(cls):
        yield cls
        for _cls in cls.__subclasses__():
            if not issubclass(_cls, SubclassIterator):
                continue
            for subcls in _cls._iter_subclasses():
                yield subcls

class SelectorBase(SubclassIterator):
    def __init__(self, *values, **kwargs):
        self.values = list(values)
    def __call__(self):
        return self.build()
    def build(self):
        v = self.values
        if len(v) > 1:
            v = list(v)
        else:
            v = [v[0]]
        return {self._selector_key:v}
    @classmethod
    def _deserialize(cls, d):
        for _cls in SelectorBase._iter_subclasses():
            if not hasattr(_cls, '_selector_key'):
                continue
            if _cls._selector_key != d['_selector_key']:
                continue
            return _cls(*d['values'])
    def _serialize(self):
        d = {k:getattr(self, k) for k in ['_selector_key', 'values']}
        return {'_Selector_':d}
    def __eq__(self, other):
        if not isinstance(other, SelectorBase):
            return NotImplemented
        if not hasattr(self, '_selector_key') or not hasattr(other, '_selector_key'):
            return NotImplemented
        if self._selector_key != other._selector_key:
            return False
        return list(self.values) == list(other.values)
    def __ne__(self, other):
        return not self == other
    def __repr__(self):
        return '<{self.__class__.__name__} "{self}">'.format(self=self)
    def __str__(self):
        return '{self._selector_key} {self.values}'.format(self=self)

class Equal(SelectorBase):
    _selector_key = '$eq'
    _op = operator.eq

class NotEqual(SelectorBase):
    _selector_key = '$ne'
    _op = operator.not_

class Greater(SelectorBase):
    _selector_key = '$gt'
    _op = operator.gt

class GreaterEqual(SelectorBase):
    _selector_key = '$gte'
    _op = operator.ge

class Less(SelectorBase):
    _selector_key = '$lt'
    _op = operator.lt

class LessEqual(SelectorBase):
    _selector_key = '$lte'
    _op = operator.le

class Contains(SelectorBase):
    _selector_key = '$in'
    _op = operator.contains

class NotContains(SelectorBase):
    _selector_key = '$nin'
    _op = 'uhh....'

def build_selector_map():
    m = {'by_operator':{}, 'by_querystring':{}}
    for cls in SelectorBase._iter_subclasses():
        if cls is SelectorBase:
            continue
        key = cls._selector_key.lstrip('$')
        cls._querystring = key
        m['by_operator'][cls._op] = cls
        m['by_querystring'][key] = cls
    return m

SELECTOR_MAP = build_selector_map()

class Query(SubclassIterator):
    def __init__(self, key, sort=False, reverse=False, **kwargs):
        self.key = key
        self.reverse = reverse
        self.sort = sort
        if self.reverse:
            self.sort = True
        self.selectors = {}
    def __call__(self, coll):
        spec = self.build_filter_spec()
        if spec is None:
            result = coll.find()
        else:
            result = coll.find(**spec)
        if self.sort:
            result = result.sort(*self.build_sort_spec())
        return result
    def _add_selector(self, cls, *values):
        sel = self.selectors.get(cls._selector_key)
        if sel is None:
            sel = cls(*values)
            self.selectors[cls._selector_key] = sel
        else:
            if cls in [Contains, NotContains]:
                sel.values.extend(list(values))
            else:
                sel.values = list(values)
        return sel
    def filter(self, *values, **kwargs):
        if len(values):
            self._add_selector(Contains, *values)
        for key, val in kwargs.items():
            cls = SELECTOR_MAP['by_querystring'][key]
            if not isinstance(val, (list, tuple, set)):
                val = [val]
            self._add_selector(cls, *val)
    def build_filter_spec(self):
        sel_spec = {}
        for sel in self.selectors.values():
            sel_spec.update(sel())
        print({self.key:sel_spec})
        if not len(sel_spec):
            return None
        return {self.key:sel_spec}
    def build_sort_spec(self):
        if not self.sort:
            return None
        if self.reverse:
            s_attr = pymongo.DESCENDING
        else:
            s_attr = pymongo.ASCENDING
        return (self.key, s_attr)
    @classmethod
    def _deserialize(cls, d):
        obj = cls(*(d[key] for key in ['key', 'sort', 'reverse']))
        obj.selectors.update(d['selectors'])
        return obj
    def _serialize(self):
        d = {k:getattr(self, k) for k in ['key', 'sort', 'reverse', 'selectors']}
        return {'_Query_':d}
    def __eq__(self, other):
        if not isinstance(other, Query):
            return NotImplemented
        for key in ['key', 'sort', 'reverse']:
            if getattr(self, key) != getattr(other, key):
                return False
        if set(self.selectors.keys()) != set(other.selectors.keys()):
            return False
        for key, sel in self.selectors.items():
            if sel != other.selectors[key]:
                return False
        return True
    def __ne__(self, other):
        return not self == other
    def __repr__(self):
        return '<{self.__class__.__name__} "{self}">'.format(self=self)
    def __str__(self):
        return '{self.key}'.format(self=self)

class QueryGroup(object):
    def __init__(self):
        self.queries = {}
        self.query_order = []
    def __call__(self, coll, **kwargs):
        sort_spec = self.build_sort_spec()
        if len(sort_spec):
            kwargs.setdefault('sort', sort_spec)
        spec = self.build_filter_spec()
        if spec is None:
            result = coll.find({}, **kwargs)
        else:
            result = coll.find(spec, **kwargs)
        return result
    def build_filter_spec(self):
        spec = []
        for q in self.queries.values():
            qspec = q.build_filter_spec()
            if qspec is None:
                continue
            spec.append(q.build_filter_spec())
        if not len(spec):
            return None
        return {'$and':spec}
    def build_sort_spec(self):
        spec = []
        for q in self.query_order:
            qspec = q.build_sort_spec()
            if qspec is None:
                continue
            spec.append(qspec)
        return spec
    def _add_query(self, key, sort=False, reverse=False, **kwargs):
        q = self.queries.get(key)
        if q is None:
            q = Query(key, sort, reverse)
            self.queries[key] = q
            self.query_order.append(q)
        q.filter(**kwargs)
        return q
    def add_sort(self, key, reverse=False):
        q = self.queries.get(key)
        if q is None:
            q = self._add_query(key, sort=True, reverse=reverse)
        else:
            q.sort = True
            q.reverse = reverse
        return q
    def filter(self, **kwargs):
        for key, val in kwargs.items():
            if '__' not in key:
                q = self._add_query(key)
                q.filter(*val)
            else:
                key, querystring = key.split('__')
                self._add_query(key, **{querystring:val})
    def exclude(self, **kwargs):
        for key, val in kwargs.items():
            q = self._add_query(key)
            if not isinstance(val, (list, tuple, set)):
                val = [val]
            q.filter(nin=val)
    @classmethod
    def _deserialize(cls, d):
        obj = cls()
        for q in d['query_order']:
            if q.key in obj.queries:
                continue
            obj.queries[q.key] = q
            obj.query_order.append(q)
        return obj
    def _serialize(self):
        return {'_QueryGroup_':{'query_order':self.query_order}}
    def __eq__(self, other):
        if not isinstance(other, QueryGroup):
            return NotImplemented
        if set(self.queries.keys()) != set(other.queries.keys()):
            return False
        if len(self.query_order) != len(other.query_order):
            return False
        for my_q, oth_q in zip(self.query_order, other.query_order):
            if my_q != oth_q:
                return False
        return True


@jsonfactory.register
class JsonFilterHandler(object):
    cls_map = {
        '_Selector_':SelectorBase,
        '_Query_':Query,
        '_QueryGroup_':QueryGroup,
    }
    def encode(self, o):
        if isinstance(o, (SelectorBase, Query, QueryGroup)):
            return o._serialize()
    def decode(self, d):
        for key, cls in self.cls_map.items():
            if key in d:
                return cls._deserialize(d[key])
        return d

@jsonfactory.register
class DateTimeSerializer(object):
    iso_fmt = '%Y-%m-%dT%H:%M:%S.%fZ%z'
    def encode(self, o):
        if isinstance(o, datetime.datetime):
            if o.tzinfo is None:
                o = UTC.localize(o)
            else:
                o = UTC.normalize(o)
            return {'_dt_str_':o.strftime(self.iso_fmt)}
    def decode(self, d):
        if '_dt_str_' in d:
            s = d['_dt_str_']
            s, tzoffset = s.split('Z')
            dt = datetime.datetime.strptime(s, self.iso_fmt.split('Z')[0])
            if len(tzoffset):
                dh = int(tzoffset[1:3])
                dm = int(tzoffset[3:])
                td = datetime.timedelta(hours=dh, minutes=dm)
                if tzoffset.startswith('+'):
                    dt += td
                elif tzoffset.startswith('-'):
                    dt -= td
            dt = UTC.localize(dt)
            return dt
        return d
