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
# BaseObject.py
# Copyright (c) 2010 - 2011 Matthew Reid

import threading
import gc
try:
    import UserDict
except:
    import collections as UserDict
import atexit
import weakref

import SignalDispatcher
from Serialization import Serializer
import Properties
#from misc import iterbases

save_keys = {}
for key in ['saved_attributes', 'saved_child_classes', 'saved_child_objects']:
    save_keys.update({key:'_%s' % (key)})

class MyWVDict(weakref.WeakValueDictionary):
    def __init__(self, *args, **kwargs):
        weakref.WeakValueDictionary.__init__(self, *args, **kwargs)
        def remove(wr, selfref=weakref.ref(self)):
            self = selfref()
            if self is not None:
                #print 'REMOVE BASEOBJECT: ', wr.key
                del self.data[wr.key]
                #print 'len = ', len(self.data)
        self._remove = remove
    def __setitem__(self, key, value):
        weakref.WeakValueDictionary.__setitem__(self, key, value)
        #print 'ADD BASEOBJECT: ', value
        #print 'add len = ', len(self.data)

#lots_of_baseobjects = MyWVDict()

class BaseObject(SignalDispatcher.dispatcher, Serializer):
    '''Base class for everything.  Too many things to document.
    
    '''
    #_saved_class_name = 'BaseObject'
    _saved_attributes = ['categories_id', 'Index']
    signals_to_register = ['property_changed']
    _Properties = {'Index':dict(type=int, fvalidate='_Index_validate')}
    def __new__(*args, **kwargs):
        realcls = args[0]
        #cls = realcls
        #print 'Baseobject __new__: ', cls
        if realcls != BaseObject:
            for cls in iterbases(realcls, BaseObject.__bases__[0]):
            #while issubclass(cls, BaseObject):
                #props = getattr(cls, '_Properties', {})
                props = cls.__dict__.get('_Properties', {})
                for key, val in props.iteritems():
                    if not hasattr(cls, key):
                        p_kwargs = val.copy()
                        p_kwargs.setdefault('name', key)
                        p_kwargs['cls'] = cls
                        property = Properties.ClsProperty(**p_kwargs)
                        setattr(cls, property.name, property)
                #cls = cls.__bases__[0]
        #return SignalDispatcher.dispatcher.__new__(*args, **kwargs)
        return object.__new__(realcls)
        
    @staticmethod
    def collect_garbage(timeout=True):
        garbage_collector.queue_collection = True
        if not timeout:
            garbage_collector.wait_for_collection = True
    @staticmethod
    def pause_garbage_collection():
        garbage_collector.enable_collection = False
    @staticmethod
    def resume_garbage_collection():
        garbage_collector.enable_collection = True
        
        
        
    def __init__(self, **kwargs):
        if globals().get('GLOBAL_CONFIG', {}).get('EnableEmissionThreads'):
            build_thread = kwargs.get('BuildEmissionThread', getattr(self, 'BuildEmissionThread', False))
            t = kwargs.get('ParentEmissionThread')
            if type(t) == type and issubclass(t, BaseThread):
                ptkwargs = kwargs.get('ParentEmissionThread_kwargs', {})
                ptkwargs.setdefault('thread_id', '_'.join([t.__name__, 'ParentEmissionThread']))
                t = t(**ptkwargs)
                build_thread = False
            if build_thread:
                if type(build_thread) == str:
                    bthread_id = build_thread
                else:
                    bthread_id = '_'.join([self.__class__.__name__, 'ParentEmissionThread'])
                t = BaseThread(thread_id=bthread_id)
            if isinstance(t, BaseThread):
                if not getattr(t, 'owner', None):
                    t.owner = self
                if not t.isAlive():
                    t.start()
                kwargs['ParentEmissionThread'] = t
                t.IsParentEmissionThread = True
        else:
            kwargs['ParentEmissionThread'] = None
        self.ParentEmissionThread = kwargs.get('ParentEmissionThread')
        self.Properties = {}
        self._Index_validate_default = True
        #cls = self.__class__
        #bases_limit = getattr(cls, '_saved_bases_limit', self._saved_class_name)
        signals_to_register = set()
        save_dict = {}
        for key in save_keys.iterkeys():
            save_dict.update({key:set()})
        self.SettingsProperties = {}
        self.SettingsPropKeys = []
        self.ChildGroups = {}
        childgroups = {}
        for cls in iterbases(self, BaseObject.__bases__[0]):
        #while cls != BaseObject.__bases__[0]:# and getattr(cls, '_saved_class_name', '') != bases_limit:
            if not hasattr(self, 'saved_class_name'):
                if hasattr(cls, '_saved_class_name'):
                    self.saved_class_name = cls._saved_class_name
            signals = getattr(cls, 'signals_to_register', None)
            if signals is not None:
                for s in signals:
                    signals_to_register.add(s)
            for key, val in save_keys.iteritems():
                if hasattr(cls, val):
                    save_dict[key] |= set(getattr(cls, val))
            for propname in getattr(cls, '_Properties', {}).iterkeys():
                prop = getattr(cls, propname)
                if isinstance(prop, Properties.ClsProperty):
                    prop.init_instance(self)
            if hasattr(cls, '_SettingsProperties'):
                spropkeys = cls._SettingsProperties[:]
                spropkeys.reverse()
                self.SettingsPropKeys.extend(spropkeys)
                for propname in spropkeys:
                    prop = self.Properties.get(propname)
                    if prop:
                        self.SettingsProperties.update({propname:prop})
                save_dict['saved_attributes'] |= set(cls._SettingsProperties)
            if hasattr(cls, '_ChildGroups'):
                for cgkey, cgval in cls._ChildGroups.iteritems():
                    if cgkey in childgroups:
                        childgroups[cgkey].update(cgval)
                    else:
                        childgroups[cgkey] = cgval
            #cls = cls.__bases__[0]
        self.SettingsPropKeys.reverse()
        self.SettingsPropKeys = tuple(self.SettingsPropKeys)
        for key, val in save_dict.iteritems():
            if not hasattr(self, key):
                setattr(self, key, val)
            
        if not hasattr(self, 'root_category'):
            self.root_category = kwargs.get('root_category')
        self.categories = {}
        self.categories_id = kwargs.get('categories_id', set())
        
        kwargs.update({'signals_to_register':signals_to_register})
        SignalDispatcher.dispatcher.__init__(self, **kwargs)
        
        prebind = kwargs.get('prebind', {})
        self.bind(**prebind)
        
        childgroup = kwargs.get('ChildGroup_parent')
        if childgroup is not None:
            self.ChildGroup_parent = childgroup
            
        for key, val in childgroups.iteritems():
            cgkwargs = val.copy()
            cgkwargs.setdefault('name', key)
            ds_cb = cgkwargs.get('deserialize_callback')
            if type(ds_cb) == str:
                cgkwargs['deserialize_callback'] = getattr(self, ds_cb, None)
            self.add_ChildGroup(**cgkwargs)
        
        Serializer.__init__(self, **kwargs)
        
        i = kwargs.get('Index')
        if self.Index is None and i is not None:
            self.Index = i
        
        self.register_signal('category_update')
        
        for c_id in self.categories_id:
            if not getattr(self, 'root_category', None):
                self.root_category = self.GLOBAL_CONFIG.get('ROOT_CATEGORY')
            category = self.root_category.find_category(id=c_id)
            if category:
                self.add_category(category)
            else:
                self.LOG.warning('could not locate category id: ' + str(c_id))
            
        f = getattr(self, 'on_program_exit', None)
        if f:
            atexit.register(f)
            
        #lots_of_baseobjects[(id(self), self.__class__)] = self
        
    #def __del__(self):
    #    print self, ' delete'
        
    def bind(self, **kwargs):
        '''Binds Properties and/or signals to the given callbacks.
        Bindings are made by keyword arguments.
        Example:
            SomeObject.bind(some_property_name=self.some_callback,
                            some_signal_name=self.some_other_callback)        
        '''
        for key, val in kwargs.iteritems():
            if key in self.Properties:
                self.Properties[key].bind(val)
            if key in self._emitters:
                self.connect(key, val)
        
    def unbind(self, *args):
        '''Unbinds (disconnects) the given callback(s) or object(s).  From any
        Property and/or signal that is bound.
        Multiple arguments are evaluated.  If an object is given, this will
        search for and unbind any callbacks that belong to that object.
        '''
        results = []
        unlinked = False
        for arg in args:
            result = False
            for prop in self.Properties.itervalues():
                if prop.parent_obj is None:
                    unlinked = True
                    break
                r = prop.unbind(arg)
                if r:
                    result = True
            if unlinked:
                self.LOG.debug('unbinding, but %s is already unlinked: %s' % (self, args))
                results = [True]*len(args)
                break
            if not result:
                if not hasattr(arg, 'im_self'):
                    r = SignalDispatcher.dispatcher.disconnect(self, obj=arg)
                    if r:
                        result = True
                #elif len(self.find_signal_keys_from_callback(arg)['signals']):
                else:
                    r = SignalDispatcher.dispatcher.disconnect(self, callback=arg)
                    if r:
                        result = True
            results.append(result)
        if False in results:
            self.LOG.debug('could not unbind', self, zip(args, results))
        return results
        
    def disconnect(self, **kwargs):
        result = SignalDispatcher.dispatcher.disconnect(self, **kwargs)
        if not result:
            self.LOG.debug('could not disconnect', self, kwargs)
        return result
    
    def add_category(self, category):
        id = category.id
        self.categories.update({id:category})
        self.categories_id.add(id)
        if self not in category.members:
            category.add_member(self)
        self.emit('category_update', obj=self, category=category, state=True)
            
    def remove_category(self, category):
        if hasattr(category, 'name'):
            id = category.id
        else:
            id = category
        if self in self.categories[id].members:
            self.categories[id].del_member(self)
        self.categories.pop(id, None)
        self.categories_id.discard(id)
        self.emit('category_update', obj=self, category=category, state=False)
        
    def unlink(self):
        for category in self.categories.copy().values():
            category.del_member(self)
        SignalDispatcher.dispatcher.unlink(self)
        #self.Properties.clear()
        for prop in self.Properties.itervalues():
            prop.own_callbacks.clear()
            prop.weakrefs.clear()
            #prop.value = None
            prop.parent_obj = None
        self.collect_garbage()
        
    def stop_ParentEmissionThread(self):
        t = self.ParentEmissionThread
        if t is None:
           return
        t.stop(blocking=True)
        self.ParentEmissionThread = None
            
    def _Index_validate(self, value):
        if not hasattr(self, 'ChildGroup_parent'):
            return self._Index_validate_default
        return self.ChildGroup_parent.check_valid_index(value)
        
    def add_child_object(self, kwargs):
        kwargs.setdefault('root_category', self.root_category)
        if getattr(self, 'osc_enabled', False):
            kwargs.setdefault('osc_parent_node', self.osc_node)
            
    def add_ChildGroup(self, **kwargs):
        if getattr(self, 'osc_enabled', False):
            kwargs.setdefault('osc_parent_node', self.osc_node)
        kwargs.setdefault('parent_obj', self)
        kwargs.setdefault('ParentEmissionThread', self.ParentEmissionThread)
        cls = ChildGroup
        if kwargs.get('zero_centered', False):
            cls = ZeroCenteredChildGroup
            del kwargs['zero_centered']
        cg = cls(**kwargs)
        self.ChildGroups.update({cg.name:cg})
        setattr(self, cg.name, cg)
        return cg
        
    def ChildGroup_prepare_child_instance(self, childgroup, cls, **kwargs):
        '''Default method to modify a childgroup's child object instantiation.
        Subclasses must return cls and kwargs, but they can be modified.
        '''
        return cls, kwargs
        
    @property
    def GLOBAL_CONFIG(self):
        return globals()['GLOBAL_CONFIG']
    @GLOBAL_CONFIG.setter
    def GLOBAL_CONFIG(self, value):
        globals()['GLOBAL_CONFIG'].update(value)
        
    @property
    def LOG(self):
        global LOGGER
        if LOGGER is None:
            self._BUILD_LOGGER()
        return LOGGER
        
    def _BUILD_LOGGER(self, **kwargs):
        global LOGGER
        if LOGGER is not None:
            LOGGER.close()
        LOGGER = Logger(**kwargs)
        
    def _GET_LOGGER(self):
        global LOGGER
        return LOGGER

from misc import iterbases
from ChildGroup import ChildGroup, ZeroCenteredChildGroup

class _GlobalConfig(BaseObject, UserDict.UserDict):
    def __init__(self, **kwargs):
        BaseObject.__init__(self, **kwargs)
        self.register_signal('update')
        self.ObjProperties = {}
        UserDict.UserDict.__init__(self)
    def __setitem__(self, key, item, emit_update=True):
        old = self.data.copy()
        item = self._check_for_emulated_type(key, item)
        if item == '__OBJPROPERTY_UPDATED__':
            return
        UserDict.UserDict.__setitem__(self, key, item)
        if emit_update:
            self.emit('update', key=key, item=item, old=old)
    def __delitem__(self, key):
        old = self.data.copy()
        self._remove_emulated_property(key)
        UserDict.UserDict.__delitem__(self, key)
        self.emit('update', key=key, old=old)
    def __setattr__(self, name, value):
        if hasattr(self, 'data') and name in self.data:
            self[name] = value
            return
        object.__setattr__(self, name, value)
    def __getattr__(self, name):
        if hasattr(self, 'data') and name in self.data:
            return self[name]
        return object.__getattr__(self, name)
    def update(self, d=None, **kwargs):
        old = self.data.copy()
        newd = {}
        if d is not None:
            newd.update(d.copy())
        newd.update(kwargs.copy())
        for key, item in newd.iteritems():
            self.__setitem__(key, item, emit_update=False)
        #UserDict.UserDict.update(self, d, **kwargs)
        self.emit('update', old=old, keys=newd.keys()[:])
    def clear(self):
        old = self.data.copy()
        for key in self.ObjProperties.keys()[:]:
            self._remove_emulated_property(key)
        UserDict.UserDict.clear(self)
        self.emit('update', old=old)
    def _check_for_emulated_type(self, key, item):
        prop = self.ObjProperties.get(key)
        if prop:
            prop.set_value(item)
            return '__OBJPROPERTY_UPDATED__'
        emtype = Properties.EMULATED_TYPES.get(type(item))
        if emtype is None:
            return item
        prop = Properties.ObjProperty(name=key, value=item, type=type(item), parent_obj=self, quiet=True)
        newitem = prop.value
        self.ObjProperties[key] = prop
        prop.bind(self._on_emulated_property_update)
        return prop.value
    def _on_emulated_property_update(self, **kwargs):
        prop = kwargs.get('Property')
        key = prop.name
        prop_old = kwargs.get('old')
        old = self.data.copy()
        old[key] = prop_old
        self.emit('update', key=key, item=prop.value, old=old)
        #print 'emu_prop: ', key, prop.value, old
    def _remove_emulated_property(self, key):
        prop = self.ObjProperties.get(key)
        if prop is None:
            return
        prop.unbind(self._on_emulated_property_update)
        del self.ObjProperties[key]
        
GLOBAL_CONFIG = _GlobalConfig()

from logger import Logger

LOGGER = None

from category import Category

ROOT_CATEGORY = Category(name='root', id='root')

GLOBAL_CONFIG['ROOT_CATEGORY'] = ROOT_CATEGORY

from threadbases import BaseThread

from garbage_collection import GarbageCollector

garbage_collector = GarbageCollector(GLOBAL_CONFIG=GLOBAL_CONFIG)
