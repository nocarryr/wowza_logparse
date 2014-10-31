import threading
import collections

import portmidizero

from midi_io import MidiIO, MidiIn, MidiOut

class pmzMidiIO(MidiIO):
    def __init__(self, **kwargs):
        portmidizero.Initialize()
        self.io_device_classes = {'in':pmzMidiIn, 'out':pmzMidiOut}
        super(pmzMidiIO, self).__init__(**kwargs)
        
    def get_info(self):
        l = []
        for i in range(portmidizero.CountDevices()):
            l.append(portmidizero.GetDeviceInfo(i))
        #print 'pmz info: ', l
        return l

class pmzMidiIn(MidiIn):
    def build_device(self, **kwargs):
        return portmidizero.Input(self.dev_info.index)
    @property
    def can_read(self):
        return self.device.Poll()
    def get_data(self):
        return self.device.Read(20)
    def _on_state_set(self, **kwargs):
        state = kwargs.get('value')
        if state:
            self.listener = Listener(device=self)
            self.listener.start()
        else:
            if self.listener is not None:
                self.listener.stop()
            self.listener = None
    
class pmzMidiOut(MidiOut):
    def build_device(self, **kwargs):
        return portmidizero.Output(self.dev_info.index, 1)
        
    def send(self, **kwargs):
        data = kwargs.get('data')
        timestamp = kwargs.get('timestamp', 0)
        sysex = kwargs.get('sysex')
        if not self.state:
            return
        if sysex is not None:
            #self.device.write_sys_ex(timestamp, sysex)
            pass
        else:
            self.device.Write([[data, timestamp]])
            
            
class Listener(threading.Thread):
    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.device = kwargs.get('device')
        self.poll_timeout = .1
        self.running = threading.Event()
        self.processing = threading.Event()
        self.queue = collections.deque()
        
    def add_buffer(self, buffer):
        self.queue.append(buffer)
        self.processing.set()
        
    def run(self):
        self.running.set()
        while self.running.isSet():
            pollwait = self.processing.wait(self.poll_timeout)
            if self.running.isSet():
                if not pollwait:
                    if self.device.can_read:
                        buffer = self.device.get_data()
                        for data in buffer:
                            self.add_buffer(data)
                self.process_next_buffer()
                
    def stop(self):
        self.running.clear()
        self.processing.set()
        
    def process_next_buffer(self):
        if not len(self.queue):
            self.processing.clear()
            return
        buffer = self.queue.popleft()
        for data in buffer:
            self.device.parse_midi_message(data=data[0], timestamp=data[1])
            
    
