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
# manager.py (package: comm.dmx.artnet)
# Copyright (c) 2011 Matthew Reid

import gc
import socket
import threading
import datetime

from Bases import BaseObject, BaseThread, RepeatTimer
from ... import BaseIO
import messages
from communication import ArtnetIO

#PRIMARY_ADDR = '2.255.255.255'
#SECONDARY_ADDR = '10.255.255.255'
#UDP_PORT = 1936
#PRIMARY_ADDR = '255.255.255.255'
#PRIMARY_ADDR = '192.168.1.255'
#PRIMARY_ADDR = '.'.join(BaseIO.detect_usable_address().split('.')[:2] + ['255', '255'])
PRIMARY_ADDR = '.'.join(BaseIO.detect_usable_address().split('.')[:3] + ['255'])
UDP_PORT = 6454

class ArtnetManager(BaseIO.BaseIO):
    ui_name = 'Artnet'
    def __init__(self, **kwargs):
        super(ArtnetManager, self).__init__(**kwargs)
        self.register_signal('new_node', 'del_node')
        self.comm = kwargs.get('comm')
        self.hostaddr = BaseIO.detect_usable_address()
        self.hostname = socket.gethostname()
        self.hostport = UDP_PORT
        self.mac_addr = BaseIO.get_mac_address()
        self.subnet = kwargs.get('subnet', 0)
        self.artpoll = messages.ArtPoll(TalkToMe=2)
        self.artpoll_reply = messages.ArtPollReply(IPAddress=self.hostaddr, 
                                                   Port=UDP_PORT, 
                                                   Oem=0xFF, 
                                                   ShortName=self.hostname, 
                                                   LongName=self.hostname, 
                                                   MAC=self.mac_addr, 
                                                   Style=1, 
                                                   NumPorts=4, 
                                                   PortTypes=[0xC0]*4, 
                                                   Swin=[1, 2, 3, 4])
                                                   #Swout=[1, 2, 3, 4])
        
        self.Nodes = {}
        self.NodesByUniverse = {}
        self.NodePortInfo = {'InputPorts':{}, 'OutputPorts':{}}
        for i, style in self.artpoll_reply.Fields['Style'].codes.iteritems():
            self.Nodes[style] = {}
        
        self.Universes = {}
        self.ds_universes = {}

        self.artnet_io = ArtnetIO(hostaddr=PRIMARY_ADDR, hostport=UDP_PORT, manager=self)
        self.poller = None
        
        if getattr(self.comm, 'MainController', None):
            self.on_comm_MainController_set()
        else:
            self.comm.bind(MainController_set=self.on_comm_MainController_set)
        
    def unlink(self):
        self.comm.unbind(self)
        if type(self.ds_universes) != dict:
            self.ds_universes.unbind(self)
        super(ArtnetManager, self).unlink()
        
    def on_comm_MainController_set(self, **kwargs):
        self.ds_universes = self.comm.MainController.DeviceSystem.universes
        self.update_ds_universes()
        self.ds_universes.bind(child_added=self.on_ds_universes_child_added, 
                               child_removed=self.on_ds_universes_child_removed)
        
    def on_ds_universes_child_added(self, **kwargs):
        obj = kwargs.get('obj')
        self.update_ds_universes(univ_obj=obj)
        
    def on_ds_universes_child_removed(self, **kwargs):
        obj = kwargs.get('obj')
        self.detach_universe(univ_obj=obj)
        
    def update_ds_universes(self, **kwargs):
        univ_obj = kwargs.get('univ_obj')
        if univ_obj is not None:
            universes = [univ_obj]
        else:
            universes = self.ds_universes.values()
        for univ_obj in universes:
            sub = univ_obj.Artnet_Subnet
            univ = univ_obj.Artnet_Universe
            self.detach_universe(univ_obj=univ_obj)
            if sub is not None and univ is not None:
                self.attach_universe(universe_obj=univ_obj, 
                                     universe_index=univ, 
                                     subnet=sub)
            univ_obj.bind(property_changed=self.on_ds_universe_obj_property_changed)
            
    def on_ds_universe_obj_property_changed(self, **kwargs):
        prop = kwargs.get('Property')
        obj = kwargs.get('obj')
        if prop.name in ['Artnet_Subnet', 'Artnet_Universe']:
            self.update_ds_universes(univ_obj=obj)
        
    def do_connect(self):
        if self.connected:
            self.do_disconnect(blocking=True)
        self.artnet_io.do_connect()
#        clslist = [communication.MulticastSender, communication.MulticastReceiver]
#        for key, cls in zip(['sender', 'receiver'], clslist):
#            obj = cls(hostaddr=self.hostaddr, hostport=self.hostport, 
#                      mcastaddr=PRIMARY_ADDR, mcastport=UDP_PORT, 
#                      manager=self)
#            self.multicast_io[key] = obj
#            obj.do_connect()
        self.poller = Poller(manager=self)
        self.poller.start()
        #self.poller.stop()
        self.connected = True
        self.update_ds_universes()
        
    def do_disconnect(self, blocking=False):
        if self.poller is not None:
            self.poller.stop(blocking=blocking)
            self.poller = None
        #for univ in self.Universes.itervalues():
        #    univ.stop()
        for univ_obj in self.ds_universes.itervalues():
            self.detach_universe(univ_obj=univ_obj, blocking=blocking)
        self.artnet_io.do_disconnect(blocking=blocking)
#        for key in ['sender', 'reciever']:
#            obj = self.multicast_io.get(key)
#            if obj:
#                obj.do_disconnect()
#                del self.multicast_io[key]
        self.connected = False
        
    def attach_universe(self, **kwargs):
        '''
        :Parameters:
            universe_obj :
            universe_index :
            subnet :
        '''
        kwargs.setdefault('subnet', self.subnet)
        kwargs.setdefault('manager', self)
        univ = UniverseThread(**kwargs)
        self.Universes[(univ.subnet, univ.universe_index)] = univ
        if self.connected:
            univ.start()
        keys = ['subnet', 'universe_index', '_thread_id']
        d = dict(zip(keys, [getattr(univ, key) for key in keys]))
        nodes = self.NodePortInfo['OutputPorts'].get((univ.subnet, univ.universe_index), [])
        d['nodes'] = [str(n) for n in nodes]
        self.LOG.info('Artnet attached universe: ', d)
            
    def detach_universe(self, **kwargs):
        univ_obj = kwargs.get('univ_obj')
        blocking = kwargs.get('blocking', True)
        univ_obj.unbind(self)
        univ_obj.unbind(self)
        key = (univ_obj.Artnet_Subnet, univ_obj.Artnet_Universe)
        for ukey, uval in self.Universes.iteritems():
            if uval.universe_obj == univ_obj:
                key = ukey
        univ_thread = self.Universes.get(key)
        if univ_thread:
            self.LOG.info('Artnet detach universe: ', key, univ_thread._thread_id)
            univ_thread.stop(blocking=blocking)
            del self.Universes[key]
        
    def add_node(self, **kwargs):
        msg = kwargs.get('artpoll_reply')
        if msg is None:
            return
        node = Node(artpoll_reply=msg, manager=self)
        nid = node.id
        style = node.style
        if nid not in self.Nodes[style]:
            self.Nodes[style][nid] = node
            #print 'new node: id=%s, style=%s, data=%s' % (node.id, node.style, node.data)
            #keys = node.Properties.keys()
            #self.LOG.info('Artnet new node: ', dict(zip(keys, [getattr(node, key) for key in keys])))
            self.LOG.info('Artnet new node: ', str(node))
            self.update_node_port_info(node=node)
            node.bind(**dict(zip(['InputPorts', 'OutputPorts'], [self.on_node_io_port_update]*2)))
            self.emit('new_node', style=style, id=nid, node=node)
        else:
            self.Nodes[style][nid].set_data(msg)
            
    def update_node_port_info(self, **kwargs):
        node = kwargs.get('node')
        if node:
            if node.style != 'StNode':
                return
            nodes = [node]
        else:
            nodes = self.Nodes['StNode'].values()
        for node in nodes:
            for iokey, iodict in self.NodePortInfo.iteritems():
                for i, sub_univ in enumerate(getattr(node, iokey)):
                    if sub_univ is not None:
                        if sub_univ not in iodict:
                            iodict[sub_univ] = set()
                        iodict[sub_univ].add(node)
                        if sub_univ in self.Universes:
                            self.Universes[sub_univ].add_node(node=node, port=i)
        #print self.NodePortInfo
        
    def on_node_io_port_update(self, **kwargs):
        node = kwargs.get('obj')
        key = kwargs.get('name')
        old = kwargs.get('old')
        value = kwargs.get('value')
        if node.style != 'StNode':
            return
        if old is not None:
            for i, subuniv in enumerate(old):
                if value[i] != subuniv:
                    nodeset = self.NodePortInfo[key].get(subuniv, set())
                    nodeset.discard(node)
        self.update_node_port_info(node=node)
    
    def del_node(self, **kwargs):
        nstyle = kwargs.get('style')
        nid = kwargs.get('id')
        node = kwargs.get('node')
        if node is not None:
            nstyle = node.style
            nid = node.id
        elif nid is not None:
            node = self.Nodes.get(nstyle, {}).get(nid)
        if node is None:
            return
        node.unbind(self)
        node.unlink()
        del self.Nodes[nstyle][nid]
        self.emit('del_node', style=nstyle, id=nid, node=node)
        if nstyle != 'StNode':
            return
        for iokey, iodict in self.NodePortInfo.iteritems():
            for sub_univ in getattr(node, iokey):
                if sub_univ is not None:
                    nodeset = iodict.get(sub_univ, set())
                    nodeset.discard(node)
                    if sub_univ in iodict and not len(nodeset):
                        del iodict[sub_univ]
                    if sub_univ in self.Universes:
                        self.Universes[sub_univ].del_node(node=node)
        #print self.NodePortInfo
            
    def send_dmx(self, **kwargs):
        if not self.comm.osc_io.isMaster:
            return
        seq = kwargs.get('sequence', 0)
        sub = kwargs.get('subnet', self.subnet)
        univ = kwargs.get('universe', 1)
        data = kwargs.get('data')
        nodes = self.NodePortInfo['OutputPorts'].get((sub, univ))
        if not nodes:
            return
        clients = [(n.data['IPAddress'], n.data['Port']) for n in nodes]
        #clients = [None]
        msg = messages.ArtDmx(Sequence=seq, Universe=(sub * 0x10) + univ, Data=data, Physical=univ)
        #if len(data) < 512:
        #    print 'dmxlen: msg=%s, data=%s, msglen=%s' % (msg.Fields['Length'].value, len(data), len(msg.get_data()[0]))
        #print 'sending dmx to univ ', univ
        self.send_msg(msg=msg, clients=clients)
        
    def send_msg(self, **kwargs):
        msg = kwargs.get('msg')
        clients = kwargs.get('clients', [None])
        s = msg.build_string()
        for client in clients:
            self.artnet_io.send(s, client)
        
    def parse_message(self, **kwargs):
        data = kwargs.get('data')
        client = kwargs.get('client')
        msg = messages.parse_message(data)
        if not msg:
            return
        #print msg.__class__.__name__, [[f.id, f.value] for f in msg.Fields.indexed_items.values()]
        if msg.msg_type == 'ArtPoll':
            self.artnet_io.send(self.artpoll_reply.build_string())
        elif msg.msg_type == 'ArtPollReply':# and msg.Fields['MAC'].value != self.mac_addr:
            self.add_node(artpoll_reply=msg)
        elif msg.msg_type == 'ArtDmx':
            #print 'ArtDmx from :', client
            u = msg.Fields['Universe'].value
            subuniv = (u / 0x10, u % 0x10)
            u = self.Universes.get(subuniv)
            if u is None:
                return
            u.merge_dmx_msg(msg=msg, client=client)
            
        #print 'artnet gc: ', gc.collect(0)
        self.collect_garbage()
        
class Poller(BaseThread):
    def __init__(self, **kwargs):
        kwargs['thread_id'] = 'ArtnetPoller'
        super(Poller, self).__init__(**kwargs)
        #self.running = threading.Event()
        #self.poll_wait = threading.Event()
        self.manager = kwargs.get('manager')
        self.poll_interval = kwargs.get('interval', 5.)
        self._threaded_call_ready.wait_timeout = self.poll_interval
        
    def do_poll(self):
        if not self._running.isSet():
            return
        #self.manager.multicast_io['sender'].send(self.manager.artpoll.build_string())
        self.manager.artnet_io.send(self.manager.artpoll.build_string())
        
    def check_dead_nodes(self):
        dead_nodes = []
        now = datetime.datetime.now()
        timeout = now - datetime.timedelta(seconds=self.poll_interval + 10)
        for nstyles in self.manager.Nodes.itervalues():
            for node in nstyles.itervalues():
                if node.last_update < timeout:
                    self.LOG.info('deleting node: timeout = ',  timeout)
                    dead_nodes.append(node)
        for node in dead_nodes:
            self.manager.del_node(node=node)
        
    def _thread_loop_iteration(self):
        if not self._running.isSet():
            return
        self.do_poll()
        self.check_dead_nodes()
        
    def old_run(self):
        self.running.set()
        self.poll_wait.set()
        while self.running.isSet():
            self.poll_wait.wait(self.poll_interval)
            if self.running.isSet():
                self.do_poll()
                self.check_dead_nodes()
            self.poll_wait.clear()
            
    def old_stop(self):
        self.running.clear()
        self.poll_wait.set()
        
class UniverseThread(BaseThread):
    auto_update_interval = 4.0
    refresh_interval = .005
    _Events = {'need_update':dict(wait_timeout=4.), 
               'refresh_wait':dict(wait_timeout=.005)}
    def __init__(self, **kwargs):
        self.manager = kwargs.get('manager')
        self.universe_obj = kwargs.get('universe_obj')
        self.is_input = self.universe_obj.saved_class_name == 'InputUniverse'
        self.subnet = kwargs.get('subnet')
        self.universe_index = kwargs.get('universe_index')
        self._values_cleared = False
        kwargs['thread_id'] = 'ArtnetUniverseThread_%s-%s_%s' % (self.subnet, self.universe_index, {True:'Input', False:'Output'}.get(self.is_input))
        kwargs['disable_threaded_call_waits'] = True
        super(UniverseThread, self).__init__(**kwargs)
        
        #self.merge_mode = kwargs.get('merge_mode', 'htp')
        
        self.subscribed_nodes = {}
        self.sequence = 1
        #self.running = threading.Event()
        #self.need_update = threading.Event()
        #self.refresh_wait = threading.Event()
        self.updates_to_send = set()
        
    def send_dmx(self):
        if self._running.isSet():
            #if len(self.updates_to_send):
            #    maxchan = max(self.updates_to_send)
            #else:
            #    maxchan = -1
            maxchan = -1
            data = list(self.universe_obj.values)[:maxchan]
        else:
            data = [0]*512
            self._values_cleared = True
        self.updates_to_send.clear()
        self.manager.send_dmx(universe=self.universe_index, 
                              subnet=self.subnet, 
                              data=data, 
                              sequence=self.sequence)
        if self.sequence == 0xFF:
            self.sequence = 1
        else:
            self.sequence += 1
        
    def merge_dmx_msg(self, **kwargs):
        if not self.is_input:
            return
        msg = kwargs.get('msg')
        client = kwargs.get('client')
        self.universe_obj.merge_input(values=msg.Fields['Data'].value[:], client=client)
        return
        data = list(self.universe_obj.values)[:-1]
        changed = False
        if self.merge_mode == 'htp':
            for i, value in enumerate(msg.Fields['Data'].value):
                if value > data[i]:
                    #print 'htp chan=%s, src=%s, old=%s, univ=%s, client=%s' % (i, value, data[i], self.universe_index, client)
                    data[i] = value
                    changed = True
        elif self.merge_mode == 'ltp':
            pass
        if changed:
            self.send_dmx()
        
    def _thread_loop_iteration(self):
        self.need_update.wait()
        self.send_dmx()
        if not len(self.updates_to_send):
            self.need_update.clear()
        self.refresh_wait.wait()
        
    def run(self):
        self.universe_obj.bind(value_update=self.on_universe_value_update)
        super(UniverseThread, self).run()
        
    def stop(self, **kwargs):
        self.universe_obj.unbind(self)
        self._running.clear()
        self.need_update.set()
        self.refresh_wait.set()
        super(UniverseThread, self).stop(**kwargs)
        self._stopped.wait()
        if not self._values_cleared:
            self.send_dmx()
        
        
    def old_run(self):
        self.running.set()
        self.universe_obj.bind(value_update=self.on_universe_value_update)
        while self.running.isSet():
            self.need_update.wait(self.auto_update_interval)
            self.send_dmx()
            if not len(self.updates_to_send):
                self.need_update.clear()
            #else:
            #    print 'univ values added during transmission: ', self.updates_to_send
            self.refresh_wait.wait(self.refresh_interval)
            
    def old_stop(self):
        self.universe_obj.unbind(self.on_universe_value_update)
        self.running.clear()
        self.need_update.set()
    
    def add_node(self, **kwargs):
        node = kwargs.get('node')
        if node.id in self.subscribed_nodes:
            return
        self.subscribed_nodes[node.id] = node
        node.bind(OutputPorts=self.on_node_io_update)
        node.attached_universes.add(self.universe_obj.name)
        
    def del_node(self, **kwargs):
        node = kwargs.get('node')
        if node.id not in self.subscribed_nodes:
            return
        node.unbind(self)
        node.attached_universes.discard(self.universe_obj.name)
        del self.subscribed_nodes[node.id]
    
    def on_node_io_update(self, **kwargs):
        node = kwargs.get('obj')
        value = kwargs.get('value')
        if (self.subnet, self.universe_index) not in value:
            self.del_node(node=node)
        
    def on_universe_value_update(self, **kwargs):
        self.updates_to_send.add(kwargs.get('channel'))
        self.need_update.set()

        
class Node(BaseObject):
    _Properties = {'IPAddress':dict(type=str), 
                   'Port':dict(type=int), 
                   'ShortName':dict(type=str), 
                   'LongName':dict(type=str), 
                   'InputPorts':dict(default=[None]*4), 
                   'OutputPorts':dict(default=[None]*4), 
                   'attached_universes':dict(default=set()), 
                   'last_update':dict(fget='_last_update_getter', fset='_last_update_setter')}
    def __init__(self, **kwargs):
        super(Node, self).__init__(**kwargs)
        self.manager = kwargs.get('manager')
        self.data = {}
        self.fields = {}
        artpoll_reply = kwargs.get('artpoll_reply')
        self.set_data(artpoll_reply)
        self.id = artpoll_reply.Fields['MAC'].value
        self.style = artpoll_reply.Fields['Style'].codes.get(artpoll_reply.Fields['Style'].value)
        #self.bind(last_update=self.on_last_update_set)
    def _last_update_getter(self):
        return self.Properties['last_update'].value
    def _last_update_setter(self, value):
        prop = self.Properties['last_update']
        old = prop.value
        prop.value = value
        prop.emit(old)
    #def on_last_update_set(self, **kwargs):
    #    print '%s, last update: %s ' % (self.LongName, self.last_update)
        
#    @property
#    def id(self):
#        return self.artpoll_reply.Fields['MAC'].value
#    @property
#    def style(self):
#        field = self.artpoll_reply.Fields['Style']
#        return field.codes.get(field.value)
    def set_data(self, msg):
        self.last_update = datetime.datetime.now()
        for key, val in msg.Fields.iteritems():
            if 'Dummy' not in key:
                self.data[key] = val.value
                self.fields[key] = val.copy()
                if key in self.Properties:
                    setattr(self, key, val.value)
        self.update_port_info()
    def update_port_info(self):
        num_ports = self.data.get('NumPorts', 0)
        ptypes = self.data.get('PortTypes', [])
        allkeys = (('InputPorts','Swin'), ('OutputPorts', 'Swout'))
        subnet = self.data.get('SubSwitch', 0)
        current_info = dict(zip([keys[0] for keys in allkeys], [getattr(self, keys[0]) for keys in allkeys]))
        for i in range(num_ports):
            keys = None
            if ptypes[i] & 0x40 == 0x40:
                keys = allkeys[0]
            if ptypes[i] & 0x80 == 0x80:
                keys = allkeys[1]
            if keys:
                sub = self.data[keys[1]][i] / 0x10
                univ = self.data[keys[1]][i] % 0x10
                if current_info[keys[0]][i] != (sub, univ):
                    current_info[keys[0]][i] = (sub, univ)
    def __str__(self):
        return ', '.join([str(f) for f in self.fields.values()])
