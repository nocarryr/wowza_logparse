import time
from comm.CommDispatcher import CommDispatcherBase


class CommDispatcher(CommDispatcherBase):
    def __init__(self, **kwargs):
        super(CommDispatcher, self).__init__(**kwargs)
        self.GLOBAL_CONFIG['app_name'] = 'teststuff'
        self.osc_io = self.build_io_module('osc')
        self.midi_io = self.build_io_module('midi')
        self.artnet = self.build_io_module('dmx.Artnet')
    def do_connect(self):
        self.osc_io.do_connect()
        self.artnet.do_connect()
        self.midi_io.do_connect()
        super(CommDispatcher, self).do_connect()
    def shutdown(self):
        self.midi_io.do_disconnect(blocking=True)
        self.osc_io.shutdown()
        self.artnet.do_disconnect(blocking=True)
        super(CommDispatcher, self).shutdown()

comm = CommDispatcher()
#print comm.IO_MODULES
comm.do_connect()
time.sleep(15.)
comm.shutdown()

