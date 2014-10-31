import os
import subprocess
import time
import heapq
import threading
#import atexit
import socket
import select
import array
#import ola_client_wrapper
#from ola.OlaClient import OlaClient
from ola.ClientWrapper import ClientWrapper, Event

from Bases import BaseObject, setID, search_for_process
from Bases import RepeatTimer
from ..BaseIO import BaseIO

class OLAEvent(Event):
    def __init__(self, **kwargs):
        ms = kwargs.get('time_ms', 0)
        cb = kwargs.get('callback')
        super(OLAEvent, self).__init__(ms, cb)
        self._args = kwargs.get('args', ())
        self._kwargs = kwargs.get('kwargs', {})
        
    def Run(self):
        #print 'callback: %s, args: %s, kwargs: %s' % (self._callback, self._args, self._kwargs)
        self._callback(*self._args, **self._kwargs)
        
class ClientWrapperWrapper(ClientWrapper):
    def __init__(self):
        self.__quit = False
        self._events = None
        self._have_events = threading.Event()
        self._stopped = threading.Event()
        super(ClientWrapperWrapper, self).__init__()
        self.responses_waiting = 0
        #print 'wrapper init done'
        self.run_thread = WrapperStartStopper(wrapper=self)
        self.run_thread.start()
        self.LOG.info('ola run thread = ', self.run_thread.name)
    @property
    def stopped(self):
        return self._stopped.isSet()
    @stopped.setter
    def stopped(self, value):
        if value:
            self._stopped.set()
        else:
            self._stopped.clear()
        #print 'stopped event:', self.stopped
    @property
    def have_events(self):
        return self._have_events.isSet()
    @have_events.setter
    def have_events(self, value):
        if value:
            self._have_events.set()
        else:
            self._have_events.clear()
        #print 'have_events event:', self.have_events
    @property
    def _quit(self):
        return self.__quit
    @_quit.setter
    def _quit(self, value):
        if not self._events:
            self.have_events = False            
        self.stopped = value
        #if not self.running and value != self.__quit:
        #    print 'wrapper stopped'
        #print 'wrapper running=%s, _quit=%s' % (self.running, value)
        self.__quit = value
    def queue_response(self):
        self.responses_waiting += 1
        #print 'response queued:', self.responses_waiting
    def response_received(self):
        self.responses_waiting -= 1
        #print 'response received:', self.responses_waiting
    def AddEvent(self, **kwargs):
        event = OLAEvent(**kwargs)
        heapq.heappush(self._events, event)
        #print 'addevent:', [str(e._run_at.time()) for e in self._events]
        #if not self.running:
        #    self.Run()
        self.have_events = True
    def CheckTimeouts(self, now):
        #super(ClientWrapperWrapper, self).CheckTimeouts(now)
        while len(self._events):
            #print 'event len:', len(self._events)
            event = self._events[0]
            if event.HasExpired(now):
                event.Run()
                heapq.heappop(self._events)
                #print 'runevent:', [str(e._run_at.time()) for e in self._events]
            else:
                #print 'not running:', str(event._run_at.time()), 'now=', str(now.time())
                break
        if self.responses_waiting <= 0:
            self.StopIfNoEvents()
    
class WrapperStartStopper(threading.Thread):
    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.wrapper = kwargs.get('wrapper')
        self.running = True
    def run(self):
        while self.running:
            self.wrapper._have_events.wait()
            #print 'starting wrapper'
            self.wrapper.Run()
            self.wrapper._stopped.wait()
            #print 'wrapper stopped'

class olaIO(BaseIO):
    ui_name = 'OLA (Open Lighting Architecture)'
    def __init__(self, **kwargs):
        super(olaIO, self).__init__(**kwargs)
        self.register_signal('new_universe')
        self.pending_calls = 0
        self.universes = {}
        self.devices = {}
        self.hostaddr = kwargs.get('hostaddr', 'localhost')
        self.hostport = int(kwargs.get('hostport', 9010))
        #self.socket = socket.socket()
        self.wrapper = None
        self.client = None
        self.olad_pid = None
        self.olad_process = None
        #self.client = OlaClient(self.socket)
        #self.do_connect()
        self.start_olad()
        #atexit.register(self.on_program_exit)
        
    @property
    def wrapper_state(self):
        if self.wrapper:
            return self.wrapper.running
        return False
        
#    def sent(self):
#        self.pending_calls += 1
#        print 'sent:', self.pending_calls, 'state:', self.wrapper_state
#        if not self.wrapper_state:
#            self.wrapper.Run()
#    def recvd(self, *args):
#        self.pending_calls -= 1
#        print 'recvd:', self.pending_calls
#        if self.pending_calls == 0:
#            self.wrapper.Stop()
            
    def start_olad(self):
        def preexec():
            os.setpgrp()
        if not self.olad_pid:
            pid = search_for_process('olad')
            if not pid:
                self.LOG.info('starting olad...')
                self.olad_process = subprocess.Popen('olad', preexec_fn=preexec)
                pid = self.olad_process.pid
            self.LOG.info('olad pid=%s' % (pid))
            self.olad_pid = pid
        
    def do_connect(self, **kwargs):
        try:
            if not self.wrapper:
                self.wrapper = ClientWrapperWrapper()
            connected = True
        except socket.error:
            connected = False
            self.LOG.warning('could not connect to olad...')
        if connected:
            if not self.client:
                self.client = self.wrapper.Client()
            self.reqUniverseInfo()
        self.connected = connected
        
    def do_disconnect(self):
        if not self.connected:
            return
        #values = array.array([0]*513)
        for univ in self.universes.itervalues():
            univ.stop_timer()
            #self.client.SendDmx(univ.id, values)
        if self.wrapper:
            self.wrapper.run_thread.running = False
            self.wrapper._have_events.set()
        self.connected = False
        
    def on_app_exit(self, *args, **kwargs):
        self.LOG.info('closing olad')
        self.do_disconnect()
        if self.olad_process:
            #t = threading.Timer(2.0, self.olad_process.kill)
            #t.daemon = True
            #t.start()
            self.olad_process.kill()
        
    def on_universe_value_update(self, **kwargs):
        if self.connected:
            univ = kwargs.get('universe')
            #self.client.SendDmx(univ.id, univ.values)
            self.wrapper.AddEvent(callback=univ.on_ola_ready_to_send)
            
        
    def sendDMXValue(self, **kwargs):
        if self.connected:
            univ = kwargs.get('universe')
            #print 'sending values for ', univ.id
            #print 'SendDmx: universe=%s, thread=%s' % (univ.id, threading.currentThread().name)
            self.client.SendDmx(univ.id, univ.values)#, self.recvd)
            #self.sent()
        
    def reqUniverseInfo(self):
        self.wrapper.queue_response()
        self.wrapper.AddEvent(callback=self.client.FetchUniverses, 
                              args=(self.recvUniverseInfo, ))
        #self.client.FetchUniverses(self.recvUniverseInfo)
        #self.sent() 
        
    def recvUniverseInfo(self, state, univData):
        #self.recvd()
        self.wrapper.response_received()
        self.LOG.info('recvUnivInfo:', state, univData)
        for univ in univData:
            #print 'name:', univ.name
            if univ.id not in self.universes:
                obj = olaUniverse(id=univ.id, name=univ.name, merge_mode=univ.merge_mode)
                obj.connect('value_update', self.on_universe_value_update)
                obj.connect('ready_to_send', self.sendDMXValue)
                self.universes.update({obj.id:obj})
                self.emit('new_universe', ola_universe=obj)
        self.LOG.info('all univ:', self.universes)
        self.reqDeviceInfo()
        
    def reqDeviceInfo(self):
        self.wrapper.queue_response()
        self.wrapper.AddEvent(callback=self.client.FetchDevices, 
                              args=(self.recvDeviceInfo, ))
        
    def recvDeviceInfo(self, status, deviceData):
        self.wrapper.response_received()
        for device in deviceData:
            obj = olaDevice(device=device, prebind={'port_update':self.on_device_port_update})
            self.devices.update({obj.id:obj})
        
        for univ in self.universes.itervalues():
            self.LOG.info(univ.id, univ.ports)
            
    def on_device_port_update(self, **kwargs):
        prop = kwargs.get('Property')
        port = kwargs.get('obj')
        old = kwargs.get('old')
        def remove_old_port(univ_id, port):
            univ = self.universes.get(univ_id)
            if univ and port.id in univ.ports[port.type]:
                del univ.ports[port.type][port.id]
        if port.active:
            univ = self.universes.get(port.universe)
            if univ:
                univ.ports[port.type].update({port.id:port})
        if prop.name == 'universe':
            remove_old_port(old, port)
        elif prop.name == 'active' and not port.active:
            remove_old_port(port.universe, port)
                    
        
class olaDevice(BaseObject):
    signals_to_register = ['port_update']
    def __init__(self, **kwargs):
        super(olaDevice, self).__init__(**kwargs)
        device = kwargs.get('device')
        self.id = device.id
        self.index = device.alias
        self.plugin_id = device.plugin_id
        self.ports = {'input':{}, 'output':{}}
        for key, ports in zip(['input', 'output'], [device.input_ports, device.output_ports]):
            for port in ports:
                obj = olaPort(port=port, type=key, device=self, 
                              prebind={'property_changed':self.on_port_property_changed})
                self.ports[key].update({obj.id:obj})
    def on_port_property_changed(self, **kwargs):
        self.emit('port_update', **kwargs)
    
class olaPort(BaseObject):
    _Properties = {'active':dict(default=False), 'universe':dict(type=int)}
    def __init__(self, **kwargs):
        super(olaPort, self).__init__(**kwargs)
        self.device = kwargs.get('device')
        port = kwargs.get('port')
        self.id = port.id
        self.type = kwargs.get('type')
        self.description = port.description
        self.universe = port.universe
        self.active = port._active

class olaUniverse(BaseObject):
    def __init__(self, **kwargs):
        self._Universe = None
        self.timeout = None
        super(olaUniverse, self).__init__(**kwargs)
        self.register_signal('value_update', 'ready_to_send')
        self.id = setID(kwargs.get('id'))
        self.name = kwargs.get('name')
        self.merge_mode = kwargs.get('merge_mode')
        self.ports = {'input':{}, 'output':{}}
        
    @property
    def values(self):
        if self.Universe:
            return self.Universe.values
        return None
        
    @property
    def Universe(self):
        return self._Universe
    @Universe.setter
    def Universe(self, value):
        if value != self.Universe:
            if self.Universe is not None:
                self.stop_timer()
            self._Universe = value
            if self.Universe is not None:
                self.start_timer()
            
    def start_timer(self):
        self.stop_timer()
        self.timeout = DMXTimeout(callback=self.on_universe_value_update)
        self.Universe.connect('value_update', self.timeout.on_update_request)
        self.timeout.start()
        #self.repeat_timer = RepeatTimer(5.0, self.timeout.on_update_request)
        #self.repeat_timer.start()
        
    def stop_timer(self):
        if self.timeout is not None:
            self.Universe.disconnect(callback=self.timeout.on_update_request)
            #self.repeat_timer.cancel()
            #self.repeat_timer = None
            self.timeout.running = False
            self.timeout.needs_update.set()
            self.timeout = None
            
    def on_universe_value_update(self, **kwargs):
        #print 'universe %s update' % (self.id)
        self.emit('value_update', universe=self)
    
    def on_ola_ready_to_send(self):
        self.emit('ready_to_send', universe=self)
            
class DMXTimeout(threading.Thread):
    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        #self.timeout = kwargs.get('timeout', .001)
        self.callback = kwargs.get('callback')
        self.running = True
        self.needs_update = threading.Event()
        self.auto_update_timer = RepeatTimer(3.0, self.on_update_request)
        #self.start_timer()
        
    def run(self):
        self.auto_update_timer.start()
        while self.running:
            self.needs_update.wait()
            self.callback()
            self.needs_update.clear()
        self.auto_update_timer.cancel()
            
    def on_update_request(self, *args, **kwargs):
        self.needs_update.set()

class olaListener(threading.Thread):
    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.state = True
        self.socket = kwargs.get('socket')
        self.client = kwargs.get('client')
        
    def run(self):
        #print 'listener started'
        while self.state:
            i, o, e = select.select([self.socket], [], [])
            if self.socket in i:
                self.client.SocketReady()


if __name__ == '__main__':
    pid = search_for_process('olad')
    #print 'pid=', pid
