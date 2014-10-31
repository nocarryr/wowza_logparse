#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Serialization.py
# Copyright (c) 2010 - 2011 Matthew Reid

import sys
try:
    import UserDict
except:
    import collections as UserDict
import json

from Properties import EMULATED_TYPES

json_presets = {'tiny':{'sort_keys':True, 'indent':None, 'separators':(',', ':')}, 
                'pretty':{'sort_keys':True, 'indent':3, 'separators':(', ', ':')}}

class Serializer(object):
    def __init__(self, **kwargs):
        d = kwargs.get('deserialize')
        if d:
            self._load_saved_attr(d)
            for key in self.saved_attributes:
                if not hasattr(self, key):
                    setattr(self, key, None)
            for key in self.saved_child_objects:
                if not hasattr(self, key):
                    setattr(self, key, {})
                    
    def to_json(self, incl_dict={}, **kwargs):
        json_preset = kwargs.get('json_preset', 'tiny')
        if 'json_preset' in kwargs:
            del kwargs['json_preset']
        d = self._get_saved_attr(**kwargs)
        d.update(incl_dict)
        return to_json(d, json_preset)
        
    def from_json(self, string, **kwargs):
        d = from_json(string)
        self._load_saved_attr(d, **kwargs)
        
    def _get_saved_attr(self, **kwargs):
        saved_child_objects = kwargs.get('saved_child_objects')
        if saved_child_objects is not None:
            del kwargs['saved_child_objects']
        d = {}
        d.update({'saved_class_name':self.saved_class_name, 'attrs':{}})
        for key in self.saved_attributes:
            val = getattr(self, key, None)
            d['attrs'][key] = val
        if not hasattr(self, 'saved_child_objects'):
            return d
        def serialize(obj, **kwargs):
            d = False
            if isinstance(obj, Serializer):
                d = serialize_object(obj, **kwargs)
            elif isinstance(obj, dict):
                d = serialize_dict(obj, **kwargs)
            return d
        def serialize_object(obj, **kwargs):
            return obj._get_saved_attr(**kwargs)
        def serialize_dict(objdict, **kwargs):
            serialized = {}
            for key, val in objdict.iteritems():
                d = serialize(val, **kwargs)
                if d is False:
                    continue
                serialized[key] = d
            return serialized
        d['saved_children'] = {}
        if saved_child_objects is None:
            saved_child_objects = self.saved_child_objects
        for attr in saved_child_objects:
            child_obj = getattr(self, attr)
            d['saved_children'][attr] = serialize(child_obj, **kwargs)
#            child_dict = getattr(self, attr)
#            if isinstance(child_dict, Serializer):
#                saved = child_dict._get_saved_attr(**kwargs)
#                if saved is False:
#                    continue
#                d['saved_children'][attr] = saved
#            elif isinstance(child_dict, dict):
#                d['saved_children'][attr] = {}
#                for key, val in child_dict.iteritems():
#                    if isinstance(val, Serializer):
#                        saved = val._get_saved_attr(**kwargs)
#                        if saved is not False:
#                            d['saved_children'][attr].update({key:saved})
#                    elif isinstance(val, dict):
#                        d['saved_children'][attr].update({key:{}})
#                        for dkey, dval in val.iteritems():
#                            saved = dval._get_saved_attr(**kwargs)
#                            if saved is not False:
#                                d['saved_children'][attr][key].update({dkey:saved})
        return d
        
    def _load_saved_attr(self, d, **kwargs):
        if 'saved_class_name' in d:
            self.saved_class_name = d['saved_class_name']
        for key, val in d.get('attrs', {}).iteritems():
            if key in self.saved_attributes:
                setattr(self, key, val)
        
#        def deserialize_obj(d, parentobj):
#            return parentobj._deserialize_child(d)
#        def deserialize_dict(d, parentobj, keys=None, return_dict=None, do_setattr=False):
#            if keys is None:
#                keys = d.keys()
#            if return_dict is None:
#                return_dict = {}
#            for key in keys:
#                if key not in d:
#                    continue
#                val = d[key]
#                if 'attrs' in val and 'saved_class_name' in val['attrs']:
#                    obj = deserialize_obj(val, parentobj)
#                else:
#                    if type(parentobj) == dict:
#                        cdict = parentobj.get(key)
#                    else:
#                        cdict = getattr(parentobj, key, None)
#                    if cdict is None:
#                        cdict = {}
#                        if do_setattr:
#                            setattr(parentobj, key, cdict)
#                    obj = deserialize_dict(val, parentobj, cdict)
#                if key not in return_dict:
#                    return_dict[key] = obj
#            return return_dict
#                
#        if 'saved_children' in d:
#            keys = kwargs.get('saved_child_objects')
#            deserialize_dict(d['saved_children'], parentobj=self, keys=keys, do_setattr=True)
        def deserialize_child(d, **kwargs):
            try:
                c = self._deserialize_child(d, **kwargs)
            except TypeError:
                if 'keyword' in str(sys.exc_info()[1]):
                    c = self._deserialize_child(d)
                else:
                    raise
            return c
        def is_ChildGroup(obj, key, d):
            if d.get('saved_class_name') == 'ChildGroup':
                return True
            if type(key) == str and getattr(getattr(obj, key, None), '_IsChildGroup_', False):
                return True
            if val.get('attrs', {}).get('_IsChildGroup_'):
                return True
        if 'saved_children' in d:
            keys = kwargs.get('saved_child_objects', d['saved_children'].keys())
            for key in keys:
                val = d['saved_children'].get(key)
                if val is None:
                    continue
                if is_ChildGroup(self, key, val):
                    cg = getattr(self, key)
                    cg._load_saved_attr(val)
                    continue
                if hasattr(self, key):
                    cdict = getattr(self, key)
                else:
                    cdict = {}
                    setattr(self, key, cdict)
                for ckey, cval in val.iteritems():
                    if is_ChildGroup(cdict, ckey, cval):
                        cg = cdict[ckey]
                        cg._load_saved_attr(cval)
                        continue
                    dskwargs = dict(saved_child_obj=key, key=ckey)
                    child = deserialize_child(cval, **dskwargs)
                    if ckey != dskwargs['key']:
                        print 'ckey != kwargs: ', (ckey, type(ckey)), (dskwargs['key'], type(dskwargs['key']))
                    ckey = dskwargs['key']
                    if child and ckey not in cdict:
                        cdict.update({ckey:child})

    def _deserialize_child(self, d, **kwargs):
        name = d.get('saved_class_name')
        for cls in self.saved_child_classes:
            if cls._saved_class_name == name:
                return cls(deserialize=d)
        return False

def to_json(obj, json_preset='tiny'):
    jskwargs = dict(cls=Encoder)
    jskwargs.update(json_presets[json_preset])
    s = json.dumps(obj, **jskwargs)
    return s
    
def from_json(jstring):
    return json.loads(jstring, cls=Decoder)
    
class Handler(object):
    def encode(self, o):
        return {self._key:self._jsontype(o)}
    def decode(self, o):
        return self._pytype(o[self._key])
        
class SetHandler(Handler):
    _key = 'py/set'
    _pytype = set
    _jsontype = list
    
HANDLERS = (SetHandler(), )
HANDLERS_BY_PYTYPE = dict(zip([h._pytype for h in HANDLERS], HANDLERS))
HANDLERS_BY_KEY = dict(zip([h._key for h in HANDLERS], HANDLERS))

class Encoder(json.JSONEncoder):
    def default(self, o):
        h = HANDLERS_BY_PYTYPE.get(type(o))
        if h is None:
            return super(Encoder, self).default(o)
        return h.encode(o)
        
class Decoder(json.JSONDecoder):
    def __init__(self, **kwargs):
        kwargs['object_hook'] = self._object_hook
        super(Decoder, self).__init__(**kwargs)
    def _object_hook(self, d):
        if not isinstance(d, dict):
            return d
        def un_unicode(obj):
            if isinstance(obj, unicode):
                return str(obj)
            if isinstance(obj, list):
                return [un_unicode(o) for o in obj]
            if isinstance(obj, tuple):
                return tuple([un_unicode(o) for o in obj])
            if isinstance(obj, dict):
                newd = {}
                for k, v in obj.iteritems():
                    k = un_unicode(k)
                    v = un_unicode(v)
                    newd[k] = v
                return newd
            return obj
        d = un_unicode(d)
        if len(d) != 1:
            return d
        ## now we're sure there's exactly one key
        k, v = d.items()[0]
        h = HANDLERS_BY_KEY.get(k)
        if h is None:
            return d
        return h.decode(d)
