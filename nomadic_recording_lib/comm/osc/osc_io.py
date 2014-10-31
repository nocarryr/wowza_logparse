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
# osc_io.py
# Copyright (c) 2011 Matthew Reid

import sys

import socket


from Bases import BaseObject
from osc_sender import UnicastOSCSender, MulticastOSCSender
from osc_receiver import UnicastOSCReceiver, MulticastOSCReceiver


#from ..BaseIO import BaseIO
from .. import BaseIO
from Bases import Config






class oscIO(BaseIO.BaseIO, Config):
    io_classes = {'Unicast':(UnicastOSCReceiver, UnicastOSCSender), 
                  'Multicast':(MulticastOSCReceiver, MulticastOSCSender)}
    _confsection = 'OSC'
    def __init__(self, **kwargs):
        self.Manager = kwargs.get('Manager')
        self.comm = self.Manager.comm
        BaseIO.BaseIO.__init__(self, **kwargs)
        Config.__init__(self, **kwargs)
        
        self.hostdata = {}
        self.hostdata_info = {'mcastaddr':{'conf':'multicast_address', 'default':'224.168.2.9'}, 
                              'mcastport':{'conf':'multicast_port', 'default':18889}, 
                              'hostaddr':{'conf':'host_address', 'default':BaseIO.detect_usable_address()}, 
                              'sendport':{'conf':'send_port', 'default':18889}, 
                              'recvport':{'conf':'recv_port', 'default':18888}}
        for k, v in self.hostdata_info.iteritems():
            val = kwargs.get(k, self.get_conf(v['conf'], v['default']))
            d = {k:type(v['default'])(val)}
            update = k in kwargs
            d.update({'update_conf':update})
            v.update({'update_conf':update})
            self.set_hostdata(**d)
        #print 'hostdata:',  self.hostdata
        self._iotype = None
        self._sender = None
        self._receiver = None
        
        
        
    @property
    def iotype(self):
        return self._iotype
    @iotype.setter
    def iotype(self, value):
        if value != self._iotype:
            self._iotype = value
            self.Manager.set_address_vars()
    
    def set_hostdata(self, **kwargs):
        for key, val in kwargs.iteritems():
            if key in self.hostdata_info:
                setattr(self, key, val)
                self.hostdata.update({key:val})
        update = kwargs.get('update_conf')
        if update is not None:
            del kwargs['update_conf']
            update = False
        if update:
            #self.update_conf(**kwargs)
            self.update_hostdata()
            
    def update_hostdata(self):
        for key in self.hostdata_info.iterkeys():
            self.hostdata.update({key:getattr(self, key)})
        d = {}
        for key, val in self.hostdata.iteritems():
            update = self.hostdata_info[key].get('update_conf', True)
            if update:
                d.update({self.hostdata_info[key]['conf']:val})
        self.update_conf(**d)
    
    def build_io(self, **kwargs):
        iotype = kwargs.get('iotype')
        if iotype is None:
            iotype = self.iotype
        update_conf = kwargs.get('update_conf', True)
        self.iotype = iotype
        iokwargs = {'root_address':self.Manager.root_address, 'osc_tree':self.Manager.osc_tree, 'osc_io':self}
        iokwargs.update(self.hostdata)
        if self.connected:
            self.do_disconnect()
        self._receiver = self.io_classes[iotype][0](**iokwargs)
        self._sender = self.io_classes[iotype][1](**iokwargs)
        if update_conf:
            self.update_conf(connection_type=iotype)
        
    def do_connect(self, **kwargs):
        self.update_hostdata()
        new_kwargs = kwargs.copy()
        new_kwargs.update(self.hostdata)
        if self._receiver is None and self._sender is None:
            self.build_io()
        try:
            for obj in [self._receiver, self._sender]:
                obj.do_connect(**kwargs)
            self.LOG.info('osc connected')
            self.connected = True
        except socket.error, msg:
            self.LOG.warning('osc socket error: ', msg)
        
    def do_disconnect(self, **kwargs):
        for obj in [self._receiver, self._sender]:
            obj.do_disconnect(**kwargs)
        self.connected = False
