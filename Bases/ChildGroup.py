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
# ChildGroup.py
# Copyright (c) 2010 - 2011 Matthew Reid

try:
    import UserDict
except:
    import collections as UserDict
from osc_base import OSCBaseObject
import Serialization
from misc import ZeroCenteredGroup

class ChildGroup(OSCBaseObject, UserDict.UserDict):
    _saved_class_name = 'ChildGroup'
    _IsChildGroup_ = True
    _Properties = {'name':dict(type=str)}
    _saved_attributes = ['name', 'ignore_index', '_IsChildGroup_']
    _saved_child_objects = ['indexed_items']
    def __init__(self, **kwargs):
        UserDict.UserDict.__init__(self)
        self.indexed_items = {}
        self.deserialize_callback = kwargs.get('deserialize_callback')
        self.parent_obj = kwargs.get('parent_obj')
        self.child_class = kwargs.get('child_class')
        self.allow_index_resort = kwargs.get('allow_index_resort', False)
        if self.child_class == '__self__':
            self.child_class = self.parent_obj.__class__
        self.send_child_updates_to_osc = kwargs.get('send_child_updates_to_osc', False)
        self.updating_child_from_osc = False
        name = kwargs.get('name')
        if name:
            kwargs.setdefault('osc_address', name)
        OSCBaseObject.__init__(self, **kwargs)
        self.register_signal('child_added', 'child_removed', 'child_index_changed', 'child_update')
        if 'deserialize' not in kwargs:
            self.name = kwargs.get('name')
            self.ignore_index = kwargs.get('ignore_index', False)
        if self.send_child_updates_to_osc:
            self.add_osc_handler(callbacks={'child-update':self._on_osc_child_update})
        self.bind(child_update=self._ChildGroup_on_own_child_update)
        
    def add_child(self, cls=None, **kwargs):
        def do_add_child(child):
            self.update({child.id:child})
            if self.ignore_index:
                osc_address = child.id
            else:
                osc_address = child.Index
                self.indexed_items.update({child.Index:child})
                child.bind(Index=self.on_child_Index_changed)
            if False:#self.osc_enabled and isinstance(child, OSCBaseObject) and not child.osc_enabled:
                osc_address = str(osc_address)
                self.LOG.info('ChildGroup %s auto add osc_address %s' % (self.name, osc_address))
                child.set_osc_address(osc_address)
                child.init_osc_attrs()
            self.resort_indecies()
            self.emit('child_added', ChildGroup=self, obj=child)
            self.emit('child_update', ChildGroup=self, mode='add', obj=child)
            return child
            
        child = kwargs.get('existing_object')
        if child is not None:
            if child.id in self:
                return
            if not self.ignore_index:
                index = child.Index
                if index is None:
                    index = kwargs.get('Index', self.find_max_index() + 1)
                if not self.check_valid_index(index):
                    self.LOG.warning('Index error: could not add child', self.name, child)
                    return False
                child.Index = index
            child.ChildGroup_parent = self
            return do_add_child(child)
            
        c_kwargs = kwargs.copy()
        if self.osc_enabled:
            c_kwargs.setdefault('osc_parent_node', self.osc_node)
        c_kwargs.update(dict(ChildGroup_parent=self, 
                             ParentEmissionThread=self.ParentEmissionThread))
        if not self.ignore_index:
            try:
                index = kwargs.get('Index', self.find_max_index() + 1)
            except:
                print self.indexed_items
                raise
            if not self.check_valid_index(index):
                self.LOG.warning('ChildGroup %s invalid index: %s' % (self.name, index))
                return
            c_kwargs['Index'] = index
        if cls is None:
            cls = self.child_class
        if self.parent_obj is not None:
            cls, c_kwargs = self.parent_obj.ChildGroup_prepare_child_instance(self, cls, **c_kwargs)
        if cls is None:
            return
        child = cls(**c_kwargs)
        return do_add_child(child)
        
    def del_child(self, child, unlink=True):
        if child.id in self:
            del self[child.id]
        if not self.ignore_index:
            child.unbind(self.on_child_Index_changed)
        if child.Index in self.indexed_items:
            del self.indexed_items[child.Index]
        if unlink:
            child.unlink()
        self.resort_indecies()
        self.emit('child_removed', ChildGroup=self, obj=child, id=child.id)
        self.emit('child_update', ChildGroup=self, mode='remove', obj=child)
        
    def detach_child(self, child):
        if child.id in self:
            del self[child.id]
        child.unbind(self)
        if getattr(child, 'ChildGroup_parent', None) == self:
            delattr(child, 'ChildGroup_parent')
        if child.Index in self.indexed_items:
            del self.indexed_items[child.Index]
        self.resort_indecies()
        self.emit('child_removed', ChildGroup=self, obj=child, id=child.id)
        self.emit('child_update', ChildGroup=self, mode='remove', obj=child)
        
    def get(self, key):
        if type(key) == int and not self.ignore_index:
            return self.indexed_items.get(key)
        return super(ChildGroup, self).get(key)
        
    def iter_indexed(self):
        for i in sorted(self.indexed_items.iterkeys()):
            child = self.indexed_items[i]
            yield child.id, child
        
    def iteritems(self):
        if self.ignore_index:
            return super(ChildGroup, self).iteritems()
        return self.iter_indexed()
        
    def itervalues(self):
        if self.ignore_index:
            return super(ChildGroup, self).itervalues()
        return (child for key, child in self.iter_indexed())
        
    def items(self):
        return [(key, val) for key, val in self.iteritems()]
        
    def values(self):
        return [val for key, val in self.iteritems()]
        
    def find_max_index(self):
        if len(self) ==0 or len(self.indexed_items) == 0:
            return 0
        return max(self.indexed_items.keys())
        
    def check_valid_index(self, index):
        if self.ignore_index:
            return True
        return type(index) == int and index not in self.indexed_items
        
    def resort_indecies(self):
        if not self.allow_index_resort:
            return
        if getattr(self, '_sorting_indecies', False):
            return
        indecies = sorted(self.indexed_items.keys())
        sorted_indecies = range(len(indecies))
        if indecies == sorted_indecies:
            return
        self._sorting_indecies = True
        for current_index, new_index in zip(indecies, sorted_indecies):
            self.indexed_items[current_index].Index = new_index
        self._sorting_indecies = False
        
    def clear(self):
        for c in self.values()[:]:
            self.del_child(c)
            #c.unbind(self.on_child_Index_changed)
        #self.indexed_items.clear()
        super(ChildGroup, self).clear()
        
    def on_child_Index_changed(self, **kwargs):
        obj = kwargs.get('obj')
        old = kwargs.get('old')
        value = kwargs.get('value')
        if old is not None and old in self.indexed_items:
            del self.indexed_items[old]
        if value is not None:
            self.indexed_items[value] = obj
        self.resort_indecies()
        self.emit('child_index_changed', ChildGroup=self, obj=obj, old=old, value=value)
        self.emit('child_update', ChildGroup=self, mode='Index', obj=obj, old=old, value=value)
        
    def unbind_all(self, *args):
        self.unbind(*args)
        for child in self.itervalues():
            child.unbind(*args)
        
    def _ChildGroup_on_own_child_update(self, **kwargs):
        if not self.osc_enabled:
            return
        if self.updating_child_from_osc:
            return
        if not self.send_child_updates_to_osc:
            return
        mode = kwargs.get('mode')
        child = kwargs.get('obj')
        values = [mode, child.id, child.Index]
        if mode == 'Index':
            return
        if mode == 'add':
            values.append(child.to_json())
        self.osc_node.send_message(address='child-update', value=values)
        
    def _on_osc_child_update(self, **kwargs):
        self.updating_child_from_osc = True
        values = kwargs.get('values')
        mode = values[0]
        key = values[1]
        i = values[2]
        if mode == 'add':
            js = values[3]
            d = self._get_saved_attr(saved_child_objects=[])
            d['saved_children']['indexed_items'] = {i:Serialization.from_json(js)}
            self._load_saved_attr(d)
        elif mode == 'remove':
            child = self.get(key)
            if child is not None:
                self.del_child(child)
        self.updating_child_from_osc = False
            
    def _load_saved_attr(self, d, **kwargs):
        if 'saved_class_name' not in d and not self.updating_child_from_osc:
            newd = self._get_saved_attr()
            items = {}
            for key, val in d.iteritems():
                if val['attrs']['Index'] is not None:
                    i = int(val['attrs']['Index'])
                else:
                    if not len(items):
                        i = self.find_max_index() + 1
                    else:
                        i = max(items.keys()) + 1
                    val['attrs']['Index'] = i
                items[i] = val
            newd['saved_children'] = {'indexed_items':items}
            d = newd
        items = d['saved_children']['indexed_items']
        for key in items.keys()[:]:
            if type(key) != int:
                item = items[key]
                #print 'replacing str index: ', key, int(key), item, self
                del items[key]
                items[int(key)] = item
        super(ChildGroup, self)._load_saved_attr(d, **kwargs)
        
    def _deserialize_child(self, d, **kwargs):
        #print 'ChildGroup deserialize child: ', kwargs, d
        if kwargs.get('saved_child_obj') != 'indexed_items':
            return super(ChildGroup, self)._deserialize_child(d, **kwargs)
        i = d['attrs']['Index']
        key = kwargs.get('key')
        if type(key) == str:
            key = int(key)
            kwargs['key'] = key
            #print 'ChildGroup %s deserialize child, key is string: %s' % (key, kwargs)
        if self.deserialize_callback is not None:
            obj = self.deserialize_callback(d)
            ckwargs = dict(existing_object=obj)
            if True:#obj.Index is None:
                ckwargs['Index'] = i
            self.add_child(**ckwargs)
        elif key is not None and key in self.indexed_items:
            obj = self.indexed_items[key]
            obj._load_saved_attr(d)
        else:
            obj = self.add_child(Index=i, deserialize=d)
            #obj = super(ChildGroup, self)._deserialize_child(d, **kwargs)
        return obj
        
    def __repr__(self):
        return '<%s of object %r>' % (self, self.parent_obj)
        
    def __str__(self):
        return 'ChildGroup %s: %r' % (self.name, self.data)

class ZeroCenteredChildGroup(ChildGroup):
    def __init__(self, **kwargs):
        self.zero_centered_items = ZeroCenteredGroup()
        kwargs.setdefault('allow_index_resort', True)
        super(ZeroCenteredChildGroup, self).__init__(**kwargs)
    def get_zero_centered(self, **kwargs):
        child = kwargs.get('child')
        if child is None:
            child_index = kwargs.get('index')
            if child_index is None:
                child_id = kwargs.get('id')
                child = self[child_id]
            else:
                child = self.indexed_items[child_index]
        return self.zero_centered_items.get_zero_centered(child.Index)
    def on_child_Index_changed(self, **kwargs):
        child = kwargs.get('obj')
        old = kwargs.get('old')
        value = kwargs.get('value')
        if old in self.zero_centered_items:
            del self.zero_centered_items[old]
        self.zero_centered_items[value] = child
        super(ZeroCenteredChildGroup, self).on_child_Index_changed(**kwargs)
    def _ChildGroup_on_own_child_update(self, **kwargs):
        child = kwargs.get('obj')
        mode = kwargs.get('mode')
        if mode == 'add':
            self.zero_centered_items[child.Index] = child
        elif mode == 'remove':
            if child.Index in self.zero_centered_items:
                del self.zero_centered_items[child.Index]
        super(ZeroCenteredChildGroup, self)._ChildGroup_on_own_child_update(**kwargs)
    
    
