import time
import rtmidi_python as rtmidi


from midi_io import MidiIO, MidiIn, MidiOut

class rtmMidiIO(MidiIO):
    def get_io_device_classes(self):
        return {'in':rtmMidiIn, 'out':rtmMidiOut}
    def get_module_time(self):
        return time.time()
    def get_info(self):
        d = {'in':rtmidi.MidiIn(), 'out':rtmidi.MidiOut()}
        i = 0
        for key, dev in d.iteritems():
            for devindex, name in enumerate(dev.ports):
                devinfo = {'type':key, 
                           'name':name, 
                           'id':'in:%d' % (devindex), 
                           'Index':i}
                yield devinfo
                i += 1
        
class rtmMidiIn(MidiIn):
    def build_device(self, **kwargs):
        return rtmidi.MidiIn()
    def rtmidi_message_callback(self, data, timestamp):
        self.parse_midi_message(data=data, timestamp=timestamp)
    def _on_state_set(self, **kwargs):
        state = kwargs.get('value')
        if state:
            self.device.open_port(self.dev_info.name)
        else:
            self.device.close_port()
        
class rtmMidiOut(MidiOut):
    def build_device(self, **kwargs):
        return rtmidi.MidiOut()
        
    def send(self, **kwargs):
        data = kwargs.get('data')
        sysex = kwargs.get('sysex')
        if not self.state:
            return
        if sysex is not None:
            data = sysex
        self.device.send_message(data)
    def _on_state_set(self, **kwargs):
        state = kwargs.get('value')
        if state:
            self.device.open_port(self.dev_info.name)
        else:
            self.device.close_port()
