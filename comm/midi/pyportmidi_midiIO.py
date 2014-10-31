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
# pyportmidi_midiIO.py
# Copyright (c) 2011 Matthew Reid

import sys
import select
import tempfile

import pypm as pyportmidi

from Bases import BaseThread
from midi_io import MidiIO, MidiIn, MidiOut

class pypmMidiIO(MidiIO):
    '''Requires PyPortMidi by John Harrison.
    http://alumni.media.mit.edu/~harrison/pyportmidi.html
    The package will fail to install on most systems.
    
    Check here for the fix:
    http://cratel.wichita.edu/cratel/cratel_pyportmidi
    
    For linux systems, you must edit the file pypm.pyx
    at line 357 to read:
        while(Pm_Poll(self.midi) != pmNoError):
        
    Note:
    It appears that the project is now hosted here:
    https://bitbucket.org/aalex/pyportmidi/wiki/Home
    
    There is also a PPA with Ubuntu builds here:
    https://launchpad.net/~frasten/+archive/ppa
    '''
    def init_module(self):
        pyportmidi.Initialize()
        
    def get_io_device_classes(self):
        return {'in':pypmMidiIn, 'out':pypmMidiOut}
        
    def get_module_time(self):
        return pyportmidi.Time()
        
    def get_info(self):
        info_keys = ['interface', 'name', 'ins', 'outs', 'open']
        for i in range(pyportmidi.CountDevices()):
            info_list = pyportmidi.GetDeviceInfo(i)
            info_dict = dict(zip(info_keys, info_list))
            if info_dict['ins']:
                info_dict['type'] = 'in'
            else:
                info_dict['type'] = 'out'
            info_dict['Index'] = i
            yield info_dict

class pypmMidiIn(MidiIn):
    def build_device(self, **kwargs):
        return pyportmidi.Input(self.dev_info.index)
        #return FDInput(index=self.dev_info.index)
    @property
    def can_read(self):
        return self.device.Poll()
    def get_data(self):
        return self.device.Read(20)
    def _on_state_set(self, **kwargs):
        super(pypmMidiIn, self)._on_state_set(**kwargs)
        state = kwargs.get('value')
        if state:
            self.listener = Listener(device=self)
            self.listener.start()
        else:
            if self.listener is not None:
                self.listener.stop(blocking=self._block_on_state_change)
            self.listener = None
        
class FDInput(tempfile._TemporaryFileWrapper):
    def __init__(self, **kwargs):
        tempfile.TemporaryFile.__init__(self)
        self.pypm_index = kwargs.get('index')
        self.device = pyportmidi.Input(self.pypm_index)
    def read(self, *args):
        return self.device.Read(*args)
    def readable(self):
        return self.device.Poll()
    def close(self):
        self.device.Close()
        tempfile.TemporaryFile.close(self)
    
class pypmMidiOut(MidiOut):
    def build_device(self, **kwargs):
        return pyportmidi.Output(self.dev_info.index, 1)
        
    def send(self, **kwargs):
        data = kwargs.get('data')
        timestamp = kwargs.get('timestamp', 0)
        if timestamp == 0:
            timestamp = self.midi_io.get_module_time()
        sysex = kwargs.get('sysex')
        if not self.state:
            return
        if data[0] == 0xF0 and data[-1:][0] == 0xF7:
            sysex = data
        if sysex is not None:
            print 'sending sysex: ', sysex
            self.device.WriteSysEx(timestamp, sysex)
        else:
            #print 'sending: data=%s, timestamp=%s' % (data, timestamp)
            self.device.Write([[data, timestamp]])
        self.emit('msg_sent', data=data, timestamp=timestamp)
            
class Listener(BaseThread):
    def __init__(self, **kwargs):
        self.device = kwargs.get('device')
        kwargs['thread_id'] = 'MidiInput_%s_Listener' % (self.device.dev_info.index)
        super(Listener, self).__init__(**kwargs)
        self._threaded_call_ready.wait_timeout = .001
        #self.poll_timeout = .001
        #self.running = threading.Event()
        #self.processing = threading.Event()
        
    def selecttestrun(self):
        self.running.set()
        while self.running.isSet():
            if not self.running.isSet():
                return
            r, w, e = select.select([self.device, ], [], [])
            if self.device in r:
                buffer = self.device.get_data()
                for data in buffer:
                    self.process_message(data)
                    
    def _thread_loop_iteration(self):
        if not self._running:
            return
        while self.device.can_read:
            buffer = self.device.get_data()
            for data in buffer:
                self.process_message(data)
                
    def old_run(self):
        self.running.set()
        while self.running.isSet():
            self.processing.wait(self.poll_timeout)
            if not self.running.isSet():
                return
            while self.device.can_read:
                buffer = self.device.get_data()
                for data in buffer:
                    self.process_message(data)
                
    def old_stop(self):
        self.running.clear()
        self.processing.set()
            
    def process_message(self, data):
        #print data
        try:
            self.device.parse_midi_message(data=data[0], timestamp=data[1])
            #print 'msgdata: ', msg.build_data()
        except:
            self.LOG.warning(sys.exc_info())
