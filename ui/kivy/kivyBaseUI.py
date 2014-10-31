from kivy.app import App as _KVApp
from kivy.clock import Clock as _KVClock

from Bases import BaseThread
from .. import BaseUI

from bases import widgets

class Application(BaseUI.Application):
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = GUIThread(Application=self)
        super(Application, self).__init__(**kwargs)
        self._app_running = False
        self._application = KivyApp(Application=self)
        self._application.bind(on_stop=self.on_mainwindow_close)
    def start_GUI_loop(self, *args):
        self._application.run()
    def stop_GUI_loop(self):
        running = self._app_running
        self._app_running = False
        if running:
            self._application.stop()
    
class KivyApp(_KVApp):
    def __init__(self, **kwargs):
        super(KivyApp, self).__init__(**kwargs)
        self.Application = kwargs.get('Application')
        self._app_name = self.Application.name
        self.title = self.Application.name
        self.Application.bind(name=self.on_Application_name_set)
        
    def build(self):
        return widgets.VBox()
    def on_start(self):
        super(KivyApp, self).on_start()
        mw = getattr(self.Application, 'mainwindow', None)
        if mw is None:
            return
        mw.init_build(self)
        self.Application._app_running = True
    def on_Application_name_set(self, **kwargs):
        name = kwargs.get('value')
        self.title = name
        self._app_name = name

class GUIThread(BaseThread):
    def __init__(self, **kwargs):
        kwargs['thread_id'] = 'GUIThread'
        #kwargs['AllowedEmissionThreads'] = ['MainThread']
        self.Application = kwargs.get('Application')
        super(GUIThread, self).__init__(**kwargs)
        #self._threaded_call_ready.wait_timeout = None
    def insert_threaded_call(self, call, *args, **kwargs):
        if not self.Application._app_running:
            call(*args, **kwargs)
            return
        print 'guithread insert call: ', call
        super(GUIThread, self).insert_threaded_call(call, *args, **kwargs)
    def _really_do_call(self, p):
        if not self.Application._app_running:
            p()
            return
        print 'guithread insert to kvclock: ', p
        _KVClock.schedule_once(p, -1)
    
class BaseWindow(BaseUI.BaseWindow):
    def __init__(self, **kwargs):
        self.window = None
        super(BaseWindow, self).__init__(**kwargs)
    def init_build(self, app):
        self.app = app
        self.window = app._app_window
        self.window.system_size = self.size
        self.window.bind(fullscreen=self.on_window_fullscreen, 
                         system_size=self.on_window_system_size)
    def on_window_fullscreen(self, *args, **kwargs):
        value = self.window.fullscreen
        if type(value) == bool and value != self.fullscreen:
            self.fullscreen = value
    def on_window_system_size(self, *args, **kwargs):
        value = self.window.system_size
        #print 'WINDOW SIZE: ', value
        if value != self.size:
            self.size = value
    def _on_own_property_changed(self, **kwargs):
        w = self.window
        if w is None:
            return
        prop = kwargs.get('Property')
        value = kwargs.get('value')
        keys = ['title', 'fullscreen']
        propmap = {'title':'title', 'size':'system_size', 'fullscreen':'fullscreen'}
        if prop.name in propmap:
            attr = propmap[prop.name]
            if getattr(w, attr) != value:
                setattr(w, attr, value)
        
