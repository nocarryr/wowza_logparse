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
# Properties.py
# Copyright (c) 2010 - 2011 Matthew Reid

import threading
import collections
import weakref

def getbases(startcls, endcls=None, reverse=False):
    if endcls is None:
        endcls = 'object'
    clslist = []
    cls = startcls
    while cls.__name__ != endcls:
        clslist.append(cls)
        cls = cls.__bases__[0]
    clslist.append(cls)
    if reverse:
        clslist.reverse()
    #print clslist
    return clslist
    
Lock = None
def get_Lock_class():
    global Lock
    return threading.Lock
    if Lock is not None:
        return Lock
    try:
        import threadbases
        Lock = threadbases.Lock
        return Lock
    except:
        return threading.Lock

class ClsProperty(object):
    '''Property that can be attached to a class.  Can be created automatically
    by adding a dictionary "_Properties" to an instance of BaseObject
    containing {'property_name':{option:value, ...}, ...}
    :Parameters:
        'name' : str, name of the Property
        'default_value' : if not None, this will be the default value when instances
            are initialized, otherwise None will be used.  default is None
        'type' : type, if not None, this will be used for type verification.
            Otherwise, the type will be assumed by either the 'default_value'
            or the first value given to the Property.  default is None
        'ignore_type' : bool, whether type verification will be used.  default is True
        'min' : if not None, this will be used set the minimum allowed value.
            This attribute can also be modified on an instance of the Property.
            Currently, this has only been tested with int and float types. default is None
        'max' : if not None, this will be used set the maximum allowed value.
            This attribute can also be modified on an instance of the Property.
            Currently, this has only been tested with int and float types. default is None
        'entries' : a sequence containing possible values.  if present, this will
            prevent anything other than the contents from being set.
        'ignore_range' : bool, whether to use the 'min' and 'max' attributes to
            verify value range, regardless of whether they are set as None. default is False
        'symbol' : str, string that can be used to format the value for output.
            default is an empty string
        'quiet' : bool, if True, BaseObject will emit the 'property_changed' signal
            any time this Property's value is changed.  If the Property is intended
            to be set rapidly (i.e. a fader value) set this to False to keep things
            running more efficiently.  default is False
        'fvalidate' : str, if not None, name of an instance method to validate
            a value (given as an argument).  The method must return True or False.
            This does not override the build-in type validation function.
            This must be a string that can be used with "getattr(self, 'method_name')".
            default is None
        'fformat' : str, if not None, name of an instance method to return a 
            formatted value (given as an argument) before being passed to the 
            setter method.
            This must be a string that can be used with "getattr(self, 'method_name')".
            default is None
        'fget' : str, if not None, name of an instance method to use to get the 
            value of the Property.  This will bypass the built-in getter.
            This must be a string that can be used with "getattr(self, 'method_name')".
            default is None
        'fset' : str, if not None, name of an instance method to use to set the 
            value of the Property.  This will bypass the built-in setter thus
            bypassing the built-in validation and formatting functionality.
            This must be a string that can be used with "getattr(self, 'method_name')".
            default is None
    '''
    
    _obj_property_attrs = ['name', 'min', 'max', 'symbol', 'type', 'quiet', 
                           'ignore_range', 'entries', 'threaded']
    def __init__(self, **kwargs):
        self.cls = kwargs.get('cls')
        self.name = kwargs.get('name')
        self.ignore_type = kwargs.get('ignore_type', False)
        self.ignore_range = kwargs.get('ignore_range', False)
        self.default_value = kwargs.get('default')
        self.min = kwargs.get('min')
        self.max = kwargs.get('max')
        self.entries = kwargs.get('entries')
        self.symbol = kwargs.get('symbol', '')
        self.type = kwargs.get('type', type(self.default_value))
        self.quiet = kwargs.get('quiet', False)
        self.additional_property_kwargs = kwargs.get('additional_property_kwargs', {})
        self.ObjPropertyClass = kwargs.get('ObjPropertyClass', ObjProperty)
        
        ## TODO: threading disabled for now. messes with gtk stuff (as i imagined)
        #self.threaded = kwargs.get('threaded', False)
        self.threaded = False
        
        for key in ['fget', 'fset', 'fvalidate', 'fformat']:
            fn = getattr(self, '_%s' % (key))
            attr = kwargs.get(key)
            clsfn = None
            if attr is not None:
                for cls in getbases(self.cls, 'BaseObject'):
                    clsfn = getattr(cls, attr, None)
                    if clsfn is not None:
                        #print 'clsfn: ', attr, clsfn
                        break
            if clsfn is not None:
                fn = clsfn
            setattr(self, key, fn)
        
    def init_instance(self, obj):
        pkwargs = dict(zip(self._obj_property_attrs, [getattr(self, attr) for attr in self._obj_property_attrs]))
        pkwargs.update(self.additional_property_kwargs)
        pkwargs.update({'obj':obj, 'value':self.default_value})
        obj.Properties[self.name] = self.ObjPropertyClass(**pkwargs)
        
    def _fget(self, obj):
        prop = obj.Properties.get(self.name)
        if prop is None:
            return
        return prop.value
        
    def _fset(self, obj, value):
        value = self.fformat(obj, value)
        if self.entries is not None and value not in self.entries:
            return
        if self._validate_type(obj, value) and self.fvalidate(obj, value):
            obj.Properties[self.name].set_value(value)
            
    def _fvalidate(self, obj, value):
        prop = obj.Properties[self.name]
        if prop.ignore_range:
            return True
        if prop.min is not None and prop.max is not None:
            return value >= prop.min and value <= prop.max            
        return True
        
    def _fformat(self, obj, value):
        return value
        
    def _validate_type(self, obj, value):
        prop = obj.Properties[self.name]
        if self.ignore_type:
            return True
        if value is None:
            return True
        if prop.type is None:
            if value is not None:
                prop.type = type(value)
            return True
        return isinstance(value, prop.type)
        
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return self.fget(obj)
        
    def __set__(self, obj, value):
        #old = self.fget(obj)
        self.fset(obj, value)
        #if old != value:
        #    obj.Properties[self.name].emit(old=old)
        
class MyWVDict(weakref.WeakValueDictionary):
    def __init__(self, *args, **kwargs):
        self.printstring = kwargs.get('printstring', '')
        if 'printstring' in kwargs:
            del kwargs['printstring']
        #super(MyWVDict, self).__init__(*args, **kwargs)
        weakref.WeakValueDictionary.__init__(self, *args, **kwargs)
        def remove(wr, selfref=weakref.ref(self)):
            self = selfref()
            if self is not None:
                del self.data[wr.key]
                #print 'REMOVE: ', len(self.data), self.printstring, wr.key
        self._remove = remove
    def __setitem__(self, key, value):
        weakref.WeakValueDictionary.__setitem__(self, key, value)
        #print 'ADD: ', len(self.data), self.printstring, key
        

def normalize_value(value, min, max):
    return value / float(max - min)
def unnormalize_value(value, min, max):
    return value * float(max - min)
def normalize_and_offset_value(value, min, max):
    return (value - min) / float(max - min)
def unnormalize_and_offset_value(value, min, max):
    return (value * float(max - min)) + min
    
class ObjProperty(object):
    '''This object will be added to an instance of a class that contains a
        ClsProperty.  It is used to store the Property value, min and max settings,
        and handle callbacks.  It also looks at its type and attempts to use
        specialized classes to emulate container types.
        Currently, only list and dict types are supported.
    
    '''
    __slots__ = ('name', 'value', 'min', 'max', 'symbol', 'entries', 
                 'type', '_type', 'parent_obj', 'quiet', 'weakrefs', '__weakref__', 
                 'threaded', 'ignore_range', 'own_callbacks',  
                 'linked_properties', 'enable_emission', 'queue_emission', 
                 'emission_event', 'emission_thread', 'emission_lock', 'own_emission_lock')
    def __init__(self, **kwargs):
        self.enable_emission = True
        self.queue_emission = False
        self.name = kwargs.get('name')
        self.type = kwargs.get('type')
        self._type = EMULATED_TYPES.get(self.type)
        self.value = kwargs.get('value')
        if self._type is not None:
            self.value = self._type(self.value, parent_property=self)
        self.min = kwargs.get('min')
        self.max = kwargs.get('max')
        self.symbol = kwargs.get('symbol')
        self.parent_obj = kwargs.get('obj')
        self.quiet = kwargs.get('quiet')
        self.ignore_range = kwargs.get('ignore_range')
        self.entries = kwargs.get('entries')
        #self.threaded = kwargs.get('threaded')
        self.own_callbacks = set()
        #self.callbacks = set()
        #self.weakrefs = MyWVDict(printstring='property weakref' + self.name)
        self.weakrefs = weakref.WeakValueDictionary()
        self.linked_properties = set()
        #self.emission_lock = threading.Lock()
        lockcls = get_Lock_class()
        if getattr(lockcls, '_is_threadbases_Lock', False):
            self.emission_lock = lockcls(owner_thread=self.emission_thread)
            self.own_emission_lock = lockcls(owner_thread=self.emission_thread)
        else:
            self.emission_lock = lockcls()
            self.own_emission_lock = lockcls()
        self.emission_event = threading.Event()
        #self.emission_thread = kwargs.get('emission_thread', getattr(self.parent_obj, 'ParentEmissionThread', None))
        
    @property
    def emission_thread(self):
        return getattr(self.parent_obj, 'ParentEmissionThread', None)
        
    def _get_range(self):
        return [self.min, self.max]
    def _set_range(self, value):
        self.min, self.max = value
    
    range = property(_get_range, _set_range)
        
    def _get_normalized(self):
        value = getattr(self.parent_obj, self.name)
        f = normalize_value
        if hasattr(value, '_normalization_iter'):
            return value._normalization_iter(value, self.min, self.max, f)
        return f(value, self.min, self.max)
    def _set_normalized(self, value):
        _value = getattr(self.parent_obj, self.name)
        f = unnormalize_value
        if hasattr(_value, '_normalization_iter'):
            value = _value._normalization_iter(value, self.min, self.max, f)
        else:
            value = self.type(f(value, self.min, self.max))
        self.set_value(value)
    
    normalized = property(_get_normalized, _set_normalized)
    
    def _get_normalized_and_offset(self):
        value = getattr(self.parent_obj, self.name)
        f = normalize_and_offset_value
        if hasattr(value, '_normalization_iter'):
            return value._normalization_iter(value, self.min, self.max, f)
        return f(value, self.min, self.max)
    def _set_normalized_and_offset(self, value):
        _value = getattr(self.parent_obj, self.name)
        f = unnormalize_and_offset_value
        if hasattr(_value, '_normalization_iter'):
            value = _value._normalization_iter(value, self.min, self.max, f)
        else:
            value = self.type(f(value, self.min, self.max))
        self.set_value(value)
    
    normalized_and_offset = property(_get_normalized_and_offset, _set_normalized_and_offset)
    
    def set_value(self, value):
        self.enable_emission = False
        if self._type is not None:
            old = self.value.copy()
            self.value._update_value(value)
        else:
            old = self.value
            self.value = value
        self.enable_emission = True
        
        if old != self.value or self.queue_emission:
            self.emit(old)
        self.queue_emission = False
            
    def get_lock(self, *args, **kwargs):
        emission_thread = self.emission_thread
        if emission_thread is None:
            return True
        elock = self.emission_lock
        if not getattr(elock, '_is_threadbases_Lock', False) and elock.locked():
            return False
#        if threading.currentThread() != emission_thread:
#            print 'emitting from wrong thread: %s, should be %s' % (threading.currentThread(), emission_thread)
#        if elock._is_owned() and elock._RLock__owner != emission_thread.ident:
#            owner = threading._active[elock._RLock__owner]
#            current = threading.currentThread()
#            print 'emission_lock owned by thread %s, not %s, current=%s' % (owner, emission_thread, current)
        return elock.acquire()
        
    def release_lock(self):
        ethread = self.emission_thread
        if ethread is None:
            return
        elock = self.emission_lock
        if not getattr(elock, '_is_threadbases_Lock', False) and not elock.locked():
            return
        #if not elock._is_owned():
        #    return
        #if elock._RLock__owner != ethread.ident:
        #    return
        elock.release()
        
    def bind(self, cb):
        #if not self.emission_lock._is_owned() and self.emission_lock._RLock__owner != threading._get_ident():
        #    self.get_lock(self.bind, cb)
        #    return
        if getattr(cb, 'im_self', None) == self.parent_obj:
            self.own_callbacks.add(cb)
        else:
            #self.get_lock()
            wrkey = (cb.im_func, id(cb.im_self))
            self.weakrefs[wrkey] = cb.im_self
            #self.release_lock()
        
    def unbind(self, cb):
        #if not self.emission_lock._is_owned() and self.emission_lock._RLock__owner != threading._get_ident():
        #    self.get_lock(self.unbind, cb)
        #    return
        result = False
        if not hasattr(cb, 'im_self'):
            ## Assume this is an instance object and attempt to unlink
            ## any methods that belong to it.
            obj = cb
            found = set()
            for wrkey in self.weakrefs.keys()[:]:
                if self.weakrefs[wrkey] == obj:
                    found.add(getattr(obj, wrkey[0].func_name))
            for realcb in found:
                r = self.unbind(realcb)
                if r:
                    result = True
            return result
        wrkey = (cb.im_func, id(cb.im_self))
        if wrkey in self.weakrefs:
            #self.get_lock()
            del self.weakrefs[wrkey]
            #self.release_lock()
            result = True
        if cb in self.own_callbacks:
            result = True
            self.own_callbacks.discard(cb)
        return result
        
    def link(self, prop, key=None):
        '''Link this Property to another Property.
        
        '''
        if self.update_linked_property(prop, key):
            self.linked_properties.add((prop, key))
            attrs = ['min', 'max']
            if prop.type == self.type:
                for attr in attrs:
                    setattr(prop, attr, getattr(self, attr))
            elif self._type is not None:
                for attr in attrs:
                    setattr(prop, attr, getattr(self, attr)[key])
            elif prop._type is not None:
                for attr in attrs:
                    pvalue = getattr(prop, attr)
                    pvalue[key] = getattr(self, attr)
            
    def unlink(self, prop, key=None):
        self.linked_properties.discard((prop, key))
        
    def update_linked_property(self, prop, key=None):
        if prop.type == self.type:
            prop.set_value(self.value)
        elif self._type is not None:
            prop.set_value(self.value[key])
        elif prop._type is not None:
            #prop.set_value({key:self.value})
            prop.value[key] = self.value
        else:
            return False
        return True
        
    def emit(self, old):
        if self.own_emission_lock.locked():
            return
        if not self.enable_emission:
            self.queue_emission = True
            return
        if not hasattr(self.parent_obj, self.name):
            return
        value = getattr(self.parent_obj, self.name)
        cb_kwargs = dict(name=self.name, Property=self, value=value, old=old, obj=self.parent_obj)
        t = self.emission_thread
        #if t is not None and t._thread_id != threading.currentThread().name:
        if t is not None and not t.can_currentthread_emit:
            #print 'Property %s doing threaded emission to %s from %s' % (self.name, self.emission_thread._thread_id, threading.currentThread().name)
            t.insert_threaded_call(self._do_emission, **cb_kwargs)
            #self.emission_event.set()
            #self.emission_event.clear()
        else:
            self._do_emission(**cb_kwargs)
            
    def _do_emission(self, **kwargs):
        with self.own_emission_lock:
            for cb in self.own_callbacks.copy():
                cb(**kwargs)
        r = self.get_lock()
        if not r:
            return
        emission_thread = self.emission_thread
        wrefs = self.weakrefs
        for wrkey in wrefs.keys()[:]:
            f, objID = wrkey
            obj = wrefs.get(wrkey)
            if obj is None:
                continue
            objthread = getattr(obj, 'ParentEmissionThread', None)
            if objthread is None or objthread == emission_thread or getattr(objthread, 'can_currentthread_emit', False):
                f(obj, **kwargs)
            else:
                m = getattr(obj, f.__name__)
                objthread.insert_threaded_call(m, **kwargs)
        if not self.quiet:
            pobj = self.parent_obj
            if hasattr(pobj, 'emit'):
                pobj.emit('property_changed', **kwargs)
        for prop, key in self.linked_properties:
            self.update_linked_property(prop, key)
        self.release_lock()
            
    def __repr__(self):
        return '<Property %s of object %r>' % (self.name, self.parent_obj)
    def __str__(self):
        return repr(self)


class ThreadedEmitter(threading.Thread):
    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.callback = kwargs.get('callback')
        self.id = id(self.callback)
        self.parent_property = kwargs.get('parent_property')
        self.running = threading.Event()
        #print 'threaded emitter init: ', self.parent_property.name
    def run(self):
        self.running.set()
        while self.running.isSet():
            self.parent_property.emission_event.wait()
            self.do_callback()
        #print 'threaded emitter stopped: ', self.parent_property.name
    def do_callback(self):
        if not self.running.isSet():
            return
        cb_kwargs = dict(name=self.parent_property.name, Property=self.parent_property, 
                         obj=self.parent_property.parent_obj, value=self.parent_property.value)
        #print 'threaded emitter: ', cb_kwargs['name'], cb_kwargs['value'], self.name
        self.callback(**cb_kwargs)
    def stop(self):
        self.running.clear()
        self.parent_property.emit(self.parent_property.value)

class ListProperty(list):
    def __init__(self, initlist=None, **kwargs):
        self.parent_property = kwargs.get('parent_property')
        super(ListProperty, self).__init__(initlist)
    @staticmethod
    def _check_normalize(value, min, max):
        if not isinstance(value, list):
            raise TypeError(value)
        if not isinstance(min, list):
            min = [min] * len(value)
        if not isinstance(max, list):
            max = [max] * len(value)
        return value, min, max
    @staticmethod
    def _normalization_iter(value, min, max, f=None):
        value, min, max = ListProperty._check_normalize(value, min, max)
        if f is not None:
            return [f(value[i], min[i], max[i]) for i in range(len(value))]
        results = []
        for i in range(len(value)):
            results.append((i, value[i], min[i], max[i]))
        return results
    def copy(self):
        return self[:]
    def clear(self):
        old = self[:]
        self.parent_property.enable_emission = False
        while len(self):
            item = self.pop()
        self.parent_property.enable_emission = True
        self.parent_property.emit(old)
    def _update_value(self, value):
        for i, item in enumerate(value):
            if i <= len(self):
                if item != self[i]:
                    self[i] = item
            else:
                self.append(item)
    def __setitem__(self, i, item):
        old = self[:]
        list.__setitem__(self, i, item)
        self.parent_property.emit(old)
    def __delitem__(self, i):
        old = self[:]
        list.__delitem__(self, i)
        self.parent_property.emit(old)
    def append(self, *args):
        old = self[:]
        super(ListProperty, self).append(*args)
        self.parent_property.emit(old)
    def insert(self, *args):
        old = self[:]
        super(ListProperty, self).insert(*args)
        self.parent_property.emit(old)
    def pop(self, *args):
        old = self[:]
        super(ListProperty, self).pop(*args)
        self.parent_property.emit(old)
    def remove(self, *args):
        old = self[:]
        super(ListProperty, self).remove(*args)
        self.parent_property.emit(old)
    def extend(self, *args):
        old = self[:]
        super(ListProperty, self).extend(*args)
        self.parent_property.emit(old)
        
class DictProperty(dict):
    def __init__(self, initdict=None, **kwargs):
        self.parent_property = kwargs.get('parent_property')
        if initdict is None:
            initdict = {}
        super(DictProperty, self).__init__(initdict)
    @staticmethod
    def _check_normalize(value, min, max):
        if not isinstance(value, dict):
            raise TypeError(value)
        if not isinstance(min, dict):
            keys = value.keys()
            min = dict(zip(keys, [min]*len(keys)))
        if not isinstance(max, dict):
            keys = value.keys()
            max = dict(zip(keys, [max]*len(keys)))
        return value, min, max
    @staticmethod
    def _normalization_iter(value, min, max, f=None):
        value, min, max = DictProperty._check_normalize(value, min, max)
        keys = value.keys()[:]
        if f is not None:
            return dict(zip(keys, [f(value[key], min[key], max[key]) for key in keys]))
        results = {}
        for key in keys:
            results[key] = (key, value[key], min[key], max[key])
        return results
    def _update_value(self, value):
        self.update(value)
    def __setitem__(self, key, item):
        old = self.copy()
        change = self._check_for_change(key, item)
        dict.__setitem__(self, key, item)
        if change:
            self.parent_property.emit(old)
    def __delitem__(self, key):
        old = self.copy()
        dict.__delitem__(self, key)
        self.parent_property.emit(old)
    def clear(self, *args):
        old = self.copy()
        super(DictProperty, self).clear(*args)
        self.parent_property.emit(old)
    def update(self, d):
        for key, val in d.iteritems():
            if self._check_for_change(key, val):
                self.parent_property.queue_emission = True
        super(DictProperty, self).update(d)
    def _check_for_change(self, key, value):
        if key not in self:
            return True
        return value != self[key]
    
class SetProperty(set):
    def __init__(self, value, **kwargs):
        self.parent_property = kwargs.get('parent_property')
        super(SetProperty, self).__init__(value)
    def _update_value(self, value):
        self.add(value)
    def add(self, item):
        old = self.copy()
        super(SetProperty, self).add(item)
        self.parent_property.emit(old)
    def discard(self, item):
        old = self.copy()
        super(SetProperty, self).discard(item)
        self.parent_property.emit(old)
    def clear(self):
        old = self.copy()
        super(SetProperty, self).clear()
        self.parent_property.emit(old)
    def copy(self):
        return set(self)
    
class DequeProperty(collections.deque):
    def __init__(self, value, **kwargs):
        self.parent_property = kwargs.get('parent_property')
        super(DequeProperty, self).__init__(value)
    def append(self, value):
        old = self.copy()
        super(DequeProperty, self).append(value)
        self.parent_property.emit(old)
    def appendleft(self, value):
        old = self.copy()
        super(DequeProperty, self).appendleft(value)
        self.parent_property.emit(old)
    def extend(self, value):
        old = self.copy()
        super(DequeProperty, self).extend(value)
        self.parent_property.emit(old)
    def extendleft(self, value):
        old = self.copy()
        super(DequeProperty, self).extendleft(value)
        self.parent_property.emit(old)
    def pop(self, *args):
        old = self.copy()
        super(DequeProperty, self).pop(*args)
        self.parent_property.emit(old)
    def popleft(self, *args):
        old = self.copy()
        super(DequeProperty, self).popleft(*args)
        self.parent_property.emit(old)
    def clear(self):
        old = self.copy()
        super(DequeProperty, self).clear()
        self.parent_property.emit(old)
    def remove(self):
        old = self.copy()
        super(DequeProperty, self).remove()
        self.parent_property.emit(old)
    def copy(self):
        return list(self)[:]
        
EMULATED_TYPES = {list:ListProperty, dict:DictProperty, set:SetProperty, collections.deque:DequeProperty}
    
class PropertyConnector(object):
    '''Mixin for objects to easily connect to Properties.
        Adds a descriptor called 'Property' (a normal python 'property' object)
        that aids in connecting and disconnecting to Property objects.
    :Methods:
        'set_Property_value' : 
        'unlink_Property' : unlinks the current Property.  Don't call directly, 
            instead use 'self.Property = None'.  This can be extended by subclasses
            however to perform functions after a Property is detached.
        'attach_Property' : attaches the given Property.  Don't call directly, 
            instead use 'self.Property = some_Property'.  This can be extended by subclasses
            however to perform functions after a Property is attached.
    :properties:
        'Property' : attaches the given Property object and detaches the current
            one if it exists.  If None is given, it simply detaches.
    '''
    
    def _get_Property(self):
        if not hasattr(self, '_Property'):
            self._Property = None
        return self._Property
    def _set_Property(self, value):
        '''This descriptor attaches the given Property object and detaches
        the current one if it exists.  If None is given, it simply detaches.
        For convenience, a list or tuple can be given with an object and the
        name of the Property and the Property object will be looked up
        (e.g. self.Property = [SomeObject, 'some_property_name'])
        '''
        if type(value) == tuple or type(value) == list:
            obj, propname = value
            value = obj.Properties[propname]            
        if value != self.Property:
            if self.Property is not None:
                self.unlink_Property(self.Property)
            self._Property = value
            if value is not None:
                self.attach_Property(value)
    
    Property = property(_get_Property, _set_Property)
    
    def unlink_Property(self, prop):
        '''unlinks the current Property.  Don't call directly, 
        instead use 'self.Property = None'.  This can be extended by subclasses
        however to perform functions after a Property is detached.
        :Parameters:
            'prop' : Property object
        '''
        prop.unbind(self.on_Property_value_changed)
        
    def attach_Property(self, prop):
        '''attaches the given Property.  Don't call directly, 
        instead use 'self.Property = some_Property'.  This can be extended by 
        subclasses however to perform functions after a Property is attached.
        :Parameters:
            'prop' : Property object
        '''
        prop.bind(self.on_Property_value_changed)
        
    def set_Property_value(self, value, convert_type=False):
        '''Use this method for convenience to set the value of the attached
        Property, if there is one attached.
        :Parameters:
            'value' : the value to set
            'convert_type' : bool, if True, attempts to convert the given
                value to the type associated with the Property. default is False
        '''
        if self.Property is not None:
            if self.Property.parent_obj is None:
                self.Property = None
                return
            if convert_type:
                if type(value) == float and self.Property.type == int:
                    value = round(value)
                value = self.Property.type(value)
            setattr(self.Property.parent_obj, self.Property.name, value)
            
    def get_Property_value(self):
        '''Use this method for convenience to get the value of the attached
        Property, if there is one attached.
        '''
        if self.Property is not None:
            if self.Property.parent_obj is None:
                self.Property = None
                return
            return getattr(self.Property.parent_obj, self.Property.name)
            
    def on_Property_value_changed(self, **kwargs):
        '''Override this method to get Property updates.  This is the method
        bound when a Property is attached.
        '''
        pass
