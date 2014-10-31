import time
import threading
import collections
import traceback

from Bases import BaseObject, BaseThread, Partial
from .. import BaseUI

from bases.ui_modules import fltk

class Application(BaseUI.Application):
    def __init__(self, **kwargs):
        self.GUIThread = get_gui_thread()
        kwargs['ParentEmissionThread'] = self.GUIThread
        super(Application, self).__init__(**kwargs)
        self.MainLoop = MainLoop(Application=self)
        self.GUIThread.MainLoop = self.MainLoop
        #self.GUIThread.bind(_stopped=self.on_GUIThread_stopped)
        self.MainLoop.bind(stopped=self.on_MainLoop_stopped)
    def start_GUI_loop(self, join=False):
        self.MainLoop.run()
#        self.GUIThread.gui_running = True
#        if not join:
#            return
#        self.GUIThread.join()
        self.stop_GUI_loop()
        self.on_MainLoop_stopped()
    def stop_GUI_loop(self):
        #self.GUIThread.gui_running = False
        self.GUIThread.stop(blocking=True)
        self.MainLoop.stop()
    def on_MainLoop_stopped(self, **kwargs):
        self.emit('exit')
        
class MainLoop(BaseObject):
    _Properties = {'running':dict(default=False), 
                   'stopped':dict(default=False)}
    def __init__(self, **kwargs):
        super(MainLoop, self).__init__(**kwargs)
        self.Application = kwargs.get('Application')
        self.awake_partials = collections.deque()
    def run(self):
        print 'mainloop starting'
        self.running = True
        #fltk.Fl_run()
        #counter = 0
        try:
            while self.running:
                fltk.Fl_check()
                #print 'Fl_check count: ', counter
                #counter += 1
                if False:#self.running and len(self.awake_partials):
                    p = self.awake_partials.popleft()
                    p()
                else:
                    time.sleep(.1)
        except KeyboardInterrupt:
            self.running = False
        except:
            traceback.print_exc()
        self.stopped = True
    def stop(self):
        self.running = False
    def inject_call(self, call, *args, **kwargs):
        p = Partial(call, *args, **kwargs)
        self.awake_partials.append(p)
        #if self.running:
        #    fltk.Fl_awake()

class GUIThread(BaseThread):
    def __init__(self, **kwargs):
        kwargs['thread_id'] = 'GUIThread'
        self.MainLoop = None
        self.gui_running = False
        super(GUIThread, self).__init__(**kwargs)
        self.register_signal('no_windows')
    def insert_threaded_call(self, call, *args, **kwargs):
        if not self.MainLoop:
            return
        if threading.currentThread().name == 'MainThread':
            call(*args, **kwargs)
        else:
            self.MainLoop.inject_call(call, *args, **kwargs)
#    def _thread_loop_iteration(self):
#        if not self.gui_running:
#            return
#        r = fltk.Fl_check()
#        if r == 0:
#            if not self._running:
#                return
#            self.emit('no_windows')
#            self.stop(blocking=False)
        
_gui_thread = GUIThread()
_gui_thread.start()
BaseObject().GLOBAL_CONFIG['GUIThread'] = _gui_thread

def get_gui_thread():
    return _gui_thread
        
from bases import widgets

class BaseWindow(BaseUI.BaseWindow):
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = get_gui_thread()
        self._updating_dimensions = False
        super(BaseWindow, self).__init__(**kwargs)
    def _build_window(self, **kwargs):
        args = [40, 40]
        args.extend(self.size[:])
        args.append(self.title)
        w = widgets.Window(*args)
        #w.end()
        #w.connect('resize', self._on_window_resize)
        return w
        
    def _update_window_dimensions(self):
        self._updating_dimensions = True
        d = {'position':['x', 'y'], 'size':['w', 'h']}
        for attr, keys in d.iteritems():
            value = [getattr(self.window, key)() for key in keys]
            if value == getattr(self, attr):
                continue
            setattr(self, attr, value)
        self._updating_dimensions = False
        
    def _on_own_property_changed(self, **kwargs):
        return
        prop = kwargs.get('Property')
        value = kwargs.get('value')
        print 'Basewindow propchange: ', kwargs
        if value is None:
            return
        if prop.name == 'size':
            if self._updating_dimensions:
                return
            self.window.size(*value)
        elif prop.name == 'title':
            self.window.label(value)
        elif prop.name == 'fullscreen':
            if value:
                #self._update_window_dimensions()
                self.window.fullscreen()
            else:
                args = self.position[:] + self.size[:]
                self.window.fullscreen_off(*args)
                
    def _on_window_resize(self, **kwargs):
        self._updating_dimensions = True
        for key in ['position', 'size']:
            value = list(kwargs.get(key))
            setattr(self, key, value)
            print key, value, getattr(self, key)
        self._updating_dimensions = False
