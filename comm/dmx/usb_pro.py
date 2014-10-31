import os, sys
import threading
import serial
import traceback

from Bases import BaseObject, BaseThread, Config
from ..BaseIO import BaseIO

LOG = BaseObject().LOG

MSG_DELIMITERS = (chr(0x7E), chr(0xE7))

def find_messages(data):
    start, stop = MSG_DELIMITERS
    startstop = ''.join(MSG_DELIMITERS)
    messages = []
    leftover = data
    if start not in data or stop not in data:
        return ([], data)
    while start in leftover:
        startI = leftover.index(start)
        leftover = leftover[startI:]
        if stop not in leftover:
            break
        if len(leftover) < 5:
            break
        sizebytes = [ord(c) for c in leftover[2:4]]
        size = (sizebytes[1] << 8) + sizebytes[0]
        stopI = size + 4
        if len(leftover) < stopI - 1:
            break
        if leftover[stopI] != stop:
            #print 'oops: size=%s, stopI=%s, msg=%s, leftover=%s' % (size, stopI, [ord(c) for c in msg], [ord(c) for c in leftover])
            LOG.warning('usbpro', 'oops: stopI=%s, str at stopI=%s, leftover=%s' % (stopI, ord(leftover[stopI]), [ord(c) for c in leftover]))
            stopI = leftover.rindex(stop)
            #msg = leftover[:stopI+1]
            
            #print 'maybe this one? ', [ord(c) for c in msg], stopI
        
        msg = leftover[:stopI+1]
        #if msg [-1:] != stop:
            
            #break
        messages.append(msg)
        leftover = leftover[stopI:]
    return (messages, leftover)

def send_to_widget(device, data):
    msg = ''.join([chr(item) for item in data])
    msg = msg.join(MSG_DELIMITERS)
    device.write(msg)
    
    
class USBProIO(BaseIO, Config):
    ui_name = 'Enttec DMX USB Pro'
    _confsection = 'DMXUSBPro'
    _Properties = {'universe_index':dict(default=1), 
                   'usb_port':dict(default=0), 
                   'io_type':dict(default='output', entries=('input', 'output'))}
    _SettingsProperties = ['universe_index', 'io_type', 'usb_port']
    def __init__(self, **kwargs):
        BaseIO.__init__(self, **kwargs)
        Config.__init__(self, **kwargs)
        self.comm = kwargs.get('comm')
        self.device = None
        self.universe_obj = None
        self.universe_thread = None
        self.receive_thread = None
        univ = self.get_conf('universe_index')
        if univ is not None:
            self.universe_index = int(univ)
        iotype = self.get_conf('io_type')
        if iotype is not None:
            self.io_type = iotype
        port = self.get_conf('usb_port')
        if port is not None:
            self.usb_port = int(port)
        self.bind(property_changed=self._on_own_property_changed)
        if self.comm.MainController:
            self.on_comm_MainController_set()
        else:
            self.comm.bind(MainController_set=self.on_comm_MainController_set)
        
    @property
    def ds_universes(self):
        if not self.comm.MainController:
            return None
        if self.io_type == 'output':
            return self.comm.MainController.DeviceSystem.universes
        else:
            return self.comm.MainController.DeviceSystem.input_universes
            
    def on_comm_MainController_set(self, **kwargs):
        #self.ds_universes = self.comm.MainController.DeviceSystem.universes
        self.attach_universe()
        self.ds_universes.bind(child_update=self.on_ds_universes_child_update)
        
    def on_ds_universes_child_update(self, **kwargs):
        self.attach_universe()
        
    def on_io_type_changed(self, **kwargs):
        if self.comm.MainController:
            ds = self.comm.MainController.DeviceSystem
            ds.universes.unbind(self)
            ds.input_universes.unbind(self)
            self.ds_universes.bind(child_update=self.on_ds_universes_child_update)
        self.attach_universe()
        if self.io_type == 'input':
            self.send_message(RDMRequest())
        
    def attach_universe(self):
        if self.universe_index is None:
            return
        if self.ds_universes is None:
            return
        univ = self.ds_universes.indexed_items.get(self.universe_index)
        if univ == self.universe_obj:
            return
        if self.universe_obj is not None:
            self.universe_obj.unbind(self)
        if self.universe_thread is not None:
            self.universe_thread.stop(blocking=True)
            self.universe_thread = None
        self.LOG.info('usbpro attach_universe: old=%s, new=%s' % (self.universe_obj, univ))
        self.universe_obj = univ
        if univ is None:
            return
        self.universe_thread = UniverseRefresher(usbproio=self, universe=univ)
        self.universe_thread.start()
        
    def do_connect(self, **kwargs):
        if self.connected:
            self.do_disconnect()
        try:
            if os.name == 'posix':
                port = '/dev/ttyUSB%s' % (self.usb_port)
            else:
                port = self.usb_port
            self.device = serial.Serial(port=port, baudrate=57600, timeout=1)
            self.receive_thread = ReceiveThread(usbproio=self)
            self.receive_thread.start()
            self.connected = True
            self.send_message(GetWidgetParams())
            if self.io_type == 'input':
                self.send_message(RDMRequest())
        except:
            self.LOG.warning('usbpro could not connect: ', sys.exc_info())
        
    def do_disconnect(self, blocking=False):
        if self.universe_thread is not None:
            self.universe_thread.stop(blocking=blocking)
            self.universe_thread = None
        if self.receive_thread is not None:
            self.receive_thread.stop(blocking=blocking)
            self.receive_thread = None
        if self.device is not None:
            self.device.close()
            self.device = None
        self.connected = False
        
    def send_message(self, message):
        if not self.connected:
            return
        data = message.build_message()
        #print 'usbpro sending: ', data
        send_to_widget(self.device, data)
        
    def on_message_received(self, message):
        data = message.data
        if isinstance(message, GetWidgetParams):
            pass
        elif isinstance(message, ReceivedDMX):
            if self.universe_obj is None:
                return
            if len(data) < 2:
                return
            if data[0] & 1 == 1 or data[0] & 2 == 2:
                return
            data = data[2:]
            #print 'dmxpro merge input: ', data
            self.universe_obj.merge_input(values=data, merge_source='usbpro')
        else:
            self.LOG.info('dmxpro rx: ', message, message.data)
        
    def _on_own_property_changed(self, **kwargs):
        prop = kwargs.get('Property')
        value = kwargs.get('value')
        if prop.name in USBProIO._SettingsProperties:
            self.update_conf(**{prop.name:value})
            if prop.name == 'universe_index':
                self.attach_universe()
            elif prop.name == 'io_type':
                self.on_io_type_changed(value=value)
            elif self.connected:
                self.do_connect()
        
class UniverseRefresher(BaseThread):
    _Events = {'refresh_wait':dict(wait_timeout=10.), 
               'sending':{}}
    def __init__(self, **kwargs):
        self.usbproio = kwargs.get('usbproio')
        self.universe = kwargs.get('universe')
        kwargs['thread_id'] = 'USBProUniverseRefresher_%s' % (self.universe.Index)
        super(UniverseRefresher, self).__init__(**kwargs)
        self.update_wait = self.Events['_threaded_call_ready']
        self.update_wait.wait_timeout = .01
        self.updates_to_send = set()
        
    def send_dmx(self):
        self.updates_to_send.clear()
        if self.universe.saved_class_name == 'InputUniverse':
            return
        message = OutputDMX(data=list(self.universe.values))
        self.usbproio.send_message(message)
        
    def _thread_loop_iteration(self):
        if not self._running:
            return
        self.refresh_wait.clear()
        self.send_dmx()
        if not len(self.updates_to_send):
            self.refresh_wait.wait()
        
    def run(self):
        if self.universe.saved_class_name == 'Universe':
            self.universe.bind(value_update=self.on_universe_update)
        super(UniverseRefresher, self).run()
        
    def stop(self, **kwargs):
        if self.universe.saved_class_name == 'Universe':
            self.universe.unbind(self)
        self.updates_to_send.clear()
        self.refresh_wait.set()
        super(UniverseRefresher, self).stop(**kwargs)
        
    def old_run(self):
        running = self.running
        running.set()
        refresh_wait = self.refresh_wait
        update_wait = self.update_wait
        update_interval = self.update_interval
        refresh_interval = self.refresh_interval
        if self.universe.saved_class_name == 'Universe':
            self.universe.bind(value_update=self.on_universe_update)
        while running.isSet():
            update_wait.wait(refresh_interval)
            if running.isSet():
                self.send_dmx()
                if not len(self.updates_to_send):
                    update_wait.clear()
                refresh_wait.wait(update_interval)
                
    def old_stop(self):
        self.universe.unbind(self)
        self.running.clear()
        self.update_wait.set()
        self.refresh_wait.set()
        
    def on_universe_update(self, **kwargs):
        self.updates_to_send.add(kwargs.get('channel'))
        #self.update_wait.set()
        self.refresh_wait.set()

class ReceiveThread(BaseThread):
    def __init__(self, **kwargs):
        kwargs['thread_id'] = 'USBProReceiveThread'
        super(ReceiveThread, self).__init__(**kwargs)
        self._threaded_call_ready.wait_timeout = .1
        self.usbproio = kwargs.get('usbproio')
        #self.running = threading.Event()
        #self.read_wait = threading.Event()
        #self.read_interval = kwargs.get('read_interval', .1)
        self.read_size = kwargs.get('read_size', 8192)
        #self.buffer = []
        self.buffer = ''
    def _thread_loop_iteration(self):
        if not self._running:
            return
        device = self.usbproio.device
        if device is None:
            return
        data = device.read(self.read_size)
        try:
            self.process_data(data)
        except:
            traceback.print_exc()
            self.buffer = ''
            
    def old_run(self):
        usbproio = self.usbproio
        running = self.running
        read_wait = self.read_wait
        read_interval = self.read_interval
        read_size = self.read_size
        running.set()
        while running.isSet():
            read_wait.wait(read_interval)
            if self.running.isSet():
                if usbproio.device is not None:
                    data = usbproio.device.read(read_size)
                    try:
                        self.process_data(data)
                    except:
                        traceback.print_exc()
                        self.buffer = ''
    def old_stop(self):
        self.running.clear()
        self.read_wait.set()
        
    def process_data(self, data):
        buffer = self.buffer
        buffer += data
        messages, leftover = find_messages(buffer)
        self.buffer = leftover
        for msg in messages:
            message = parse_message(msg)
            if message is None:
                continue
            self.usbproio.on_message_received(message)

class MessageBase(object):
    def __init__(self, **kwargs):
        self.set_data(kwargs.get('data', []))
    def get_data(self):
        return self.data
    def set_data(self, data):
        self.data = data
    def build_message(self):
        msg = [self.label]
        data = self.get_data()
        size = [len(data) & 0xFF, (len(data) >> 8) & 0xFF]
        msg.extend(size)
        msg.extend(data)
        return msg
    
class GetWidgetParams(MessageBase):
    label = 3
        
class DMXBase(MessageBase):
    def set_data(self, data):
        if not len(data):
            data = [0] * 512
        if len(data) == 512:
            data = [0] + data
        super(DMXBase, self).set_data(data)
    def set_channel(self, chan, value):
        self.data[chan+1] = value
    
class ReceivedDMX(DMXBase):
    label = 5
    
class OutputDMX(DMXBase):
    label = 6
    
class RDMRequest(DMXBase):
    label = 7

class SetUnsolicited(MessageBase):
    label = 8
    
        
MESSAGE_CLASSES = (GetWidgetParams, ReceivedDMX, OutputDMX, RDMRequest, SetUnsolicited)
MESSAGES_BY_LABEL = dict(zip([cls.label for cls in MESSAGE_CLASSES], MESSAGE_CLASSES))

def parse_message(data):
    start, stop = MSG_DELIMITERS
    if start not in data or stop not in data:
        return
    if data[0] == start:
        startI = data.index(start)
        data = data[startI+1:]
    if data[-1:] == stop:
        stopI = data.rindex(stop)
        data = data[:stopI]
    data = [ord(c) for c in data]
    #print 'parse: ', data
    lbl = data[0]
    cls = MESSAGES_BY_LABEL.get(lbl)
    if cls is None:
        return
    return cls(data=data[3:])
    
    
