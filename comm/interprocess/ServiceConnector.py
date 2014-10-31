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
# ServiceConnector.py
# Copyright (c) 2011 Matthew Reid

import sys

from Bases import BaseObject

from SystemData import SystemData
from pybonjour_browsepublish import Publisher, Browser

class ServiceConnector(BaseObject):
    def __init__(self, **kwargs):
        super(ServiceConnector, self).__init__(**kwargs)
        self.register_signal('new_host', 'remove_host', 'host_connection', 'got_local_address')
        self.system = self.GLOBAL_CONFIG.get('SystemData')
        if not self.system:
            self.system = SystemData()
        self.hosts = {}
        self.services = {}
        self.listeners = {}
        self.published = False
        
            
    def add_service(self, **kwargs):
        serv = Publisher(**kwargs)
        self.services.update({serv.name:serv})
        if self.published:
            serv.publish()
        return serv
        
    def update_service(self, **kwargs):
        serv = self.services.get(kwargs.get('name'))
        if serv:
            serv.update(**kwargs)
        
    def add_listener(self, **kwargs):
        l = Browser(**kwargs)
        l.connect('new_host', self.on_new_host)
        l.connect('remove_host', self.on_remove_host)
        self.listeners.update({l.id:l})
        if self.published:
            l.do_connect()
        return l
        
    def publish(self, servicename=None):
        if servicename is None:
            for key, service in self.services.iteritems():
                #try:
                service.publish()
                #except:
                #    print 'could not publish service:', key
        elif servicename in self.services:
            self.services[servicename].publish()
        for l in self.listeners.itervalues():
            l.do_connect()
        self.published = True
            
    def unpublish(self, servicename=None, blocking=False):
        if servicename is None:
            for service in self.services.itervalues():
                service.unpublish(blocking=blocking)
        elif servicename in self.services:
            self.services[servicename].unpublish(blocking=blocking)
        for l in self.listeners.itervalues():
            l.do_disconnect(blocking=blocking)
        self.published = False
            
    def on_new_host(self, **kwargs):
        data = kwargs.get('data')
        if True:# data['hostname'] != self.system.hostname:
            host = Host(data)
            self.hosts.update({host.id:host})
            self.emit('new_host', host=host)
        if self.system.address is None:
            self.system.address = data['address']
            self.emit('got_local_address', address=data['address'])
    def on_remove_host(self, **kwargs):
        data = kwargs.get('data')
        hostid = None
        for key, val in self.hosts.iteritems():
            if val.name == data['name'] and val.stype == data['stype']:
                hostid = key
        if hostid is not None and hostid in self.hosts:
            del self.hosts[hostid]
            self.emit('remove_host', id=hostid)
    def set_host_connected(self, id, state):
        if id in self.hosts:
            self.hosts[id].connected = state
            self.emit('host_connection', id=id, state=state)

class Host(object):
    def __init__(self, hostdata, connected=False):
        for key, val in hostdata.iteritems():
            setattr(self, key, val)
        self.id = self.name
        self.hostdata = hostdata
        self.connected = connected
        

class ServiceInfo(object):
    def __init__(self, servname, classObj, **kwargs):
        self.name = servname
        self.classObj = classObj
        self._kwargs = kwargs
        if 'name' in kwargs:
            self._kwargs.update({'name':kwargs.get('name') + '-' + self.name})



if __name__ == '__main__':
    from SystemData import SystemData
    import gtk
    sysdata = SystemData()
    servconnector = ServiceConnector(sysdata)
    gtk.main()
