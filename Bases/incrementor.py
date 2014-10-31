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
# incrementor.py
# Copyright (c) 2011 Matthew Reid

from BaseObject import BaseObject

class Incrementor(BaseObject):
    _Properties = {'value':dict(default=0, min=0, max=9999, quiet=True), 
                   'resolution':dict(default=1), 
                   'value_offset':dict(default=0)}
    def __init__(self, **kwargs):
        super(Incrementor, self).__init__(**kwargs)
        self.name = kwargs.get('name')
        self.children = {}
        self.register_signal('bounds_reached')
        self.parent = kwargs.get('parent')
        if self.parent is not None:
            self.parent.bind(bounds_reached=self.on_parent_bounds_reached)
        self.value_set_local = False
        self.bind(value=self._on_value_set, 
                  resolution=self._on_resolution_set, 
                  bounds_reached=self._on_own_bounds_reached)
        res = kwargs.get('resolution', getattr(self, '_resolution', None))
        if res is not None:
            self.resolution = res
        children = kwargs.get('children', {})
        for key, val in children.iteritems():
            self.add_child(key, **val)
    def add_child(self, name, cls=None, **kwargs):
        if cls is None:
            cls = Incrementor
        kwargs.setdefault('parent', self)
        kwargs.setdefault('name', name)
        obj = cls(**kwargs)
        self.children[name] = obj
        return obj
    def get_values(self):
        d = self.get_all_obj()
        keys = d.keys()
        return dict(zip(keys, [d[key].value + self.value_offset for key in keys]))
    def set_values(self, **kwargs):
        d = self.get_all_obj()
        for key, val in kwargs.iteritems():
            if key not in d:
                continue
            d[key].value = val - self.value_offset
    def get_all_obj(self, **kwargs):
        d = kwargs.get('d')
        if d is None:
            root = self.get_root_obj()
            d = {}
            kwargs['d'] = d
            root.get_all_obj(d=d)
            return d
        d[self.name] = self
        for key, val in self.children.iteritems():
            val.get_all_obj(d=d)
    def get_root_obj(self):
        if self.parent is not None:
            return self.parent.get_root_obj()
        return self
    def get_root_sum(self, **kwargs):
        root_prop = kwargs.get('root_prop')
        if root_prop is None:
            root = self.get_root_obj()
            rp = root.Properties['value']
            kwargs.update({'root_prop':rp, 'value':rp.value})
            return root.get_root_sum(**kwargs)
        myval = self.value
        for child in self.children.itervalues():
            myval = myval + child.get_root_sum(**kwargs)
        if self.parent is not None:
            d = self.parent.get_range()
            myval = myval * (d['max'] - d['min'] + 1)
        return myval
    def set_root_sum(self, value):
        if self.parent is not None:
            self.parent.set_root_sum(value)
            return
        self.reset_values()
        for i in range(value):
            self += 1
    def reset_values(self, **kwargs):
        root = kwargs.get('root')
        if root is None:
            root = self.get_root_obj()
            kwargs['root'] = root
            root.reset_values(**kwargs)
            return
        self.value_set_local = True
        self.value = self.get_range()['min']
        self.value_set_local = False
        for child in self.children.itervalues():
            child.reset_values(**kwargs)
    def set_range(self, **kwargs):
        for key in ['min', 'max']:
            if key in kwargs:
                setattr(self.Properties['value'], key, kwargs[key])
    def get_range(self):
        return dict(zip(['min', 'max'], self.Properties['value'].range))
    def __add__(self, value):
        prop = self.Properties['value']
        for i in range(value):
            newval = prop.value + 1
            if newval > prop.max:
                newval = newval - (prop.max + 1) + prop.min
                self.emit('bounds_reached', mode='add')
            self.value_set_local = True
            self.value = newval
            self.value_set_local = False
        return self
    def __sub__(self, value):
        prop = self.Properties['value']
        for i in range(value):
            newval = prop.value - 1
            if newval < prop.min:
                newval = newval + prop.max
                self.emit('bounds_reached', mode='sub')
            self.value_set_local = True
            self.value = newval
            self.value_set_local = False
        return self
    def on_parent_bounds_reached(self, **kwargs):
        mode = kwargs.get('mode')
        if mode == 'add':
            self += 1
        elif mode == 'sub':
            self -= 1
    def _on_value_set(self, **kwargs):
        if self.value_set_local:
            return
        old = kwargs.get('old')
        value = kwargs.get('value')
    def _on_resolution_set(self, **kwargs):
        self.set_range(min=0, max=self.resolution - 1)
    def _on_own_bounds_reached(self, **kwargs):
        pass
        
class IncrementorGroup(BaseObject):
    def __init__(self, **kwargs):
        self.root_incrementor = None
        self.all_incrementors = {}
        super(IncrementorGroup, self).__init__(**kwargs)
        self.register_signal('value_update')
        incrementors = kwargs.get('incrementors', {})
        for key, val in incrementors.iteritems():
            self.add_incrementor(key, **val)
    def add_incrementor(self, name, cls=None, **kwargs):
        if self.root_incrementor is not None:
            return
        if cls is None:
            cls = Incrementor
        kwargs.setdefault('name', name)
        obj = cls(**kwargs)
        allobj = obj.get_all_obj()
        # This ensures that there are no existing objects in the tree
        if len(set(allobj.keys()) & set(self.all_incrementors.keys())):
            return
        #self.root_incrementors[name] = obj
        self.root_incrementor = obj
        self.all_incrementors.update(allobj)
        for incr in allobj.itervalues():
            incr.bind(value=self._on_incrementor_value_update)
        return obj
    def get_incrementor(self, name):
        return self.all_incrementors.get(name)
    def __add__(self, value):
        if self.root_incrementor is not None:
            if isinstance(value, IncrementorGroup):
                self.__convert_incr_group(mode='add', incr_group=value)
            else:
                self.root_incrementor += value
        return self
    def __sub__(self, value):
        if self.root_incrementor is not None:
            if isinstance(value, IncrementorGroup):
                self.__convert_incr_group(mode='sub', incr_group=value)
            else:
                self.root_incrementor -= value
        return self
    def _on_incrementor_value_update(self, **kwargs):
        obj = kwargs.get('obj')
        kwargs['name'] = obj.name
        self.emit('value_update', **kwargs)
    def __convert_incr_group(self, **kwargs):
        ## TODO: make this do stuff
        pass
    def __getattr__(self, name):
        if hasattr(self, 'all_incrementors'):
            incr = self.all_incrementors.get(name)
            if incr is not None:
                return incr.value
        return super(IncrementorGroup, self).__getattr__(name)
    def __setattr__(self, name, value):
        if hasattr(self, 'all_incrementors'):
            incr = self.all_incrementors.get(name)
            if incr is not None:
                incr.value = value
                return
        super(IncrementorGroup, self).__setattr__(name, value)
    
class Frame(Incrementor):
    def __init__(self, **kwargs):
        kwargs.setdefault('resolution', 30)
        super(Frame, self).__init__(**kwargs)
        self.add_child('second', Second)
        
class Microsecond(Incrementor):
    _resolution = 10 ** 6
    def __init__(self, **kwargs):
        kwargs.setdefault('name', 'microsecond')
        super(Microsecond, self).__init__(**kwargs)
        self.add_child('second', Second)
        
class Millisecond(Incrementor):
    _resolution = 1000
    def __init__(self, **kwargs):
        kwargs.setdefault('name', 'millisecond')
        super(Millisecond, self).__init__(**kwargs)
        self.add_child('second', Second)
        
class Second(Incrementor):
    _resolution = 60
    def __init__(self, **kwargs):
        super(Second, self).__init__(**kwargs)
        self.add_child('minute', Minute)
    
class Minute(Incrementor):
    _resolution = 60
    def __init__(self, **kwargs):
        super(Minute, self).__init__(**kwargs)
        self.add_child('hour', Hour)
        
class Hour(Incrementor):
    pass
    
#if __name__ == '__main__':
#    import threading
#    import datetime
#    import time
#    class TestThread(threading.Thread):
#        def run(self):
#            tick = threading.Event()
#            incrgroup = self.incrgroup
#            incrgroup.bind(value_update=self.on_value_update)
#            timeout = .001
#            #incr = ms.resolution * timeout
#            starttime = datetime.datetime.now()
#            self.starttime = starttime
#            self.now = starttime
#            print starttime
#            for key in ['hour', 'minute', 'second', 'microsecond']:
#                value = getattr(starttime, key)
#                if key == 'microsecond':
#                    value = int(value * .001) + 1
#                    key = 'millisecond'
#                setattr(incrgroup, key, value)
#            while True:
#                tick.wait(timeout)
#                self.now = datetime.datetime.now()
#                incrgroup += 1
#        def on_value_update(self, **kwargs):
#            name = kwargs.get('name')
#            if name == 'millisecond':
#                return
#            keys = ['hour', 'minute', 'second', 'millisecond']
#            print zip(keys, [getattr(self.incrgroup, key) for key in keys]), name, '\n'
#            s = self.now.strftime('%H:%M:%S')
#            print '%s.%s' % (s, self.now.microsecond * .001)
#    class oldTestThread(threading.Thread):
#        def run(self):
#            tick = threading.Event()
#            ms = Microsecond()
#            self.ms = ms
#            #ms.bind(value=self.on_ms)
#            all_obj = ms.get_all_obj()
#            all_obj['second'].bind(value=self.on_second)
#            timeout = .01
#            #incr = ms.resolution * timeout
#            self.starttime = time.time()
#            startdt = datetime.datetime.fromtimestamp(self.starttime)
#            while True:
#                tick.wait(timeout)
#                now = datetime.datetime.now()
#                self.now = time.time()
#                td = now - startdt
#                all_obj['hour'].value = td.seconds / 3600
#                all_obj['minute'].value = (td.seconds % 3600) / 60
#                all_obj['second'].value = td.seconds % 60
#                all_obj['microsecond'].value = td.microseconds
#                #elapsed = td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6
#                #ms += elapsed
#                #lasttime = now
#        def on_ms(self, **kwargs):
#            print 'microsecond: ', kwargs.get('value')
#        def on_second(self, **kwargs):
#            print 'seconds=%s, values=%s' % (self.now - self.starttime, self.ms.get_values())
#    hour = {'resolution':60}
#    minute = {'resolution':60, 'children':{'hour':hour}}
#    sec = {'resolution':60, 'children':{'minute':minute}}
#    ms = {'resolution':1000, 'children':{'second':sec}}
#    d = {'millisecond':ms}
#    incrgroup = IncrementorGroup(incrementors=d)
#    t = TestThread()
#    t.incrgroup = incrgroup
#    t.start()
#    
#    
