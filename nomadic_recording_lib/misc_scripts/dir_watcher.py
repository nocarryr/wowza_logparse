#! /usr/bin/env python

import time
import weakref
import os.path
import argparse

import pyinotify


LOG_START_TS = None
LOG_FILENAME = os.path.join(os.getcwd(), 'dir_watcher.log')

def LOG(*args):
    global LOG_START_TS
    if LOG_START_TS is None:
        LOG_START_TS = time.time()
    ts = time.time() - LOG_START_TS
    line = '%013.6f - %s\n' % (ts, ' '.join([str(arg) for arg in args]))
    with open(LOG_FILENAME, 'a') as f:
        f.write(line)

class Signal(object):
    def __init__(self, **kwargs):
        self.name = kwargs.get('name')
        self.parent = kwargs.get('parent')
        self.value = kwargs.get('value')
        self.listeners = weakref.WeakValueDictionary()
    def bind(self, method):
        obj_id = id(method.im_self)
        wrkey = (method.im_func, obj_id)
        self.listeners[wrkey] = method.im_self
    def unbind(self, *args):
        listeners = self.listeners
        r = False
        for arg in args:
            if not hasattr(arg, 'im_self'):
                for wrkey in listeners.keys()[:]:
                    if listeners.get(wrkey) == arg:
                        del listeners[wrkey]
                        r = True
            else:
                wrkey = (arg.im_func, id(arg.im_self))
                if wrkey in listeners:
                    del listeners[wrkey]
                    r = True
        return r
    def unbind_all(self):
        self.listeners.clear()
    def emit(self, **kwargs):
        kwargs['signal'] = self
        listeners = self.listeners
        for key in listeners.keys()[:]:
            f, obj_id = key
            obj = listeners.get(key)
            if obj is None:
                continue
            r = f(obj, **kwargs)
            if r is False:
                del listeners[key]
class WatchedFile(object):
    def __init__(self, **kwargs):
        self.filename = kwargs.get('filename')
        self.dirname = kwargs.get('dirname')
        self.ready = Signal(name='ready', parent=self, value=False)
    @property
    def full_path(self):
        return os.path.join(self.dirname, self.filename)
    def unlink(self):
        self.ready.unbind_all()
    def set_ready(self, value=True):
        if self.ready.value == value:
            return
        self.ready.value = value
        self.ready.emit()
class WatchedDir(object):
    def __init__(self, **kwargs):
        self._notifier = None
        self.dirname = kwargs.get('dirname')
        self.new_file = Signal(name='new_file', parent=self)
        self.file_ready = Signal(name='file_ready', parent=self)
        self.files = {}
        self.notifier = kwargs.get('notifier')
    @property
    def notifier(self):
        return self._notifier
    @notifier.setter
    def notifier(self, value):
        def unlink_old(n):
            if n.callback == self.handle_event:
                n.callback = None
        if self._notifier is not None:
            unlink_old(self._notifier)
        elif value is None:
            unlink_old(self._notifier)
        self._notifier = value
        if value is not None:
            if self.dirname is None:
                self.dirname = value.path
            value.callback = self.handle_event
    def run(self):
        n = self.notifier
        if n is None:
            return
        n.run()
    def stop(self):
        n = self.notifier
        if n is None:
            return
        n.stop()
    def unlink(self):
        self.new_file.unbind_all()
        self.file_ready.unbind_all()
    def add_file(self, filename):
        if filename in self.files:
            self.files[filename].set_ready(False)
        LOG('adding file: %s' % (filename))
        f = WatchedFile(filename=filename, dirname=self.dirname)
        f.ready.bind(self.on_file_ready)
        self.files[filename] = f
        self.new_file.emit(file=f)
    def set_file_ready(self, filename):
        if filename not in self.files:
            self.add_file(filename)
        self.files[filename].set_ready()
    def on_file_ready(self, **kwargs):
        s = kwargs.get('signal')
        if not s.value:
            return
        LOG('file_ready: %s' % (s.parent.filename))
        self.file_ready.emit(file=s.parent)
    def handle_event(self, event):
        if event.path != self.dirname:
            return
        if event.mask == pyinotify.IN_CREATE:
            self.add_file(event.name)
        elif event.mask == pyinotify.IN_CLOSE_WRITE:
            self.set_file_ready(event.name)

class EventHandler(pyinotify.ProcessEvent):
    def my_init(self, **kwargs):
        self.callback = kwargs.get('callback')
    def process_default(self, event):
        cb = self.callback
        if cb is None:
            return
        cb(event)

def build_mask(*args):
    mask = 0
    for arg in args:
        if isinstance(arg, basestring):
            arg = getattr(pyinotify, arg)
        mask |= arg
    return mask
    
class Notifier(object):
    def __init__(self, **kwargs):
        self._callback = None
        self.wm = pyinotify.WatchManager()
        self.mask = kwargs.get('mask', 0)
        events = kwargs.get('events')
        if events:
            if type(events) not in [list, tuple, set]:
                events = [events]
            self.mask |= build_mask(*events)
        self.path = kwargs.get('path')
        self.handler = EventHandler(callback=self.callback)
        self.callback = kwargs.get('callback')
        self.notifier = self.build_notifier()
        self.wm.add_watch(self.path, self.mask)
    @property
    def callback(self):
        return self._callback
    @callback.setter
    def callback(self, value):
        self._callback = value
        self.handler.callback = value
    def build_notifier(self):
        return pyinotify.Notifier(self.wm, self.handler)
    def run(self):
        self.notifier.loop()
    def stop(self):
        self.notifier.stop()
class ThreadedNotifier(Notifier):
    def build_notifier(self):
        n = pyinotify.ThreadedNotifier(self.wm, self.handler)
        n.start()
        return n
    def run(self):
        pass
    
def build_notifier(**kwargs):
    wm = pyinotify.WatchManager()
    mask = kwargs.get('mask', 0)
    events = kwargs.get('events')
    if events:
        if type(events) not in [list, tuple, set]:
            events = [events]
        mask |= build_mask(*events)
    path = kwargs.get('path')
    callback = kwargs.get('callback')
    run_loop = kwargs.get('run_loop', True)
    handler = EventHandler(callback=callback)
    notifier = pyinotify.Notifier(wm, handler)
    wm.add_watch(path, mask)
    if run_loop:
        notifier.loop()
    else:
        return {'handler':handler, 'notifier':notifier}
    
def watch_dir(**kwargs):
    path = kwargs.get('path')
    threaded = kwargs.get('threaded', False)
    if threaded:
        ncls = ThreadedNotifier
    else:
        ncls = Notifier
    events = ['IN_CREATE', 'IN_CLOSE_WRITE']
    notifier = ncls(events=events, path=path)
    watched_dir = WatchedDir(notifier=notifier)
    return watched_dir

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('-p', dest='path')
    p.add_argument('--logfile', dest='logfile')
    p.add_argument('-e', dest='events', action='append')
    args, remaining = p.parse_known_args()
    o = vars(args)
    if not o.get('path'):
        o['path'] = os.getcwd()
    if o.get('logfile'):
        LOG_FILENAME = o['logfile']
    if not o.get('events'):
        o['events'] = 'IN_CLOSE_WRITE'
    mask = 0
    for event in o['events']:
        mask |= getattr(pyinotify, event)
    o['mask'] = mask
    build_notifier(**o)
