import os, sys
import array
import collections
import threading
import time

from pygame import midi as pm


#from SignalDispatcher import SignalDispatcher
#import SignalDispatcher

from Bases import SignalDispatcher, ChildGroup
from Bases.misc import hexstr

from midi_io import MidiIO, MidiIn, MidiOut
import messages


class PyGameThread(threading.Thread):
    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.active_inputs = {}
        self.input_poll_time = .1
        self.running = threading.Event()
        self.active = threading.Event()
        self.queue = collections.deque()
    def add_to_queue(self, cb, *args, **kwargs):
        self.queue.append((cb, args, kwargs))
        self.active.set()
    def add_active_input(self, **kwargs):
        input_id = kwargs.get('id')
        device = kwargs.get('device')
        cb = kwargs.get('callback')
        needs_activate = len(self.active_inputs) == 0
        self.active_inputs[input_id] = (device, cb)
        if needs_activate:
            self.active.set()
    def del_active_input(self, key):
        if key not in self.active_inputs:
            return
        del self.active_inputs[key]
    def run(self):
        pm.init()
        self.running.set()
        while self.running.isSet():
            if len(self.active_inputs):
                flag = self.active.wait(self.input_poll_time)
            else:
                flag = self.active.wait()
            if self.running.isSet():
                self.do_next_item()
                if not flag:
                    self.check_inputs()
    def stop(self):
        self.active_inputs.clear()
        self.running.clear()
        self.active.set()
    def do_next_item(self):
        if not len(self.queue):
            self.active.clear()
            return
        cb, args, kwargs = self.queue.popleft()
        cb(*args, **kwargs)
    def check_inputs(self):
        for key in self.active_inputs.keys()[:]:
            if key not in self.active_inputs:
                continue
            device, cb = self.active_inputs.get(key)
            if device.poll():
                cb()
        
class PyGameMidiIO(MidiIO):
    #_Properties = {'detected_inputs':dict(default={}),
    #               'detected_outputs':dict(default={})}
    io_device_classes = {'in':pygmMidiIn, 'out':pygmMidiOut}
    def __init__(self, **kwargs):
        super(PyGameMidiIO, self).__init__(**kwargs)
        
        #pm.init()
        self.pygame_thread = PyGameThread()
        self.pygame_thread.start()
        self.pygame_thread.running.wait()
        
        
    
    
    
    def get_info(self):
        l = []
        for x in range(pm.get_count()):
            l.append(pm.get_device_info(x))
            #dev = DeviceInfo(Index=x, info=pm.get_device_info(x))
            #self.dev_info[dev.type].add_child(existing_object=dev)
            #dev.bind(active=self.on_dev_info_active_set)
        return l
                
    
    

class pygmMidiOut(MidiOut):
    def build_device(self, **kwargs):
        return pm.Output(self.dev_info.index)
        
    def send(self, **kwargs):
        data = kwargs.get('data')
        timestamp = kwargs.get('timestamp', 0)
        #if timestamp is None:
        #    timestamp = pm.time()
        sysex = kwargs.get('sysex')
        if not self.state:
            return
        if sysex is not None:
            #self.device.write_sys_ex(timestamp, sysex)
            pass
        else:
            #self.device.write([[data, timestamp]])
            #self.buffer.add_message([[data, timestamp]])
            self.midi_io.pygame_thread.add_to_queue(self.device.write, [[data, timestamp]])
        
class pygmMidiIn(MidiIn):
    def __init__(self, **kwargs):
        super(pygmMidiIn, self).__init__(**kwargs)
        self.listener = None
        #self.bind(state=self._on_state_set)
        
    def build_device(self, **kwargs):
        return pm.Input(self.dev_info.index)
        
    def on_data_received(self, **kwargs):
        #print hexstr(kwargs.get('data'))
        self.emit('data_received', **kwargs)
        
    #def on_msg_received(self, **kwargs):
    #    self.emit('msg_received', **kwargs)
    
    def _on_state_set(self, **kwargs):
        state = kwargs.get('value')
        if state:
            #self.listener = Listener(device=self.device)
            #self.listener.connect('msg_received', self.on_msg_received)
            #self.listener.start()
            self.midi_io.pygame_thread.add_active_input(id=self.id, 
                                                        device=self.device, 
                                                        callback=self.device_can_read)
        else:
            self.midi_io.del_active_input(self.id)
            #if self.listener is not None:
            #    self.listener.stop()
            #self.listener = None
            
    def device_can_read(self):
        buffer = self.device.read(20)
        #self.listener.add_buffer(buffer)
        for data in buffer:
            self.parse_midi_message(data=data[0], timestamp=data[1])

sx_start = chr(0xF0)
sx_end = chr(0xF7)

class Listener(threading.Thread, SignalDispatcher.dispatcher):
    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        SignalDispatcher.dispatcher.__init__(self)
        self.register_signal('data_received', 'disconnected', 'msg_received')
        self.device = kwargs.get('device')
        self.running = threading.Event()
        self.processing = threading.Event()
        self.queue = collections.deque()
        
    def add_buffer(self, buffer):
        self.queue.append(buffer)
        self.processing.set()
        
    def run(self):
        self.running.set()
        while self.running.isSet():
            self.processing.wait()
            if self.running.isSet():
                self.process_next_buffer()
        self.emit('disconnected')
                
    def stop(self):
        self.running.clear()
        self.processing.set()
        
    def process_next_buffer(self):
        if not len(self.queue):
            self.processing.clear()
            return
        buffer = self.queue.popleft()
        for data in buffer:
            msg = messages.parse_midi_message(data[0])
            if msg is None:
                continue
            self.emit('msg_received', msg=msg, timestamp=data[1])



if __name__ == '__main__':
    m = PyGameMidiIO()
    #for dtype in ['out', 'in']:
    #    id = m.dev_info[dtype].keys()[0]
    #    m.add_device(dtype, id)
        #m.change_device_state(type=dtype, id=id, state=True)
    m.do_connect()
    sx = [0xF0, 1, 2, 3, 4, 0xF7]
    s = ''.join([chr(byte) for byte in sx])
    m._send(s)
    m._send(s)
