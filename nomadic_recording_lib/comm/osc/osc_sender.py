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
# osc_sender.py
# Copyright (c) 2011 Matthew Reid

import sys
import collections
import socket
#from twisted.internet import reactor
#from txosc import osc#, dispatch, async
import messages

if __name__ == '__main__':
    import sys, os
    p = os.path.split(os.getcwd())[0]
    sys.path.append(os.path.split(p)[0])

from ..BaseIO import BaseIO

ANY = '0.0.0.0'
MAX_PACKET_SIZE = 1000000

def split_packet(s):
    l = s[:MAX_PACKET_SIZE]
    if len(s) >= MAX_PACKET_SIZE:
        start = MAX_PACKET_SIZE
        while start <= len(s):
            end = start + MAX_PACKET_SIZE
            l.append(s[start:end])
            start = end
    return l    

class BaseOSCSender(BaseIO):
    def __init__(self, **kwargs):
        super(BaseOSCSender, self).__init__(**kwargs)
        self.root_address = kwargs.get('root_address')
        self.hostaddr = kwargs.get('hostaddr', 'localhost')
        self.hostport = int(kwargs.get('sendport', 18889))
        #self.hostport = 18889
        self.client = None
        self.queue = collections.deque()
        #self.connected = False
        self.debug = self.GLOBAL_CONFIG.get('arg_parse_dict', {}).get('debug_osc')
        self.preprocess_callbacks = []
        
    def add_preprocess(self, cb):
        if cb not in self.preprocess_callbacks:
            self.preprocess_callbacks.append(cb)
        return self.preprocess_callbacks.index(cb)
        
    def do_connect(self, **kwargs):
        self.do_disconnect()
        for key, val in kwargs.iteritems():
            if key in ['hostaddr', 'hostport']:
                setattr(self, key, val)
        self.build_socket()
        self.LOG.info('sender connect', self.hostaddr, self.hostport, self.__class__)
        self.connected = True
        #self.emit('state_changed', state=True)
        
    def do_disconnect(self, **kwargs):
        if self.client is not None:
            self.client.close()
            self.client = None
            self.connected = False
            #self.emit('state_changed', state=False)
            
    def _send(self, element, address):
        if self.connected:
            #self.preprocess(element)
            s = element.build_string()
            #for p in split_packet(s):
            #    self.queue_message(p, 0, address)
            try:
                self.client.sendto(s, 0, address)
            except socket.error, msg:
                self.LOG.warning('%s, msg len=%s, address=%s' % (msg, len(s), element.address))
            if self.debug:
                self.LOG.info('_osc_send: ' + str(element) + '   ' + str(address))
#                if isinstance(element, messages.Bundle):
#                    self.LOG.debug('_send_bundle: ', element.timetag, element.elements)
#                else:
#                    self.LOG.debug('_send: ', element.address, element.arguments, address)
                
#    def queue_message(self, *args):
#        self.queue.append(args)
#        
#    def _send_next_message(self):
    def preprocess(self, msg):
        for cb in self.preprocess_callbacks:
            cb(msg)
            
class MulticastOSCSender(BaseOSCSender):
    def __init__(self, **kwargs):
        super(MulticastOSCSender, self).__init__(**kwargs)
        self.mcastaddr = kwargs.get('mcastaddr', '224.168.2.9')
        self.mcastport = kwargs.get('mcastport', 18888)
        
    def do_connect(self, **kwargs):
        for key, val in kwargs.iteritems():
            if key in ['mcastaddr', 'mcastport']:
                setattr(self, key, val)
        super(MulticastOSCSender, self).do_connect(**kwargs)
        
    def build_socket(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 
                                    socket.IPPROTO_UDP)
        self.client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.client.bind((ANY, self.hostport))
        self.client.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
    
    def _send(self, element):
        super(MulticastOSCSender, self)._send(element, (self.mcastaddr, self.mcastport))
        
class UnicastOSCSender(BaseOSCSender):
    def build_socket(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 
                                    socket.IPPROTO_UDP)
        #self.client.bind(('', 0))
        
    def _send(self, element, address):
        if type(address) == str:
            addr = (address, self.hostport)
        else:
            addr = address
        super(UnicastOSCSender, self)._send(element, addr)



if __name__ == "__main__":
    app = MulticastOSCSender()
    app.do_connect()
    reactor.callLater(0, app.send_spam)
    reactor.run()
