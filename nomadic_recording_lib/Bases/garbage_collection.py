import gc

from threadbases import BaseThread

GLOBAL_CONFIG_KEY = 'USE_BASEOBJECT_GARBAGE_COLLECTOR'

def build_cls():
    class GCCollectThread(BaseThread):
        _Events = {'queue_collection':{}, 
                   'enable_collection':{}, 
                   'collecting':{}, 
                   'wait_for_collection':dict(wait_timeout=1.)}
        def __init__(self, **kwargs):
            kwargs.setdefault('thread_id', 'GARBAGE_COLLECTOR')
            super(GCCollectThread, self).__init__(**kwargs)
            self.enable_collection = True
        def _thread_loop_iteration(self):
            if not self.enable_collection:
                return
            self.wait_for_collection.wait()
            if self.queue_collection:
                self.do_collect()
                self.queue_collection = False
            self.wait_for_collection = False
        def do_collect(self):
            self.collecting = True
            r = gc.collect()
            #print 'gc result: ',  r
            self.collecting = False
    return GCCollectThread
    
class GarbageCollector(object):
    def __init__(self, **kwargs):
        self.GLOBAL_CONFIG = kwargs.get('GLOBAL_CONFIG')
        self.gc_thread = None
        self.gc_thread_cls = None
        self.on_global_config_update()
        self.GLOBAL_CONFIG.bind(update=self.on_global_config_update)
    @property
    def running(self):
        if self.gc_thread is None:
            return False
        return self.gc_thread._running
    @property
    def _running(self):
        return self.running
    @property
    def enable_collection(self):
        if self.gc_thread is None:
            return False
        return self.gc_thread.enable_collection
    @enable_collection.setter
    def enable_collection(self, value):
        if self.gc_thread is None:
            return
        self.gc_thread.enable_collection = value
    @property
    def queue_collection(self):
        if self.gc_thread is None:
            return False
        return self.gc_thread.queue_collection
    @queue_collection.setter
    def queue_collection(self, value):
        if self.gc_thread is None:
            return
        self.gc_thread.queue_collection = value
    @property
    def wait_for_collection(self):
        if self.gc_thread is None:
            return False
        return self.gc_thread.wait_for_collection
    @wait_for_collection.setter
    def wait_for_collection(self, value):
        if self.gc_thread is None:
            return
        self.gc_thread.wait_for_collection = value
    def do_collect(self):
        if self.gc_thread is None:
            return
        self.gc_thread.do_collect()
    def build_collector(self):
        self.kill_collector()
        if self.gc_thread_cls is None:
            self.gc_thread_cls = build_cls()
        self.gc_thread = self.gc_thread_cls()
        self.gc_thread.start()
    def kill_collector(self):
        if self.gc_thread is None:
            return
        if self.gc_thread.isAlive():
            self.gc_thread.stop(blocking=True)
        self.gc_thread = None
    def on_global_config_update(self, **kwargs):
        gc_enable = self.GLOBAL_CONFIG.get(GLOBAL_CONFIG_KEY)
        if gc_enable and not self.running:
            self.build_collector()
        if not gc_enable:
            self.kill_collector()
    def stop(self, **kwargs):
        self.kill_collector()
