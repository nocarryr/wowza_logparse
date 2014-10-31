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
# threadbases.py
# Copyright (c) 2011 Matthew Reid

import os, os.path
import time
import threading
import traceback
import collections
import weakref
import functools

class Lock(object):
    _is_threadbases_Lock = True
    def __init__(self, **kwargs):
        self.owner_thread = kwargs.get('owner_thread')
        self._current_owner = None
        self.lock_count = 0
        self.__lock = threading.Lock()
    def locked(self):
        return self.is_locked
    @property
    def is_locked(self):
        return self.__lock.locked()
    @property
    def current_owner(self):
        return self._current_owner
    @current_owner.setter
    def current_owner(self, value):
        if isinstance(value, threading.Thread):
            value = value.ident
        self._current_owner = value
#    @property
#    def lock_count(self):
#        return self._lock_count
#    @lock_count.setter
#    def lock_count(self, value):
#        self._lock_count = value
#        print self
    def acquire(self, **kwargs):
        blocking = kwargs.get('blocking', True)
        ident = threading._get_ident()
        ot = self.owner_thread
        if self.is_locked:
            if ident == self.current_owner:
                self.lock_count += 1
                return True
            else:
                if ot is not None and ot.ident != ident:
                    return False
        else:
            if ot is not None and ot.ident != ident:
                return False
            self.__lock.acquire(blocking)
            self.current_owner = ident
            self.lock_count += 1
    def release(self):
        if not self.is_locked:
            return False
        ident = threading._get_ident()
        ot = self.owner_thread
        if ident != self.current_owner:
            return False
        self.lock_count -= 1
        if self.lock_count == 0:
            self.current_owner = None
            self.__lock.release()
        return True
    def __enter__(self):
        return self.acquire(blocking=True)
    def __exit__(self, *args):
        return self.release()
    def __repr__(self):
        clsname = self.__class__.__name__
        ident = self.current_owner
        owner = None
        if ident is not None:
            owner = threading._active.get(ident)
        s = '<%s (%s) owner_thread: %r, current_owner: %s, lock_count: %s>' % (clsname, id(self), self.owner_thread, owner, self.lock_count)
        return s

from BaseObject import BaseObject
from osc_base import OSCBaseObject
from partial import WeakPartial
from logger import Logger
#from Properties import ObjProperty
import Properties
from misc import setID, iterbases

setattr(Properties, 'Lock', Lock)
ObjProperty = Properties.ObjProperty

class EventValue(int):
    @property
    def value(self):
        return bool(self.event.value)
    @value.setter
    def value(self, value):
        self.event.set_value(bool(value))
    @property
    def wait_timeout(self):
        return self.event.wait_timeout
    @wait_timeout.setter
    def wait_timeout(self, value):
        self.event.wait_timeout = value
    @property
    def state(self):
        return self.value
    @state.setter
    def state(self, value):
        self.value = value
    def isSet(self):
        return self.value
    def is_set(self):
        return self.value
    def set(self):
        self.event.set()
    def clear(self):
        self.event.clear()
    def wait(self, timeout=None):
        self.event.wait(timeout)
    def __nonzero__(self):
        return self > 0
    def __str__(self):
        return str(self > 0)
        
        
class Event(ObjProperty):
    __slots__ = ['_wait_timeout', '_is_waiting', '_done_waiting', 
                 '_event', '_event_set_local']
    def __init__(self, **kwargs):
        self._event = threading.Event()
        self._is_waiting = threading.Event()
        self._done_waiting = threading.Event()
        self._done_waiting.set()
        self._wait_timeout = kwargs.get('wait_timeout')
        self._event_set_local = False
        value = kwargs.get('value', False)
        if not isinstance(value, EventValue):
            value = EventValue(value)
            value.event = self
        kwargs['value'] = value
        super(Event, self).__init__(**kwargs)
    @property
    def wait_timeout(self):
        return self._wait_timeout
    @wait_timeout.setter
    def wait_timeout(self, value):
        old = self._wait_timeout
        if value == old:
            return
        self._wait_timeout = value
        if None in [value, old]:
            return
        if self._is_waiting.isSet():
            e_initial = self._event.isSet()
            self._event.set()
            self._done_waiting.wait()
            if e_initial is False:
                self._event.clear()
    def set_value(self, value):
        if not isinstance(value, EventValue):
            value = EventValue(value)
            value.event = self
        old = self.value
        if bool(old) == bool(value):
            return
        self.value = value
        self._event_set_local = True
        if value:
            self.set()
        else:
            self.clear()
        self._event_set_local = False
        #print 'Event %s set_value: %s, current: %s' % (self.name, value, self.value)
        self.enable_emission = True
        self.emit(old)
    def isSet(self):
        return bool(self.value)
    def is_set(self):
        return self.isSet()
    def set(self):
        self._event.set()
        if self._event_set_local:
            return
        self.set_value(True)
    def clear(self):
        self._event.clear()
        if self._event_set_local:
            return
        self.set_value(False)
    def wait(self, timeout=None):
        if timeout is None:
            timeout = self.wait_timeout
        self._is_waiting.set()
        self._done_waiting.clear()
        self._event.wait(timeout)
        self._is_waiting.clear()
        self._done_waiting.set()
    def __repr__(self):
        return '<EventProperty %s of %s: value=%s, wait_timeout=%s>' % (self.name, self.parent_obj, self.isSet(), self.wait_timeout)
    def __str__(self):
        return repr(self)
    
class ChannelEvent(BaseObject):
    _Properties = {'state':dict(default=False)}
    def __init__(self, **kwargs):
        super(ChannelEvent, self).__init__(**kwargs)
        self._on_event = Event()
        self._off_event = Event()
        self._off_event.state = True
        self._on_event.bind(state=self._on_event_state_set)
        self._off_event.bind(state=self._off_event_state_set)
    def _on_event_state_set(self, **kwargs):
        pass
    def _off_event_state_set(self, **kwargs):
        pass

#class Partial(object):
#    def __init__(self, cb, *args, **kwargs):
#        obj = cb.im_self
#        self.id = id(obj)
#        self.obj_name = obj.__class__.__name__
#        self.func_name = cb.im_func.func_name
#        self._partial = functools.partial(cb, *args, **kwargs)
#    @property
#    def cb(self):
#        return self._partial.func
#    @property
#    def args(self):
#        return self._partial.args
#    @property
#    def kwargs(self):
#        return self._partial.keywords
#    def __call__(self, *args, **kwargs):
#        self._partial()
#    def __str__(self):
#        return '%s(%s), %s' % (self.obj_name, self.id, self.func_name)
#    def __repr__(self):
#        return 'ThreadBasePartial object %s: %s' % (id(self), str(self))

_THREADS = weakref.WeakValueDictionary()

def add_call_to_thread(call, *args, **kwargs):
    obj = getattr(call, 'im_self', None)
    if not isinstance(obj, BaseThread):
        return False
    obj.insert_threaded_call(call, *args, **kwargs)
    return True


class BaseThread(OSCBaseObject, threading.Thread):
    _Events = {'_running':{}, 
               '_stopped':{}, 
               '_threaded_call_ready':dict(wait_timeout=.1), 
               '_threaded_calls_idle':{}}
    _Properties = {'_thread_id':dict(default='')}
    def __new__(*args, **kwargs):
        events_by_cls = {}
        props_by_cls = {}
        cls = args[0]
        if cls != BaseThread:
            while issubclass(cls, BaseThread):
                d = {}
                p = {}
                events = cls.__dict__.get('_Events')
                if events is None:
                    cls = cls.__bases__[0]
                    continue
                props = cls.__dict__.get('_Properties', {})
                for key, val in events.iteritems():
                    e_kwargs = val.copy()
                    e_kwargs.setdefault('default', False)
                    additional_kwargs = e_kwargs.get('additional_property_kwargs', {})
                    additional_kwargs['wait_timeout'] = e_kwargs.get('wait_timeout')
                    e_kwargs['additional_property_kwargs'] = additional_kwargs
                    e_kwargs['ObjPropertyClass'] = Event
                    props[key] = e_kwargs
                setattr(cls, '_Properties', props)
                cls = cls.__bases__[0]
        return OSCBaseObject.__new__(*args, **kwargs)
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = None
        self.IsParentEmissionThread = kwargs.get('IsParentEmissionThread', False)
        thread_id = setID(kwargs.get('thread_id'))
        if thread_id in _THREADS:
            newid = '__'.join([thread_id, setID(None)])
            self.LOG.warning('thread_id %s already exists using %s' % (thread_id, newid))
            thread_id = newid
        _THREADS[thread_id] = self
        self.AllowedEmissionThreads = set()
        self.AllowedEmissionThreads |= set(kwargs.get('AllowedEmissionThreads', []))
        self.AllowedEmissionThreads.add(thread_id)
        threading.Thread.__init__(self, name=thread_id)
        OSCBaseObject.__init__(self, **kwargs)
        self._thread_id = thread_id
        self._insertion_lock = Lock()
        self.Events = {}
        timed_events = []
        
        for cls in iterbases(self, 'OSCBaseObject'):
            if not hasattr(cls, '_Events'):
                continue
            for key in cls._Events.iterkeys():
                e = self.Properties[key]
                self.Events[key] = e
                if e.wait_timeout is not None:
                    timed_events.append(e.name)
        self._threaded_calls_idle = True
        timed_events.reverse()
        self.timed_events = timed_events
        self._threaded_calls_queue = collections.deque()
        self._timed_calls_queue = TimeQueue()
        self.disable_threaded_call_waits = kwargs.get('disable_threaded_call_waits', False)
        
    @property
    def pethread_log(self):
        return pethread_logger
        
    @property
    def can_currentthread_emit(self):
        name = threading.currentThread().name
        val = name in self.AllowedEmissionThreads
        #print 'Thread %s can emit=%s currentthread=%s' % (self.name, val, name)
        return val
        
    def get_now_for_timed_calls(self):
        return time.time()
        
    def insert_threaded_call(self, call, *args, **kwargs):
        p = None
        if self.can_currentthread_emit:
            call(*args, **kwargs)
            return
        with self._insertion_lock:
            if self.IsParentEmissionThread:
                self.pethread_log('insert call', call, ' to PEThread %s' % (self.name))
            kwargs = kwargs.copy()
            kwargs['__PartialObjOwnerThread__'] = self
            p = WeakPartial(call, self._on_WeakPartial_dead, *args, **kwargs)
            if p.call_time is not None:
                self._timed_calls_queue.put(p.call_time, p)
            else:
                self._threaded_calls_queue.append(p)
            self._threaded_calls_idle = False
            self._cancel_event_timeouts()
        return p
        
    def _on_WeakPartial_dead(self, p):
        callqueue = self._threaded_calls_queue
        timequeue = self._timed_calls_queue
        print '%s WeakPartial %s dead' % (self._thread_id, p)
        with self._insertion_lock:
            if p in callqueue:
                callqueue.remove(p)
                print '%s removed %s from callqueue' % (self._thread_id, p)
            if p.call_time is not None and p.call_time in timequeue.times:
                r = timequeue.remove(time=p.call_time, item=p)
                print '%s removed %s from timequeue, result=%s' % (self._thread_id, p, r)
        
    def _cancel_event_timeouts(self, events=None):
        if events is None:
            events = self.timed_events
        for key in events:
            e = self.Events.get(key)
            if not e:
                continue
            e.set()
            
    def run(self):
        disable_call_waits = self.disable_threaded_call_waits
        do_threaded_calls = self._do_threaded_calls
        do_timed_calls = self._do_timed_calls
        loop_iteration = self._thread_loop_iteration
        self._running = True
        while self._running:
            if True:#self._running:
                loop_iteration()
                if not disable_call_waits:
                    self._threaded_call_ready.wait()
                    do_threaded_calls()
                    do_timed_calls()
        self._stopped = True
        
    def stop(self, **kwargs):
        blocking = kwargs.get('blocking', False)
        wait_for_queues = kwargs.get('wait_for_queues', True)
        self._running = False
        if self._thread_id in _THREADS:
            del _THREADS[self._thread_id]
        if wait_for_queues:
            if not len(self._threaded_calls_queue):
                self._threaded_call_ready = True
            self._cancel_event_timeouts()
        else:
            self._threaded_calls_queue.clear()
            self._threaded_call_ready = True
        if not self.isAlive():
            self._stopped = True
        if blocking and threading.currentThread() != self:
            if type(blocking) in [float, int]:
                timeout = float(blocking)
            else:
                timeout = None
            self._stopped.wait(timeout)
        
    def _thread_loop_iteration(self):
        pass
        
    def _do_threaded_calls(self):
        queue = self._threaded_calls_queue
        with self._insertion_lock:
            if not len(queue):
                if self._running:
                    if not len(self._timed_calls_queue):
                        self._threaded_call_ready = False
                        self._threaded_calls_idle = True
                return
            p = queue.popleft()
        if p.is_dead:
            print 'PARTIAL %s already dead' % (p)
        if self.IsParentEmissionThread:
            self.pethread_log('do_call: ', repr(p))
        try:
            #result = p()
            result = self._really_do_call(p)
            return (result, p.cb, p.args, p.kwargs)
        except:
            self.LOG.warning(traceback.format_exc())
    def _do_timed_calls(self):
        queue = self._timed_calls_queue
        with self._insertion_lock:
            lowest_time = queue.lowest_time()
            now = self.get_now_for_timed_calls()
            if lowest_time is None or now < lowest_time:
                if self._running:
                    if not len(self._threaded_calls_queue):
                        self._threaded_call_ready = False
                        self._threaded_calls_idle = True
                return
            p = queue.pop(lowest_time)
        if self.IsParentEmissionThread:
            self.pethread_log('do_timed_call, now=%s: %r' % (now, p))
        try:
            result = self._really_do_call(p)
            return (result, p.cb, p.args, p.kwargs)
        except:
            self.LOG.warning(traceback.format_exc())
        
    def _really_do_call(self, p):
        return p()

from scheduler import TimeQueue

class PEThreadLogger(BaseObject):
    def __init__(self, **kwargs):
        super(PEThreadLogger, self).__init__(**kwargs)
        self._logger = None
        r = self.get_logging_opts()
        if not r:
            self.GLOBAL_CONFIG.bind(update=self.on_global_config_update)
    @property
    def enabled(self):
        return self._logger is not None
    def __call__(self, *args, **kwargs):
        if not self.enabled:
            return
        now = '%18.6f' % (time.time())
        tname = threading.currentThread().name
        self._logger.info(now, tname, *args, **kwargs)
    def get_logging_opts(self):
        o = self.GLOBAL_CONFIG.get('arg_parse_dict')
        if not o:
            return False
        enabled = o.get('pethreads')
        if not enabled:
            return True
        filename = o.get('pethread_logfile')
        if not filename:
            return True
        if filename.lower() == 'true':
            filename = os.path.join(os.getcwd(), 'pethreads.log')
        self.LOG.info('pethread_filename: ', filename)
        self._logger = Logger(log_mode='basicConfig', log_filename=filename, use_conf=False, 
                              log_level='info', log_format='%(message)s', logger_kwargs={'filemode':'w'})
        return True
    def on_global_config_update(self, **kwargs):
        r = self.get_logging_opts()
        if r:
            self.GLOBAL_CONFIG.unbind(self)
        
pethread_logger = PEThreadLogger()


if __name__ == '__main__':
    import sys, time
    def events_to_str(t):
        return ', '.join([str(e) for e in t.Events.values()])
    class TestThread(BaseThread):
        _Events = {'testevent':{}}
        def __init__(self, **kwargs):
            self.last = time.time()
            super(TestThread, self).__init__(**kwargs)
        def test_call(self, **kwargs):
            now = time.time()
            print 'test_call %s: elapsed=%s, last=%s, now=%s' % (kwargs['i'], now - self.last, self.last, now)
            self.last = now
            #print 'thread_id=%s, current_thread=%s, kwargs=%s, events=%s\n' % (self._thread_id, threading.current_thread().name, kwargs, events_to_str(self))
        
    testthread = TestThread(thread_id='test')
    print 'before start: ', events_to_str(testthread)
    testthread.start()
    for i in range(5):
        #add_call_to_thread(testthread.test_call, i=i)
        testthread.insert_threaded_call(testthread.test_call, i=i)
    time.sleep(2.)
    testthread.stop(blocking=True)
    print 'after stop: ', events_to_str(testthread)
    sys.exit(0)
