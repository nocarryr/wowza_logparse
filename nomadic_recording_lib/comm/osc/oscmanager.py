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
# oscmanager.py
# Copyright (c) 2011 Matthew Reid

import threading
import time
import datetime
import socket

#from txosc import osc
#from Bases.osc_node import OSCNode, Bundle
from Bases import BaseObject, OSCBaseObject, BaseThread, ChildGroup, Config

from .. import BaseIO

from messages import Message, Bundle, Address, DoubleFloatArgument
from osc_node import OSCNode
from osc_io import oscIO
from osc_client import Client


def join_address(*args):
    s = '/'.join(['/'.join(arg.split('/')) for arg in args])
    return s
    
def issequence(obj):
    for t in [list, tuple, set]:
        if isinstance(obj, t):
            return True
    return False
    
def ip_to_int(ipstr):
    return int(''.join([s.rjust(3, '0') for s in ipstr.split('.')]))
    
class OSCManager(BaseIO.BaseIO, Config):
    _confsection = 'OSC'
    _Properties = {'app_address':dict(type=str), 
                   'master_priority':dict(default=10), 
                   'session_name':dict(type=str), 
                   'ring_master':dict(type=str), 
                   'epoch_offset':dict(default=0.)}
    def __init__(self, **kwargs):
        self.comm = kwargs.get('comm')
        BaseIO.BaseIO.__init__(self, **kwargs)
        Config.__init__(self, **kwargs)
        self.register_signal('client_added', 'client_removed', 'unique_address_changed', 'new_master')
        self.discovered_sessions = ChildGroup(name='discovered_sessions', 
                                              child_class=Session, 
                                              ignore_index=True)
        self.app_address = self.GLOBAL_CONFIG.get('app_name', self.get_conf('app_address', 'OSCApp'))
        self.default_root_address = kwargs.get('root_address', '%s-%s' % (self.app_address, socket.gethostname()))
        self.root_address = self.default_root_address
        self.wildcard_address = None
        self.master_priority = int(self.get_conf('master_priority', 10))
        self.GLOBAL_CONFIG['master_priority'] = self.master_priority
        s = self.GLOBAL_CONFIG.get('session_name')
        if s == 'None':
            s = None
        if s is not None:
            self.session_name = s
        else:
            self.session_name = socket.gethostname()
            self.GLOBAL_CONFIG['session_name'] = self.session_name
        self.osc_tree = OSCNode(name=self.app_address, 
                                root_node=True, 
                                transmit_callback=self.on_node_tree_send, 
                                get_client_cb=self.get_client, 
                                get_epoch_offset_cb=self.get_epoch_offset)
        #self.root_node = self.osc_tree.add_child(name=self.app_address)
        self.root_node = self.osc_tree
        #self.epoch_offset = datetime.timedelta()
        #self.epoch_offset = 0.
        self.clock_send_thread = None
        s = kwargs.get('use_unique_addresses', self.get_conf('use_unique_addresses', 'True'))
        flag = not s == 'False'
        
        #self.root_node.addCallback('/clocksync', self.on_master_sent_clocksync)
        #csnode = self.root_node.add_child(name='clocksync')
        #csnode.bind(message_received=self.on_master_sent_clocksync)
        #self.clocksync_node = csnode
        self.ioManager = oscIO(Manager=self)
        self.SessionManager = OSCSessionManager(Manager=self)
        self.SessionManager.bind(client_added=self.on_client_added, 
                                 client_removed=self.on_client_removed, 
                                 new_master=self.on_new_master)
        self.set_use_unique_address(flag, update_conf=False)
        io = kwargs.get('connection_type', self.get_conf('connection_type', 'Unicast'))
        self.ioManager.build_io(iotype=io, update_conf=False)
        self.ClockSync = ClockSync(osc_parent_node=self.root_node, 
                                   clients=self.clients)
        self.ClockSync.bind(offset=self.on_ClockSync_offset_set)
        
    @property
    def oscMaster(self):
        return self.SessionManager.oscMaster
    @property
    def isMaster(self):
        return self.SessionManager.isMaster
    @property
    def isRingMaster(self):
        return self.SessionManager.isRingMaster
    @property
    def clients(self):
        return self.SessionManager.clients
    @property
    def local_client(self):
        return self.SessionManager.local_client
        
    def get_epoch_offset(self):
        return self.epoch_offset
        
    def do_connect(self, **kwargs):
        self.SessionManager.do_connect()
        self.ioManager.do_connect(**kwargs)
        self.connected = True
        
    def do_disconnect(self, **kwargs):
        #self.stop_clock_send_thread(blocking=True)
        self.ClockSync.isMaster = False
        self.ioManager.do_disconnect(**kwargs)
        self.SessionManager.do_disconnect(**kwargs)
        self.connected = False
        
    def shutdown(self):
        self.do_disconnect(blocking=True)
        self.osc_tree.unlink_all(direction='down', blocking=True)
        
        
    def set_use_unique_address(self, flag, update_conf=True):
        self.use_unique_address = flag
        if update_conf:
            self.update_conf(use_unique_addresses=flag)
        self.set_address_vars()
        self.emit('unique_address_changed', state=flag)
    
    def set_address_vars(self):
        return
        if self.ioManager.iotype == 'Multicast' or self.use_unique_address:
            self.root_address = self.default_root_address
            #self.SessionManager.add_client_name(None, update_conf=False)
        else:
            self.root_address = self.app_address
            self.root_node.name = self.root_address
            
    def update_wildcards(self):
        return
        #if self.wildcard_address:
        #    self.osc_tree._wildcardNodes.discard(self.wildcard_address)
        #    self.osc_tree._wildcardNodes.discard('{null}')
        names = []
        for c in self.clients.itervalues():
            if not c.isLocalhost:
                names.append(c.osc_name)
        if names:
            s = '{%s}' % (','.join(names))
            self.wildcard_address = s
            self.root_node.name = s
            #self.osc_tree._wildcardNodes.add(s)
            #print 'wildcard = ', s
            #print 'root_node = ', s
            #print 'wcnodes = ', self.osc_tree._wildcardNodes
        
    def get_client(self, **kwargs):
        hostaddr = kwargs.get('hostaddr')[0]
        #print hostaddr, self.clients_by_address
        return self.SessionManager.clients_by_address.get(hostaddr)
        
    def on_node_tree_send(self, **kwargs):
        clients = kwargs.get('clients')
        client_name = kwargs.get('client')
        element = kwargs.get('element')
#        timetag = kwargs.get('timetag')
#        if timetag is not None:
#            del kwargs['timetag']
        to_master = kwargs.get('to_master', client_name is None and not self.isMaster)
        if to_master:
            client_name = self.oscMaster
        if clients is None:
            client = self.clients.get(client_name)
            if client is not None:
                clients = [client]
#        address = kwargs.get('address')
#        #root_address = kwargs.get('root_address', self.root_address)
        all_sessions = kwargs.get('all_sessions', False)
#        #address[0] = root_address
#        if not isinstance(address, Address):
#            address = Address(address)
#        #junk, address = address.pop()
#        #address = address.append_right(root_address)
#        
#        #path = '/' + join_address(*address)
#        #if path[-1:] == '/':
#        #    path = path[:-1]
#        args = self.pack_args(kwargs.get('value'))
#        msg = Message(*args, address=address)
#        bundle = Bundle(msg, timetag=timetag)
        
        _sender = self.ioManager._sender
        if _sender is None:
            return
        _sender.preprocess(element)
        if isinstance(element, Bundle):
            messages = element.get_flat_messages()
        else:
            messages = [element]
        if self.ioManager.iotype == 'Multicast':
            #print 'osc_send: ', msg
            _sender._send(element)
            return
        if self.ioManager.iotype != 'Unicast':
            return
            
        if clients is None:
            clients = set()
            for c in self.clients.itervalues():
                if all_sessions:
                    if c.sendAllUpdates:
                        clients.add(c)
                else:
                    if c.sendAllUpdates and c.isSameSession:
                        clients.add(c)
        for c in clients:
            if c.accepts_timetags:
                _sender._send(element, c.hostaddr)
            else:
                for msg in messages:
                    _sender._send(msg, c.hostaddr)
    
    def pack_args(self, value):
        if isinstance(value, list) or isinstance(value, tuple):
            return value
        elif value is None:
            return []
        return [value]
        
    def on_ClockSync_offset_set(self, **kwargs):
        self.epoch_offset = kwargs.get('value')
        
    def start_clock_send_thread(self):
        self.stop_clock_send_thread()
        self.clock_send_thread = ClockSender(osc_node=self.clocksync_node, 
                                             time_method='timestamp', 
                                             clients=self.clients)
        self.clock_send_thread.start()
        
    def stop_clock_send_thread(self, blocking=True):
        if self.clock_send_thread is None:
            return
        self.clock_send_thread.stop(blocking=blocking)
        self.clock_send_thread = None
            
    def on_master_sent_clocksync(self, **kwargs):
        msg = kwargs.get('message')
        value = msg.get_arguments()[0]
        #dt = datetime.datetime.strptime(value, '%Y%m%d %H:%M:%S %f')
        #now = datetime.datetime.fromtimestamp(msg.timestamp)
        now = time.time()
        #print 'msg.timestamp: ', msg.timestamp
        #tsnow = datetime.datetime.fromtimestamp(msg.timestamp)
        #print 'now=%s, tsnow=%s' % (now, tsnow)
        self.epoch_offset = now - value
        #print 'epoch_offset: ', self.epoch_offset
        
    def on_client_added(self, **kwargs):
        self.emit('client_added', **kwargs)
        
    def on_client_removed(self, **kwargs):
        self.emit('client_removed', **kwargs)
        
    def on_new_master(self, **kwargs):
        self.emit('new_master', **kwargs)
            
class OSCSessionManager(BaseIO.BaseIO, Config):
    _confsection = 'OSC'
    _Properties = {'oscMaster':dict(type=str)}
    def __init__(self, **kwargs):
        self.Manager = kwargs.get('Manager')
        self.ioManager = self.Manager.ioManager
        self.comm = self.Manager.comm
        self.root_node = self.Manager.root_node
        self.osc_tree = self.Manager.osc_tree
        BaseIO.BaseIO.__init__(self, **kwargs)
        Config.__init__(self, **kwargs)
        self.register_signal('client_added', 'client_removed', 'new_master')
        #self.oscMaster = None
        self.bind(oscMaster=self._on_oscMaster_set)
        self.set_master_timeout = None
        self.master_takeover_timer = None
        self.check_master_attempts = None
        self.local_client = None
        self.clients = ChildGroup(name='clients', 
                                  osc_address='CLIENTS', 
                                  osc_parent_node=self.root_node, 
                                  child_class=Client, 
                                  ignore_index=True)
        self.clients_by_address = {}
        #self.root_node.addCallback('/getMaster', self.on_master_requested_by_osc)
        #self.root_node.addCallback('/setMaster', self.on_master_set_by_osc)
        #self.getMasterNode = self.root_node.add_child(name='getMaster')
        #self.getMasterNode.bind(message_received=self.on_master_requested_by_osc)
        #self.setMasterNode = self.root_node.add_child(name='setMaster')
        #self.setMasterNode.bind(message_received=self.on_master_set_by_osc)
        self.GLOBAL_CONFIG.bind(update=self.on_GLOBAL_CONFIG_update)
        if self.GLOBAL_CONFIG.get('osc_use_discovery', True):
            self.comm.ServiceConnector.connect('new_host', self.on_host_discovered)
            self.comm.ServiceConnector.connect('remove_host', self.on_host_removed)
        
        self.Manager.bind(master_priority=self._on_master_priority_set, 
                          session_name=self._on_session_name_set, 
                          ring_master=self._on_ring_master_set)
    
    @property
    def root_address(self):
        return self.Manager.root_address
    @property
    def local_name(self):
        if not self.local_client:
            return '-'.join([self.GLOBAL_CONFIG.get('app_name'), socket.gethostname()])
        return self.local_client.name
    @property
    def isMaster(self):
        return self.oscMaster == self.local_name
    @property
    def isRingMaster(self):
        return self.Manager.ring_master == self.local_name
    @property
    def master_priority(self):
        return self.Manager.master_priority
    @master_priority.setter
    def master_priority(self, value):
        self.Manager.master_priority = value
    @property
    def discovered_sessions(self):
        return self.Manager.discovered_sessions
    @property
    def session_name(self):
        return self.Manager.session_name
    @session_name.setter
    def session_name(self, value):
        self.Manager.session_name = value
        
    def determine_ring_master(self):
        masters = {}
        for session in self.discovered_sessions.itervalues():
            m = session.master
            if m is None:
                continue
            #key = int(''.join([s.rjust(3, '0') for s in m.address.split('.')]))
            key = ip_to_int(m.address)
            masters[key] = m
        if not len(masters):
            return False
        master = masters[min(masters.keys())]
        if master.name != self.Manager.ring_master:
            self.Manager.ring_master = master.name
        return master
        
    def do_connect(self):
        serv = self.comm.ServiceConnector.add_service(**self.build_zeroconf_data())
        self.comm.ServiceConnector.add_listener(stype='_osc._udp')
        self.connected = True
        self.check_for_master()
        
    def do_disconnect(self, **kwargs):
        self.set_master(False)
        self.connected = False
        
    def add_to_session(self, **kwargs):
        ''' Adds a Client obj to a Session object which will handle
        master determination, etc.  If the Session does not exist,
        one is created.
        '''
        name = kwargs.get('name')
        if name is None:
            return
        client = kwargs.get('client')
        clients = kwargs.get('clients', [])
        if client is not None:
            clients.append(client)
        sessions = self.discovered_sessions
        session = sessions.get(name)
        if session:
            for c in clients:
                session.add_member(c)
        else:
            prebind = dict(master=self.on_session_master_set, 
                           members_update=self.on_session_members_update)
            session = sessions.add_child(name=name, members=clients, prebind=prebind)
            
    def remove_from_session(self, **kwargs):
        ''' Removes a Client object (or objects) from a Session object,
        if it exists.
        '''
        name = kwargs.get('name')
        client = kwargs.get('client')
        clients = kwargs.get('clients', [])
        if client is not None:
            clients.append(client)
        sessions = self.discovered_sessions
        session = sessions.get(name)
        if not session:
            return
        for c in clients:
            session.del_member(c)
        
    def add_client(self, **kwargs):
        kwargs.setdefault('port', self.ioManager.hostdata['sendport'])
        kwargs.setdefault('app_address', self.Manager.app_address)
        #kwargs['osc_parent_node'] = self.client_osc_node
        if socket.gethostname() in kwargs.get('name', ''):
            kwargs['isLocalhost'] = True
            #kwargs['master_priority'] = self.master_priority
        client = self.clients.add_child(**kwargs)
        self.clients_by_address[client.address] = client
        if client.isLocalhost:
            self.local_client = client
            #client.master_priority = self.master_priority
            #print 'local_client session: ', client.session_name
        self.add_to_session(name=client.session_name, client=client)
        client.bind(property_changed=self.on_client_obj_property_changed)
        #if client.session_name is not None:
        #    self.discovered_sessions.add(client.session_name)
        self.Manager.update_wildcards()
        #if self.check_master_attempts is None:
        #    self.check_for_master(client=client.name)
        propkeys = client.Properties.keys()
        self.LOG.info('add_client:', dict(zip(propkeys, [client.Properties[key].value for key in propkeys])))
        keys = ['name', 'address', 'port']
        s_kwargs = dict(zip(keys, [getattr(client, key) for key in keys]))
        s_kwargs.update({'client':client})
        self.emit('client_added', **s_kwargs)
        
    def remove_client(self, **kwargs):
        name = kwargs.get('name')
        client = self.clients.get(name)
        if client is None:
            return
        #self.remove_client_name(name, update_conf=False)
        #self.remove_client_address(addr, update_conf=False)
        client.unbind(self)
        self.clients.del_child(client)
        self.Manager.update_wildcards()
        self.LOG.info('remove_client:', name)
        self.emit('client_removed', name=name, client=client)
        if client.session_name is not None:
            self.remove_from_session(name=client.session_name, client=client)
    
    def on_session_master_set(self, **kwargs):
        session = kwargs.get('obj')
        value = kwargs.get('value')
        self.determine_ring_master()
        if session.name != self.session_name:
            return
        if session.master is None:
            m = self.determine_next_master()
            if m == self.local_client:
                self.set_master()
        if session.master.name == self.oscMaster:
            return
        if session.master != self.local_client:
            self.set_master(session.master.name)
            
    def on_session_members_update(self, **kwargs):
        session = kwargs.get('obj')
        mode = kwargs.get('mode')
        if mode == 'remove':
            if not len(session.members):
                session.unbind(self)
                self.discovered_sessions.del_child(session)
            
    def on_client_obj_property_changed(self, **kwargs):
        prop = kwargs.get('Property')
        old = kwargs.get('old')
        value = kwargs.get('value')
        client = kwargs.get('obj')
        if prop.name == 'isRingMaster' and value is True:
            if self.Manager.ring_master != client.name:
                self.Manager.ring_master = client.name
        elif prop.name == 'session_name' and value is not None:
            self.add_to_session(name=value, client=client)
            
    def build_zeroconf_data(self):
        d = dict(name=self.local_name, 
                 stype='_osc._udp', 
                 port=self.Manager.ioManager.hostdata['recvport'])
        txt = {'app_name':self.GLOBAL_CONFIG['app_name']}
        #session = self.GLOBAL_CONFIG.get('session_name')
        #if session:
        #    txt['session_name'] = session
        d['text'] = txt
        return d
        
    def build_curly_wildcard(self, l):
        return '{%s}' % (','.join(list(l)))
        
    def _on_master_priority_set(self, **kwargs):
        value = kwargs.get('value')
        #if self.local_client is not None:
        #    self.local_client.master_priority = value
        self.GLOBAL_CONFIG['master_priority'] = value
        self.update_conf(master_priority=value)
        #data = self.build_zeroconf_data()
        #self.comm.ServiceConnector.update_service(**data)
        
    def _on_session_name_set(self, **kwargs):
        value = kwargs.get('value')
        #if self.local_client is not None:
        #    self.local_client.session_name = value
        #    self.local_client.isMaster = False
        
        #data = self.build_zeroconf_data()
        #self.comm.ServiceConnector.update_service(**data)
        #self.select_new_master()
        if self.local_client is not None:
            self.add_to_session(name=value, client=self.local_client)
            #self.local_client.session_name = value
            master = self.discovered_sessions[value].master
            if master is not None:
                master = master.name
            self.set_master(master)
        self.GLOBAL_CONFIG['session_name'] = value
        
    def on_GLOBAL_CONFIG_update(self, **kwargs):
        keys = kwargs.get('keys')
        if not keys:
            keys = [kwargs.get('key')]
        for key in ['master_priority', 'session_name']:
            if key not in keys:
                continue
            value = self.GLOBAL_CONFIG.get(key)
            if value != getattr(self, key):
                setattr(self, key, value)
        
    def on_host_discovered(self, **kwargs):
        host = kwargs.get('host')
        if '.' not in host.address:
            return
        c_kwargs = host.hostdata.copy()
        c_kwargs.update({'discovered':True})
        self.add_client(**c_kwargs)
        
    def on_host_removed(self, **kwargs):
        self.LOG.info('remove:', kwargs)
        id = kwargs.get('id')
        self.remove_client(name=id)
        
    def check_for_master(self, **kwargs):
        if self.connected and not self.isMaster:
            name = kwargs.get('name')
            #if self.check_master_attempts is None:
            #    self.check_master_attempts = 0
            #self.cancel_check_master_timer()
            self.set_master_timeout = threading.Timer(10.0, self.on_check_master_timeout)
            self.set_master_timeout.start()
            #new_kwargs = {}#{'address':'getMaster'}
            #if name:
            #    new_kwargs.update({'client':name})
            #element = self.getMasterNode.send_message(value=self.session_name, 
            #                                          all_sessions=True, 
            #                                          timetag=-1)
            #print 'sent getmaster: ', [str(element)]
            
    def on_check_master_timeout(self):
        self.set_master()
        return
        self.check_master_attempts += 1
        if self.check_master_attempts == 3:
            self.check_master_attempts = None
            self.set_master()
        else:
            self.check_for_master()
        
    def set_master(self, name=None):
        self.cancel_check_master_timer()
        if self.master_takeover_timer:
            self.master_takeover_timer.cancel()
        if name is None:
            s = self.local_name
        elif name is False:
            s = None
        else:
            s = name
        if s != self.oscMaster:
            self.oscMaster = s
            if self.oscMaster is None:
                return
            lc = self.local_client
            if self.isMaster:
                if lc is not None:
                    lc.isMaster = True
            else:
                if lc is not None:
                    lc.isMaster = False
                m = self.determine_next_master()
                if m and m.isLocalhost and name is not False:
                    self.LOG.info('master takeover in 10 seconds...')
                    t = threading.Timer(10.0, self.on_master_takeover_timeout)
                    self.master_takeover_timer = t
                    t.start()
        self.LOG.info('master = ', self.oscMaster)
        self.determine_ring_master()
        self.emit('new_master', master=self.oscMaster, master_is_local=self.isMaster)
        
    def on_master_takeover_timeout(self):
        self.LOG.info('master takeover timer complete')
        self.master_takeover_timer = None
        m = self.determine_next_master()
        if not m:
            return
        if not self.isMaster and m.isLocalhost:
            self.set_master()
            
    def cancel_check_master_timer(self):
        if self.set_master_timeout and self.set_master_timeout.isAlive():
            self.set_master_timeout.cancel()
            self.set_master_timeout = None
            
    def determine_next_master(self):
        session = self.discovered_sessions[self.session_name]
        d = {}
        for c in session.members.itervalues():
            key = c.master_priority
            if key is None:
                continue
            if not (c.isSlave or c.isMaster or c.isLocalhost):
                continue
            if key in d and ip_to_int(c.address) > ip_to_int(d[key].address):
                continue
            d[key] = c
        self.LOG.info('clients by priority: ', d)
        if not len(d):
            return None
        return d[min(d)]
        
    def old_determine_next_master(self):
        d = {}
        for client in self.clients.itervalues():
            if not client.isSameSession:
                continue
            key = client.master_priority
            if key is not None and (client.isSlave or client.isMaster or client.isLocalhost):
                if key in d:
                    if d[key].name < client.name:
                        d[key] = client
                else:
                    d[key] = client
        self.LOG.info('clients by priority: ', d)
        if not len(d):
            return None
        return d[min(d)]
        
    def _on_ring_master_set(self, **kwargs):
        value = kwargs.get('value')
        self.LOG.info('RINGMASTER: ', value)
        self.local_client.isRingMaster = value == self.local_name
        self.Manager.ClockSync.isMaster = self.isRingMaster
            
    def _on_oscMaster_set(self, **kwargs):
        self.root_node.oscMaster = self.isMaster
        
class Session(BaseObject):
    _Properties = {'master':dict(ignore_type=True)}
                   #'members':dict(default={})}
    _ChildGroups = {'members':dict(ignore_index=True)}
    signals_to_register = ['members_update']
    def __init__(self, **kwargs):
        super(Session, self).__init__(**kwargs)
        self.members.bind(child_update=self._on_members_update)
        self.name = kwargs.get('name')
        self.id = self.name
        self.master = kwargs.get('master')
        members = kwargs.get('members', [])
        for m in members:
            self.add_member(m)
    def add_member(self, member):
        #self.LOG.info('SESSION %s adding member %s' % (self.name, member))
        if member.session_name != self.name:
            member.session_name = self.name
        if member.isMaster:
            if self.master is None:
                self.master = member
            else:
                member.isMaster = False
        member.bind(session_name=self.on_member_session_name_set, 
                    isMaster=self.on_member_isMaster_set)
        self.members.add_child(existing_object=member)
        #self.LOG.info('SESSION %s members: %s' % (self.name, [str(m) for m in self.members.values()]))
        
    def del_member(self, member):
        if type(member) == str:
            member = self.members.get(member)
        if not isinstance(member, Client):
            return
        if member.name not in self.members:
            return
        #self.LOG.info('SESSION %s deleting member %s' % (self.name, member))
        member.unbind(self)
        if member.session_name == self.name:
            member.session_name = None
        self.members.del_child(member, unlink=False)
        if self.master is not None and self.master.name not in self.members:
            self.master = None
    def on_member_session_name_set(self, **kwargs):
        #self.LOG.info('%s member session_name set: %s' % (self.name, kwargs))
        old = kwargs.get('old')
        value = kwargs.get('value')
        member = kwargs.get('obj')
        if old == self.name and value != self.name:
            self.del_member(member)
        if self.master is not None and self.master.name not in self.members:
            self.master = None
    def on_member_isMaster_set(self, **kwargs):
        #self.LOG.info('%s member isMaster set: %s' % (self.name, kwargs))
        value = kwargs.get('value')
        member = kwargs.get('obj')
        if member.session_name == self.name and value:
            self.master = member
            return
        if self.master and self.master.name not in self.members:
            self.master = None
    def _on_members_update(self, **kwargs):
        new_kwargs = kwargs.copy()
        new_kwargs['obj'] = self
        self.emit('members_update', **new_kwargs)
        
class ClockSync(OSCBaseObject):
    _Properties = {'isMaster':dict(default=False), 
                   'offset':dict(default=0.)}
    def __init__(self, **kwargs):
        kwargs.setdefault('osc_address', 'clocksync')
        super(ClockSync, self).__init__(**kwargs)
        self.clients = kwargs.get('clients')
        self.clock_send_thread = None
        self.clock_times = {}
        self.nodes = {}
        for key in ['sync', 'DelayReq', 'DelayResp']:
            node = self.osc_node.add_child(name=key)
            method = getattr(self, 'on_%s_message_received' % (key))
            node.bind(message_received=method)
            self.nodes[key] = node
        self.bind(isMaster=self._on_isMaster_set, 
                  offset=self._on_offset_set)
        
    def _on_isMaster_set(self, **kwargs):
        value = kwargs.get('value')
        if value:
            self.start_clock_send_thread()
        else:
            self.stop_clock_send_thread()
            
    def start_clock_send_thread(self):
        self.stop_clock_send_thread()
        self.offset = 0.
        self.clock_send_thread = ClockSender(osc_node=self.nodes['sync'], 
                                             clients=self.clients, 
                                             time_method='timestamp')
        self.clock_send_thread.start()
        
    def stop_clock_send_thread(self, blocking=True):
        if self.clock_send_thread is None:
            return
        self.clock_send_thread.stop(blocking=blocking)
        self.clock_send_thread = None
        
    def on_sync_message_received(self, **kwargs):
        msg = kwargs.get('message')
        times = self.clock_times
        times['master_sync'] = msg.get_arguments()[0]
        times['local_sync'] = msg.timestamp
        #self.delay_req_timestamp = msg.timestamp
        self.nodes['DelayReq'].send_message(client=msg.client, timetag=-1, all_sessions=True)
        
    def on_DelayReq_message_received(self, **kwargs):
        msg = kwargs.get('message')
        value = DoubleFloatArgument(msg.timestamp)
        self.nodes['DelayResp'].send_message(value=value, client=msg.client, timetag=-1, all_sessions=True)
        
    def on_DelayResp_message_received(self, **kwargs):
        msg = kwargs.get('message')
        times = self.clock_times
        times['master_resp'] = msg.get_arguments()[0]
        times['local_resp'] = msg.timestamp
        #netdelay = times['master_resp'] - times['local_resp']
        netdelay = times['local_sync'] - times['local_resp']
        times['netdelay'] = netdelay
        self.offset = times['local_sync'] - times['master_sync']# - (netdelay / 2.)
        #print ['='.join([key, times[key].__repr__()]) for key in ['master_sync', 'local_sync', 'master_resp', 'local_resp', 'netdelay']]
        #print 'offset: ', self.offset.__repr__()
        
    def _on_offset_set(self, **kwargs):
        offset = kwargs.get('value')
        #self.LOG.info('OSC offset = ' + offset.__repr__())
        
class ClockSender(BaseThread):
    def __init__(self, **kwargs):
        kwargs['thread_id'] = 'OSCManager_ClockSender'
        super(ClockSender, self).__init__(**kwargs)
        self._threaded_call_ready.wait_timeout = 10.
        #self.running = threading.Event()
        #self.sending = threading.Event()
        #self.Manager = kwargs.get('Manager')
        self.osc_node = kwargs.get('osc_node')
        self.clients = kwargs.get('clients')
        time_method = kwargs.get('time_method', 'datetime')
        self.time_method = getattr(self, time_method)
        #self.osc_address = kwargs.get('osc_address', 'clocksync')
        #self.interval = kwargs.get('interval', 10.)
    def datetime(self):
        now = datetime.datetime.now()
        return now.strftime('%Y%m%d %H:%M:%S %f')
    def timestamp(self):
        return DoubleFloatArgument(time.time())
    def _thread_loop_iteration(self):
        if not self._running:
            return
        clients = [c for c in self.clients.values() if c.sendAllUpdates and c.accepts_timetags]# and c.isSameSession]
        #now = datetime.datetime.now()
        #value = now.strftime('%Y%m%d %H:%M:%S %f')
        #value = time.time()
        value = self.time_method()
        self.osc_node.send_message(value=value, 
                                   timetag=-1, 
                                   clients=clients)
    def old_run(self):
        self.running.set()
        self.send_clock()
        while self.running.isSet():
            self.sending.wait(self.interval)
            if self.running.isSet():
                self.send_clock()
            self.sending.clear()
    def old_stop(self):
        self.running.clear()
        self.sending.set()
