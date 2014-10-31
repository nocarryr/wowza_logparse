import sys
import threading
import signal
import gobject, glib

from pipeline import Pipeline

#_KeyboardInterrupt = KeyboardInterrupt
#
#class KeyboardInterrupt(_KeyboardInterrupt):
#    def __init__(self, *args):
#        print 'INTERCEPTED!'
#        _KeyboardInterrupt.__init__(self, *args)
        
class Launcher(threading.Thread):
    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.stopped = threading.Event()
        self.pipeline = kwargs.get('pipeline')
        self.stop_callback = kwargs.get('stop_callback', self._stop_callback)
        self.pipeline.bind(pipeline_state=self.on_pipeline_state_changed)
        signal.signal(signal.SIGINT, self.stop)
    def on_pipeline_state_changed(self, **kwargs):
        value = kwargs.get('value')
        if value in ['null']:
            self.stopped.set()
    def run(self):
        self.pipeline.start()
        self.stopped.wait()
        self.pipeline.stop()
        self.stop_callback()
    def stop(self, *args):
        print threading.currentThread(), 'caught sigint'
        signal.siginterrupt(signal.SIGINT, True)
        self.pipeline.stop()
    def _stop_callback(self):
        pass

def gtk_launcher(**kwargs):
    pipeline = Pipeline(**kwargs)
    return pipeline
    
class cliLauncher(object):
    def __init__(self, **kwargs):
        self.pipeline = kwargs.get('pipeline')
        if self.pipeline is None:
            self.pipeline = Pipeline(**kwargs)
        self.launcher = Launcher(pipeline=self.pipeline, stop_callback=self.on_launcher_end)
    def launch(self):
        self.launcher.start()
        gobject.threads_init()
        self.loop = glib.MainLoop()
        try:
            self.loop.run()
        except KeyboardInterrupt:
            pass
    def on_launcher_end(self):
        self.loop.quit()
        sys.exit(0)
    
if __name__ == '__main__':
    #elems = [{'gst_name':'videotestsrc'}, {'gst_name':'xvimagesink'}]
    elems = ['videotestsrc', 'xvimagesink']
    cliLauncher(element_data=elems).launch()
