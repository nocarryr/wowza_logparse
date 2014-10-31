import sys
import threading
import collections
import socket
import errno

from Bases import Config
from ..BaseIO import BaseIO

class NetlinxDMX(BaseIO, Config):
    ui_name = 'Netlinx (AMX test module)'
    _confsection = 'NetlinxDMX'
    _Properties = {'universe_index':dict(default=1), 
                   'netlinx_address':dict(type=str), 
                   'netlinx_port':dict(default=1998, min=1, max=65535)}
    _SettingsProperties = ['universe_index', 'netlinx_address', 'netlinx_port']
    def __init__(self, **kwargs):
        self.reconnect_timer = None
        self.ds_universes = None
        self.universe_obj = None
        self.universe_thread = None
        self.socket = None
        self.should_be_connected = False
        BaseIO.__init__(self, **kwargs)
        Config.__init__(self, **kwargs)
        self.comm = kwargs.get('comm')
        univ = self.get_conf('universe_index')
        if univ is not None:
            self.universe_index = int(univ)
        self.netlinx_address = self.get_conf('netlinx_address')
        port = self.get_conf('netlinx_port')
        if port is not None:
            self.netlinx_port = port
        self.bind(property_changed=self._on_own_property_changed)
        if self.comm.MainController:
            self.on_comm_MainController_set()
        else:
            self.comm.bind(MainController_set=self.on_comm_MainController_set)
        
    def on_comm_MainController_set(self, **kwargs):
        self.ds_universes = self.comm.MainController.DeviceSystem.universes
        self.attach_universe()
        self.ds_universes.bind(child_update=self.on_ds_universes_child_update)
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
            self.universe_thread.stop()
            self.universe_thread.join()
            self.universe_thread = None
        self.LOG.info('netlinx attach_universe: old=%s, new=%s' % (self.universe_obj, univ))
        self.universe_obj = univ
        if univ is None:
            return
        self.universe_thread = UniverseRefresher(netlinxdmx=self)
        self.universe_thread.start()
        univ.bind(value_update=self.on_universe_value_update)
    def on_ds_universes_child_update(self, **kwargs):
        self.attach_universe()
    def do_connect(self):
        if self.reconnect_timer is not None:
            if self.reconnect_timer.is_alive():
                self.reconnect_timer.cancel()
            self.reconnect_timer = None
        if self.connected:
            self.do_disconnect()
        self.should_be_connected = True
        try:
            self.socket = socket.socket()
            self.socket.connect((self.netlinx_address, self.netlinx_port))
            self.connected = True
        except socket.error, msg:
            self.LOG.warning('could not connect to Netlinx')
            #self.reconnect(5.)
    def do_disconnect(self):
        if self.connected:
            self.socket.close()
        self.should_be_connected = False
        self.connected = False
    def reconnect(self, timeout=.5):
        if self.connected:
            self.do_disconnect()
        if self.reconnect_timer is not None:
            self.reconnect_timer.cancel()
            self.reconnect_timer = None
        t = threading.Timer(timeout, self.do_connect)
        self.reconnect_timer = t
        t.start()
    def _send(self, string):
        if self.connected:
            self.socket.send(string)
        #print 'netlinx: ', string
    def sendDMXValue(self, **kwargs):
        chan = kwargs.get('channel')
        value = kwargs.get('value')
        self._send('C%s=%s!' % (chan, value))
        #print 'C%s=%s!' % (chan, values[chan])
    def on_universe_value_update(self, **kwargs):
        univ = kwargs.get('universe')
        if univ != self.universe_obj:
            return
        if self.universe_thread is None:
            return
        self.universe_thread.send_single(**kwargs)
    def _on_own_property_changed(self, **kwargs):
        prop = kwargs.get('Property')
        value = kwargs.get('value')
        if prop.name in NetlinxDMX._SettingsProperties:
            self.update_conf(**{prop.name:value})
            if prop.name == 'universe_index':
                self.attach_universe()
            elif self.connected:
                self.reconnect()
                
    
class UniverseRefresher(threading.Thread):
    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.netlinxdmx = kwargs.get('netlinxdmx')
        self.refresh_interval = kwargs.get('refresh_interval', 10.)
        self.running = threading.Event()
        self.refresh_wait = threading.Event()
        self.sending = threading.Event()
        self.queue = collections.deque()
    def send_single(self, **kwargs):
        chan = kwargs.get('channel')
        value = kwargs.get('value')
        self.queue.append((chan, value))
        self.refresh_wait.set()
    def send_all_channels(self):
        univ = self.netlinxdmx.universe_obj
        for chan in univ.patched_channels:
            self.queue.append((chan, univ.values[chan-1]))
        self.refresh_wait.set()
    def run(self):
        running = self.running
        running.set()
        refresh_wait = self.refresh_wait
        interval = self.refresh_interval
        while running.isSet():
            flag = refresh_wait.wait(interval)
            if running.isSet():
                if refresh_wait.is_set():
                    self.send_next_message()
                else:
                    self.send_all_channels()
    def stop(self):
        self.running.clear()
        self.refresh_wait.set()
    def send_next_message(self):
        if not len(self.queue):
            self.refresh_wait.clear()
            return
        chan, value = self.queue.popleft()
        #print 'send_next_msg: ', chan, value
        self.netlinxdmx.sendDMXValue(channel=chan, value=value)
        
