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
# midi_io.py
# Copyright (c) 2011 Matthew Reid

import time
import datetime

from Bases import BaseObject, ChildGroup, Config, Scheduler
from ..BaseIO import BaseIO

from mapper import MidiMapper
import messages

class MidiIO(BaseIO, Config):
    _confsection = 'MIDI'
    def __init__(self, **kwargs):
        BaseIO.__init__(self, **kwargs)
        Config.__init__(self, **kwargs)
        self.comm = kwargs.get('comm')
        self.register_signal('msg_received', 'msg_sent')
        self.time_scale = self.get_time_scale()
        self.detected_inputs = ChildGroup(name='Inputs')
        self.detected_outputs = ChildGroup(name='Outputs')
        self.dev_info = {'in':self.detected_inputs, 
                         'out':self.detected_outputs}
        self.devices = {}
        for key, cls in self.get_io_device_classes().iteritems():
            self.devices[key] = ChildGroup(name=key, child_class=cls)
        
        self.init_module()
        now = time.time()
        self.start_time = {'module':self.get_module_time(), 
                           'time':now, 
                           'dt':datetime.datetime.fromtimestamp(now)}
        #print self.start_time
        
        
        self.update_devices()
        conf = self.get_conf()
        for key, confkey in {'in':'enabled_inputs', 'out':'enabled_outputs'}.iteritems():
            val = conf.get(confkey)
            if not val:
                continue
            for dev in val:
                self.add_device(key, dev, update_conf=False)
        self.prepare_conf_update()
        self.Mapper = MidiMapper(midi_io=self)
#        self.midi_osc = MidiOSCRoot(osc_parent_node=self.comm.osc_io.root_node)
#        self.midi_osc.bind(event=self.on_midi_osc_event)
#        
#    def on_midi_osc_event(self, **kwargs):
#        print kwargs
        
    @property
    def module_time_offset(self):
        mod_dt = self.module_time_to_datetime(self.get_module_time())
        now = datetime.datetime.now()
        td = mod_dt - now
        return td.seconds + td.days * 24 * 3600 + (td.microseconds / float(10**6))
        
    def time_to_module_time(self, t):
        diff = t - self.start_time['time']
        return (diff + self.start_time['module']) * self.time_scale
        
    def module_time_to_time(self, modtime):
        seconds = (modtime / self.time_scale) - self.start_time['module']
        return self.start_time['time'] + seconds
        
    def datetime_to_module_time(self, dt):
        td = dt - self.start_time['dt']
        seconds = td.seconds + td.days * 24 * 3600 + (td.microseconds / float(10**6))
        return (seconds + self.start_time['module']) * self.time_scale
        
    def module_time_to_datetime(self, modtime):
        seconds = (modtime / self.time_scale) - self.start_time['module']
        td = datetime.timedelta(seconds=seconds)
        return self.start_time['dt'] + td
        
    def do_connect(self, *args, **kwargs):
        for key, val in self.devices.iteritems():
            for id in val.iterkeys():
                self.change_device_state(type=key, id=id, state=True)
        self.LOG.info('MIDI connected')
        self.connected = True
    
    def do_disconnect(self, blocking=False):
        for key, val in self.devices.iteritems():
            for id in val.iterkeys():
                self.change_device_state(type=key, id=id, state=False)
        self.LOG.info('MIDI disconnected')
        self.connected = False
        
    def update_devices(self):
        for dev_info in self.get_info():
            dev = DeviceInfo(**dev_info)
            self.dev_info[dev.type].add_child(existing_object=dev)
            dev.bind(active=self.on_dev_info_active_set)
        
    def add_device(self, dtype, id, update_conf=True):
        if id in self.dev_info[dtype] and id not in self.devices[dtype]:
            #dev = self.dev_classes[dtype](dev_info=self.dev_info[dtype][id])
            dev = self.devices[dtype].add_child(dev_info=self.dev_info[dtype][id], midi_io=self)
            if dtype == 'in':
                dev.bind(msg_received=self.on_msg_received)
            else:
                dev.bind(msg_sent=self.on_msg_sent)
            #self.devices[dtype].update({id:dev})
            self.dev_info[dtype][id].active = True
            if self.connected:
                self.change_device_state(type=dtype, id=id, state=True)
            if update_conf:
                self.prepare_conf_update()
            self.LOG.info('MIDI %s %s added' % (dtype, id))
            
    def del_device(self, dtype, id, update_conf=True):
        device = self.devices[dtype].get(id)
        if device is None:
            return
        self.change_device_state(type=dtype, id=id, state=False)
        #del self.devices[dtype][id]
        self.devices[dtype].del_child(device)
        self.LOG.info('MIDI %s %s removed' % (dtype, id))
        self.dev_info[dtype][id].active = False
        if update_conf:
            self.prepare_conf_update()
        
    def on_dev_info_active_set(self, **kwargs):
        obj = kwargs.get('obj')
        state = kwargs.get('value')
        if state:
            self.add_device(obj.type, obj.id)
        else:
            self.del_device(obj.type, obj.id)
    
    def change_device_state(self, **kwargs):
        id = kwargs.get('id')
        dtype = kwargs.get('type')
        state = kwargs.get('state')
        blocking = kwargs.get('blocking', False)
        device = self.devices[dtype][id]
        device._block_on_state_change = blocking
        device.state = state
    
    def prepare_conf_update(self):
        d = {}
        for key, confkey in {'in':'enabled_inputs', 'out':'enabled_outputs'}.iteritems():
            #s = ','.join(self.devices[key].keys())
            d.update({confkey:self.devices[key].keys()})
        self.update_conf(**d)
       
    def _send(self, data, **kwargs):
        id = kwargs.get('id')
        if id is not None and id in self.devices['out']:
            self.devices['out'][id].send(data=data)
        else:
            for dev in self.devices['out'].itervalues():
                dev.send(data=data)
    
    def on_msg_received(self, **kwargs):
        self.emit('msg_received', **kwargs)
        
    def on_msg_sent(self, **kwargs):
        self.emit('msg_sent', **kwargs)
    
    def init_module(self):
        '''
        subclasses may use this to perform any initialization necessary
        '''
        pass
        
    def get_time_scale(self):
        '''
        subclasses may override the time scale (default is milliseconds)
        '''
        return 1000.
        
    def get_io_device_classes(self):
        '''
        subclasses must return a dict containing:
            {'in':[midi input class], 'out':[midi output class]}
        '''
        raise NotImplementedError('method must be defined by subclass')
        
    def get_info(self, *args, **kwargs):
        '''
        subclasses must return a sequence of dicts to initialize the DeviceInfo class.
            interface: (midi subsystem name)
            name: name of the device
            type: either "in" or "out"
            open: (bool) whether the device is currently opened by the system
            id: 
        '''
        raise NotImplementedError('method must be defined by subclass')
        
    def get_module_time(self):
        '''
        subclasses must return the current timestamp from the midi subsystem
        '''
        raise NotImplementedError('method must be defined by subclass')
        
class DeviceInfo(BaseObject):
    _Properties = {'name':dict(type=str), 
                   'type':dict(type=str, entries=['in', 'out']), 
                   'active':dict(default=False)}
    _SettingsProperties = ['Index', 'name', 'active']
    def __init__(self, **kwargs):
        super(DeviceInfo, self).__init__(**kwargs)
        self.register_signal('state_changed')
        self.interface = kwargs.get('interface')
        self.name = kwargs.get('name')
        self.type = kwargs.get('type')
        self.open = kwargs.get('open')
        self.id = kwargs.get('id', self.name)
    @property
    def index(self):
        return self.Index
        
class MidiOut(BaseObject):
    _Properties = {'state':dict(default=False)}
    def __init__(self, **kwargs):
        super(MidiOut, self).__init__(**kwargs)
        self.register_signal('msg_sent')
        self.dev_info = kwargs.get('dev_info')
        self.midi_io = kwargs.get('midi_io')
        self._block_on_state_change = False
        self.device = self.build_device(**kwargs)
        self.id = self.dev_info.id
        #self.buffer = None
        self.bind(state=self._on_state_set)
        
    def unlink(self):
        self.state = False
        super(MidiOut, self).unlink()
        
    def send(self, **kwargs):
        pass
        
    def _on_state_set(self, **kwargs):
        pass
        
        
class MidiIn(BaseObject):
    _Properties = {'state':dict(default=False)}
    def __init__(self, **kwargs):
        super(MidiIn, self).__init__(**kwargs)
        self.register_signal('data_received', 'msg_received')
        self.dev_info = kwargs.get('dev_info')
        self.midi_io = kwargs.get('midi_io')
        self._block_on_state_change = False
        self.id = self.dev_info.id
        self.device = self.build_device(**kwargs)
        self.scheduler = None
        self.bind(state=self._on_state_set)
        
        
    def parse_midi_message(self, **kwargs):
        data = kwargs.get('data')
        timestamp = kwargs.get('timestamp', 0)
        if timestamp == 0:
            timestamp = self.midi_io.get_module_time()
        #now = time.time()
        t = self.midi_io.module_time_to_time(timestamp)
        #nowdiff = now - self.midi_io.start_time['time']
        #tdiff = t - self.midi_io.start_time['time']
        #print 'realtime=%010.8f, modtime=%010.8f, diff=%010.8f' % (nowdiff, tdiff, tdiff - nowdiff)
        msg = messages.parse_midi_message(data, timestamp=t)
        if msg is None:
            return
        self.scheduler.add_item(t, msg)
        return msg
        
    def on_data_received(self, **kwargs):
        self.emit('data_received', **kwargs)
        
    def on_msg_received(self, **kwargs):
        self.emit('msg_received', **kwargs)
        
    def _on_state_set(self, **kwargs):
        if kwargs.get('value'):
            self.scheduler = Scheduler(callback=self.on_scheduler_process_msg)#, spawn_threads=True)
            self.scheduler.start()
        elif self.scheduler is not None:
            self.scheduler.stop(blocking=self._block_on_state_change)
            self.scheduler = None
        
    def on_scheduler_process_msg(self, msg, t):
#        msgtype = None
#        if isinstance(msg, messages.NoteMessage):
#            msgtype = 'note'
#        elif isinstance(msg, messages.ControllerMessage):
#            msgtype = 'controller'
#        if msgtype:
#            tkwargs = dict(zip(msg.byte_order, msg.build_data()))
#            tkwargs['ioType'] = 'in'
#            tkwargs['type'] = msgtype
#            self.midi_io.midi_osc.trigger_event(**tkwargs)
        self.emit('msg_received', msg=msg)
        
