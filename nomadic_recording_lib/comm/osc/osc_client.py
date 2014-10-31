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
# osc_client.py
# Copyright (c) 2011 Matthew Reid

import threading
import socket
from Bases import OSCBaseObject

class Client(OSCBaseObject):
    _Properties = {'name':dict(type=str), 
                   'address':dict(type=str), 
                   'port':dict(type=int), 
                   'hostname':dict(type=str), 
                   'session_name':dict(type=str), 
                   'isMaster':dict(default=False), 
                   'isSlave':dict(default=False), 
                   'isLocalhost':dict(default=False), 
                   'isRingMaster':dict(default=False), 
                   'isSameSession':dict(default=False), 
                   'master_priority':dict(type=int)}
    def __init__(self, **kwargs):
        self._sendAllUpdates = False
        self._isSlave = False
        if 'name' in kwargs:
            kwargs.setdefault('osc_address', kwargs['name'])
        super(Client, self).__init__(**kwargs)
        
        self.app_address = kwargs.get('app_address')
        self.name = kwargs.get('name')
        self.isLocalhost = kwargs.get('isLocalhost', socket.gethostname() in self.name)
        self.master_priority = kwargs.get('master_priority')
        
        self.address = kwargs.get('address')
        self.port = kwargs.get('port')
        self.hostaddr = (self.address, self.port)
        self.hostname = kwargs.get('hostname')
        if self.osc_name != self.name:
            self.set_osc_address(self.osc_name)
        txt = kwargs.get('text', {})
        self.app_name = kwargs.get('app_name', txt.get('app_name'))
        #self.app_name = txt.get('app_name')
        #mp = txt.get('master_priority')
        #if mp is not None and self.master_priority is None:
        #    self.master_priority = int(mp)
        if self.isLocalhost:
            local_name = self.GLOBAL_CONFIG.get('osc_local_client_name')
            if local_name is not None:
                self.name = local_name
                self.set_osc_address(self.name)
            self.master_priority = self.GLOBAL_CONFIG.get('master_priority')
            self.session_name = self.GLOBAL_CONFIG.get('session_name')
            self.app_name = self.GLOBAL_CONFIG.get('app_name')
        else:
            self.session_name = kwargs.get('session_name')
            #self.session_name = txt.get('session_name')
        if self.session_name == '':
            self.session_name = None
        
        self.isMaster = kwargs.get('isMaster', False)
        self.discovered = kwargs.get('discovered', False)
        self.accepts_timetags = kwargs.get('accepts_timetags', True)
        self.isSameSession = self.session_name == self.GLOBAL_CONFIG.get('session_name')
        self.update_timer = None
        for key in ['isMaster', 'isRingMaster', 'session_name', 'master_priority']:
            h = self.add_osc_handler(Property=key, 
                                     all_sessions=True, 
                                     use_timetags=False, 
                                     request_initial_value=False)
        if self.app_name is not None and not self.isLocalhost:
            self.update_timer = threading.Timer(2., self.on_update_timer)
            self.LOG.info('waiting to request props for client ', self.name)
            self.update_timer.start()
        self.GLOBAL_CONFIG.bind(update=self.on_GLOBAL_CONFIG_update)
        self.bind(property_changed=self._on_own_property_changed)
        
        #print 'client: name=%s, local=%s, master=%s, slave=%s, sendall=%s' % (self.name, self.isLocalhost, self.isMaster, self.isSlave, self.sendAllUpdates)
    
    def unlink(self):
        if self.update_timer is not None:
            self.update_timer.cancel()
        self.GLOBAL_CONFIG.unbind(self)
        super(Client, self).unlink()
        
    @property
    def id(self):
        return self.name
    @property
    def osc_name(self):
        if ' ' in self.name:
            if self.hostname is not None:
                return self.hostname.split('.')[0]
            return '_'.join(self.name.split(' '))
        return self.name
#    @property
#    def isMaster(self):
#        return self._isMaster
#    @isMaster.setter
#    def isMaster(self, value):
#        if value != self._isMaster:
#            self._isMaster = value

#    @property
#    def isSlave(self):
#        return (self.app_address in self.name and self.isSameSession 
#                and not self.isLocalhost and not self.isMaster)
        
#    @property
#    def isSameSession(self):
#        return self.session_name == self.GLOBAL_CONFIG.get('session_name')
    
    @property
    def sendAllUpdates(self):
        if self._sendAllUpdates:
            return True
        return (self.isMaster or self.isSlave) and not self.isLocalhost
    @sendAllUpdates.setter
    def sendAllUpdates(self, value):
        self._sendAllUpdates = value
        
    def on_update_timer(self):
        self.update_timer = None
        self.LOG.info('requesting props for client ', self.name)
        self.refresh_osc_properties()
        
    def refresh_osc_properties(self):
        if self.isLocalhost:
            return
        for h in self.osc_handlers.itervalues():
            #if h.Property is None:
            #    continue
            h.request_Property_value(clients=[self])
        
    def _on_own_property_changed(self, **kwargs):
        prop = kwargs.get('Property')
        if prop.name != 'isSlave':
            self.isSlave = (self.app_address in self.name
                            and not self.isLocalhost and not self.isMaster)
        elif prop.name != 'isSameSession':
            self.isSameSession = self.session_name == self.GLOBAL_CONFIG.get('session_name')
        if prop.name == 'session_name' and self.isLocalhost:
            self.isMaster = False
            
            
    def on_GLOBAL_CONFIG_update(self, **kwargs):
        keys = kwargs.get('keys')
        if keys is None:
            keys = [kwargs.get('key')]
        if self.isLocalhost:
            for key in ['session_name', 'master_priority']:
                if key not in keys:
                    continue
                if getattr(self, key) ==  self.GLOBAL_CONFIG[key]:
                    continue
                setattr(self, key, self.GLOBAL_CONFIG[key])
        else:
            self.isSameSession = self.session_name == self.GLOBAL_CONFIG.get('session_name')
        
    def __str__(self):
        return '<OSCClient %s: isMaster=%s>' % (self.name, self.isMaster)
    def __repr__(self):
        s = super(Client, self).__repr__()
        s = s[:-1]
        s += ' (%s)>' % (self.name)
        return s
