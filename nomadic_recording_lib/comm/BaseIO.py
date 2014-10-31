#  This file is part of OpenLightingDesigner.
# 
#  OpenLightingDesigner is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  OpenLightingDesigner is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with OpenLightingDesigner.  If not, see <http://www.gnu.org/licenses/>.
#
# BaseIO.py
# Copyright (c) 2010 - 2011 Matthew Reid

import socket
import uuid

from Bases import BaseObject

def detect_usable_address():
    for addr in socket.gethostbyname_ex(socket.gethostname())[2]:
        if addr.split('.')[0] != '127':
            return addr
    return socket.gethostbyname('.'.join([socket.gethostname(), 'local']))
    
def get_mac_address(out_type=None):
    if out_type is None:
        out_type = int
    return out_type(uuid.getnode())

class BaseIO(BaseObject):
    _Properties = {'connected':dict(default=False)}
    def __init__(self, **kwargs):
        super(BaseIO, self).__init__(**kwargs)
        self.register_signal('state_changed')
        self.register_signal('data_received')
        #self._connected = False
        
        self.client = None
        self.bind(connected=self._on_connected_set)
        
    def _send(self, data):
        pass
            
    def on_data_received(self, *args, **kwargs):
        data = kwargs.get('data')
        if data is None:
            data = args[0]
        self.emit('data_received', data=data, client=self)
        
    def on_client_disconnect(self, connector, reason):
        self.client = None
        self.connected = False
        #self.emit('state_changed', state=False)
        
    def do_connect(self, *args, **kwargs):
        pass
        
    def do_disconnect(self, **kwargs):
        pass
        
#    @property
#    def connected(self):
#        return self._connected
#    @connected.setter
#    def connected(self, value):
#        if value != self._connected:
#            self._connected = value
#            self.emit('state_changed', state=value)

    def _on_connected_set(self, **kwargs):
        self.emit('state_changed', state=kwargs.get('value'))
