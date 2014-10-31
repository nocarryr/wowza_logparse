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
# masterclock.py
# Copyright (c) 2010 - 2011 Matthew Reid

import sys
import datetime
import time
import threading
import weakref

from SignalDispatcher import dispatcher
from threadbases import BaseThread
from partial import WeakPartial
from incrementor import IncrementorGroup

MIDNIGHT = datetime.time()

_CLOCKS = weakref.WeakValueDictionary()

class BaseClock(dispatcher):
    def __init__(self, **kwargs):
        super(BaseClock, self).__init__(**kwargs)
        self.register_signal('tick')
        if not len(_CLOCKS):
            i = 0
        else:
            i = max(_CLOCKS.keys()) + 1
        self.clock_index = i
        _CLOCKS[i] = self
        self.clock_interval = kwargs.get('clock_interval', .01)
        self.tick_interval = kwargs.get('tick_interval', .04)
        #self.tick_granularity = len(str(self.tick_interval).split('.')[1])
        self.seconds = None
        self.starttime = None
        callbacks = kwargs.get('callbacks', [])
        self.running = False
        self.timer_id = None
        self.timer = None
        self.tick_listener = None
        self.callbacks = set()
        self.callbacks_to_delete = set()
        self.callback_threads = {}
        self.raw_tick_callbacks = set()
        #self.callback_triggers = {}
        for cb in callbacks:
            self.add_callback(cb)
        #self.ticks = 0
        
    def start(self):
        self.stop()
        self.running = True
        self._build_timer()
        
    def stop(self, blocking=False):
        self.running = False
        self._kill_timer(blocking)
        self.timer_id = None
        #self.ticks = 0
    
    def add_callback(self, callback, threaded=False):
        #p = WeakPartial(callback, self._on_WeakPartial_dead)
        if not threaded:
            self.callbacks.add(callback)
            print 'masterclock callback <%s> added: %s' % (callback, self.callbacks)
            return
        obj = callback.im_self
        cbid = '%s-%s' % (callback.im_func.__name__, id(obj))
        if cbid in self.callback_threads:
            return
        t = ThreadedCallback(clock=self, callback=callback)
        #e = t.trigger
        self.callback_threads[cbid] = t
        #self.callback_triggers[callback] = t.trigger
        t.start()
        
    def del_callback(self, callback, blocking=False):
        print 'masterclock del_callback %s, %s' % (callback, self.callbacks)
        self.callbacks_to_delete.add(callback)
        if not blocking:
            return
        cbThread = self.callback_threads.get(id(callback))
        if not cbThread:
            return
        cbThread._stopped.wait()
        
    def _on_WeakPartial_dead(self, p):
        print 'MASTERCLOCK weakpartial %s dead' % (p)
        
    def add_raw_tick_callback(self, cb):
        self.raw_tick_callbacks.add(cb)
        
    def del_raw_tick_callback(self, cb):
        self.callbacks_to_delete.add(cb)
        
    def _do_remove_callbacks(self):
        to_delete = self.callbacks_to_delete
        callbacks = self.callbacks
        callback_threads = self.callback_threads
        if not len(to_delete):
            return
        for cb in to_delete:
            callbacks.discard(cb)
            obj = cb.im_self
            cbid = '%s-%s' % (cb.im_func.__name__, id(obj))
            if cbid in callback_threads:
                callback_threads[cbid].stop()
                del callback_threads[cbid]
            self.raw_tick_callbacks.discard(cb)
                #del self.callback_triggers[cb]
        #if len(self.callbacks) == 0:
        #    self.stop()
        print 'masterclock removed callbacks %s, %s, %s' % (to_delete, callbacks, callback_threads.keys())
        self.callbacks_to_delete.clear()
        
    def do_callbacks(self):
        seconds = self.seconds
        for t in self.callback_threads.itervalues():
            t.trigger(self, seconds)
        for cb in self.callbacks:
            cb(self, seconds)
            
    def on_timer(self, *args):
        self.now = self.get_now()
        seconds = self.calc_seconds(self.now)
        self.clock_seconds = seconds
        self._do_remove_callbacks()
        if self.seconds is None:
            cs = seconds - int(seconds)
            for i in range(int(1 / self.tick_interval)):
                ts = i * self.tick_interval
                if ts >= cs:
                    self.seconds = int(seconds) + ts
                    break
        for cb in self.raw_tick_callbacks:
            cb(self, seconds)
        tickseconds = self.seconds
        if tickseconds is not None and seconds < tickseconds + self.tick_interval:
            return
        if tickseconds is None:
            return
        self.do_tick_increment()
        self.emit('tick', clock=self, seconds=self.seconds)
        try:
            self.do_callbacks()
        except:
            pass
            #print sys.exc_info()
        
    def do_tick_increment(self):
        self.seconds += self.tick_interval
        
    def _build_timer(self):
        self.timer = Ticker(interval=self.clock_interval, callback=self.on_timer, clock=self)
        self.starttime = self.get_now()
        self.now = self.starttime
        self.timer.start()
        
    def _kill_timer(self, blocking=False):
        if self.tick_listener is not None:
            self.tick_listener.stop(blocking=blocking)
            self.tick_listener = None
        if self.timer is not None:
            self.timer.stop(blocking=blocking)
            self.timer = None
            
class DatetimeClock(BaseClock):
    def calc_seconds(self, dt):
        midnight = datetime.datetime.combine(dt.date(), datetime.time())
        td = dt - midnight
        return td.seconds + (td.microseconds / float(10**6))
    def get_now(self):
        return datetime.datetime.now()
        
class SysTimeClock(BaseClock):
    def get_now(self):
        return time.time()
    def calc_seconds(self, seconds):
        return seconds
        
class IncrementorClock(SysTimeClock):
    time_struct_keys = {'tm_sec':'second', 'tm_min':'minute', 'tm_hour':'hour'}
    def __init__(self, **kwargs):
        incrementor_group = kwargs.get('incrementor_group')
        if not incrementor_group:
            hour = {'resolution':60}
            minute = {'resolution':60, 'children':{'hour':hour}}
            sec = {'resolution':60, 'children':{'minute':minute}}
            ms = {'resolution':100, 'children':{'second':sec}}
            d = {'millisecond':ms}
            incrementor_group = IncrementorGroup(incrementors=d)
        self.incrementor_group = incrementor_group
        root = incrementor_group.root_incrementor
        tickint = 1. / root.resolution
        kwargs['tick_interval'] = tickint
        kwargs['clock_interval'] = tickint
        super(IncrementorClock, self).__init__(**kwargs)
#    @property
#    def seconds(self):
#        return self.incrementor_group.root_incrementor.get_root_sum()
#    @seconds.setter
#    def seconds(self, value):
#        if value is None:
#            return
#        self.incrementor_group.root_incrementor.set_root_sum(value)
    def do_tick_increment(self):
        #self.incrementor_group.root_incrementor += 1
        now = self.now
        start = self.starttime
        self.seconds = now - start
        tstruct = time.localtime(now)
        incrgroup = self.incrementor_group
        root = incrgroup.root_incrementor
        root.value = int(round(now - (int(now)) * root.resolution))
        
        for tmkey, inckey in self.time_struct_keys.iteritems():
            value = getattr(tstruct, tmkey)
            setattr(incrgroup, inckey, value)
        
class Ticker(BaseThread):
    _Events = {'ticking':{}}
    _Properties = {'interval':dict(type=float)}
    def __init__(self, **kwargs):
        clock = kwargs.get('clock')
        kwargs['thread_id'] = '%s-%s_Ticker' % (clock.__class__.__name__, clock.clock_index)
        kwargs['disable_threaded_call_waits'] = True
        super(Ticker, self).__init__(**kwargs)
        self.bind(interval=self._on_interval_set)
        self.interval = kwargs.get('interval')
        self.callback = kwargs.get('callback', self._default_callback)
        #self._threaded_call_ready.wait_timeout = None
        
    def _thread_loop_iteration(self):
        if not self._running:
            return
        time.sleep(self.interval)
        self.ticking.set()
        self.callback()
        self.ticking.clear()
        
    def _on_interval_set(self, **kwargs):
        pass
        #self._threaded_call_ready.wait_timeout = self.interval
        
    def _default_callback(self):
        pass
        
class oldTicker(threading.Thread):
    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.interval = kwargs.get('interval')
        self.callback = kwargs.get('callback', self._default_callback)
        self.running = threading.Event()
        self.waiting = threading.Event()
        self.ticking = threading.Event()
        
    def run(self):
        interval = self.interval
        callback = self.callback
        running = self.running
        waiting = self.waiting
        ticking = self.ticking
        running.set()
        while running.isSet():
            if not running.isSet():
                return
            #waiting.wait(interval)
            time.sleep(interval)
            ticking.set()
            callback()
            
    def stop(self):
        self.running.clear()
        
    def _default_callback(self):
        pass
        

class ThreadedCallback(BaseThread):
    def __init__(self, **kwargs):
        self.clock = kwargs.get('clock')
        self.callback = kwargs.get('callback')
        kwargs['thread_id'] = '%s-%s_ThreadedCallback-%s' % (self.clock.__class__.__name__, self.clock.clock_index, str(self.callback))
        super(ThreadedCallback, self).__init__(**kwargs)
    def trigger(self, clock, seconds):
        self.insert_threaded_call(self.callback, clock, clock.seconds)
    def stop(self, **kwargs):
        kwargs['wait_for_queues'] = False
        super(ThreadedCallback, self).stop(**kwargs)
        
class oldThreadedCallback(threading.Thread):
    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.running = threading.Event()
        self._trigger_event = threading.Event()
        self.clock = kwargs.get('clock')
        self.callback = kwargs.get('callback')
    def run(self):
        clock = self.clock
        self.running.set()
        while self.running.isSet():
            self._trigger_event.wait()
            if self.running.isSet():
                self.callback(clock, clock.seconds)
            self._trigger_event.clear()
    def stop(self):
        self.running.clear()
        self._trigger_event.set()
    def trigger(self, clock, seconds):
        #print seconds
        #self.seconds = seconds
        self._trigger_event.set()
        

#MasterClock = DatetimeClock
MasterClock = SysTimeClock
#MasterClock = IncrementorClock

if __name__ == '__main__':
    class Tester(object):
        def __init__(self, name, clock, duration=5):
            self.name = name
            self.clock = clock
            self.duration = duration
            self.starttime = None
            self.clockstart = None
            self.tickstart = None
            self.stopping = False
            self.clock_data = []
            self.tick_data = []
            self.clock.add_raw_tick_callback(self.on_raw_tick)
            self.clock.add_callback(self.on_tick)
            self.clock.start()
        def on_raw_tick(self, clock, seconds):
            now = time.time()
            if self.starttime is None:
                self.starttime = now
                self.clockstart = seconds
            if self.stopping:
                return
            time_elapsed = now - self.starttime
            clock_elapsed = seconds - self.clockstart
            self.clock_data.append([time_elapsed, clock_elapsed])
            #print 'time=%010.6f, clock=%010.6f, diff=%010.6f' % (time_elapsed, clock_elapsed, time_elapsed - clock_elapsed)
            if time_elapsed < self.duration:
                return
            self.stop()
        def on_tick(self, clock, seconds):
            now = time.time()
            if self.tickstart is None:
                self.tickstart = now
                self.firsttick = seconds
            time_elapsed = now - self.tickstart
            tickoffset = seconds - self.firsttick
            self.tick_data.append([time_elapsed, tickoffset])
        def stop(self):
            def calc_diff(l):
                return [item[0] - item[1] for item in l]
            def calc_avg(l):
                s = 0
                for num in l:
                    s += num
                return s / len(l)
            self.stopping = True
            self.clock_diff = calc_diff(self.clock_data)
            self.clock_avg = calc_avg(self.clock_diff)
            self.tick_diff = calc_diff(self.tick_data)
            self.tick_avg = calc_avg(self.tick_diff)
            keys = ['data', 'diff', 'avg']
            self.all_data = {'clock':{}, 'tick':{}}
            for key, val in self.all_data.iteritems():
                attrkeys = ['_'.join([key, attr]) for attr in keys]
                val.update(dict(zip(attrkeys, [getattr(self, akey) for akey in attrkeys])))
            self.clock.stop()
    cdata = []
    #c = DatetimeClock()
    #t = Tester('master', c)
    #c.timer.join()
    #cdata.append(t.all_data)
    c = SysTimeClock()
    t = Tester('nodattime', c)
    c.timer.join()
    cdata.append(t.all_data)
    c = IncrementorClock()
    t = Tester('incrementor', c)
    c.timer.join()
    cdata.append(t.all_data)
#    print 'clock_avg: ', ['%010.8f' % (data['clock']['clock_avg']) for data in cdata]
#    print 'tick_avg: ', ['%010.8f' % (data['tick']['tick_avg']) for data in cdata]
#    print 'clock_min: ', ['%010.8f' % (min([diff for diff in data['clock']['clock_diff']])) for data in cdata]
#    print 'clock_max: ', ['%010.8f' % (max([diff for diff in data['clock']['clock_diff']])) for data in cdata]
#    print 'tick_min:  ', ['%010.8f' % (min([diff for diff in data['tick']['tick_diff']])) for data in cdata]
#    print 'tick_max:  ', ['%010.8f' % (max([diff for diff in data['tick']['tick_diff']])) for data in cdata]
