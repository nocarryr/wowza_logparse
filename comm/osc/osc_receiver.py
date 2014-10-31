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
# osc_receiver.py
# Copyright (c) 2011 Matthew Reid

import sys
import time
import SocketServer
import threading
import select
import socket

from Bases import osc_base, BaseThread
import messages

#from twisted.internet import reactor
#import txosc
#from txosc import osc, dispatch#, sync, async

if __name__ == '__main__':
    import sys, os
    p = os.path.split(os.getcwd())[0]
    sys.path.append(os.path.split(p)[0])
from ..BaseIO import BaseIO

ANY = '0.0.0.0'
MAX_PACKET_SIZE = 1000000

class BaseOSCReceiver(BaseIO):
    def __init__(self, **kwargs):
        super(BaseOSCReceiver, self).__init__(**kwargs)
        self.register_signal('raw_data')
        self.root_address = kwargs.get('root_address')
        self.hostaddr = kwargs.get('hostaddr', 'localhost')
        self.hostport = int(kwargs.get('recvport', 18888))
        self.osc_io = kwargs.get('osc_io')
        self.osc_tree = kwargs.get('osc_tree')#, dispatch.Receiver())
        #self.osc_tree.setFallback(self.fallback)
        self.server = None
        self.server_thread = None
        self.debug = self.GLOBAL_CONFIG.get('arg_parse_dict', {}).get('debug_osc')
        self.connection_count = 0
        self.preprocess_callbacks = []
        
    def add_preprocess(self, cb):
        if cb not in self.preprocess_callbacks:
            self.preprocess_callbacks.append(cb)
        return self.preprocess_callbacks.index(cb)
        
    def fallback(self, message, address):
        if self.debug:
            if self.root_address not in message.address:
                self.LOG.info('fallback: ', message, address)
        
    def do_connect(self, **kwargs):
        self.connection_count += 1
        #print 'count = ', self.connection_count
        self.do_disconnect()
        for key, val in kwargs.iteritems():
            if key in ['hostaddr', 'hostport']:
                setattr(self, key, val)
        server_kwargs = self.set_server_kwargs()
        server_kwargs.update({'debug':self.debug, 
                              'raw_data_cb':self.on_server_raw_data, 
                              'preprocess_cb':self.preprocess_cb, 
                              'osc_io':self.osc_io})
        self.server = self.server_class(**server_kwargs)
        #self.server_thread = ServerThread(self.server)
        self.server_thread = ServeThread(self.server)#threading.Thread(target=self.server.serve_forever)
        #self.server_thread.daemon = True
        self.server_thread.start()
        self.connected = True
        self.LOG.info('OSC recvr connected',  self.hostaddr, self.hostport, self.server_class)
        #self.emit('state_changed', state=True)
        
        
    def do_disconnect(self, **kwargs):
        if self.server is not None and self.connected:
            self.server_thread.stop(**kwargs)
            self.server = None
            self.server_thread = None
            self.connected = False
    
    def on_server_raw_data(self, data):
        self.emit('raw_data', data=data)
        
    def preprocess_cb(self, data):
        new_data = data
        for cb in self.preprocess_callbacks:
            new_data = cb(data)
        return new_data
        

class ServeThread(BaseThread):
    def __init__(self, server, **kwargs):
        kwargs['thread_id'] = 'OSCReceiver_ServeThread'
        super(ServeThread, self).__init__(**kwargs)
        self.server = server
    def _thread_loop_iteration(self):
        if not self._running:
            return
        self.server.serve_forever()
    def stop(self, **kwargs):
        self.server.shutdown()
        super(ServeThread, self).stop(**kwargs)
        self.LOG.info('osc receiver closed')
        
class MulticastOSCReceiver(BaseOSCReceiver):
    def __init__(self, **kwargs):
        super(MulticastOSCReceiver, self).__init__(**kwargs)
        self.mcastaddr = kwargs.get('mcastaddr', '224.168.2.9')
        self.mcastport = int(kwargs.get('mcastport', 18888))
        self.server_class = MulticastUDPServer
    def set_server_kwargs(self):
        return dict(hostaddress=(self.hostaddr, self.hostport), 
                    handler_cls=RequestHandler, osc_tree=self.osc_tree, 
                    mcastaddr=self.mcastaddr, mcastport=self.mcastport)
    def do_connect(self, **kwargs):
        for key, val in kwargs.iteritems():
            if key in ['mcastaddr', 'mcastport']:
                setattr(self, key, val)
        super(MulticastOSCReceiver, self).do_connect(**kwargs)
        
class UnicastOSCReceiver(BaseOSCReceiver):
    def __init__(self, **kwargs):
        super(UnicastOSCReceiver, self).__init__(**kwargs)
        self.server_class = UnicastUDPServer
    def set_server_kwargs(self):
        return dict(hostaddress=(self.hostaddr, self.hostport), 
                    handler_cls=RequestHandler, osc_tree=self.osc_tree)
        
class RequestHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        timestamp = time.time()
        data = self.request[0]
        client = self.server.osc_io.Manager.get_client(hostaddr=self.client_address)
        #print 'CLIENT: ', client
        #element = messages.parse_message(data, client=client)
        
        #if element is False:
        #    return
       # print 'element client: ', element.client
        #element = osc_base._elementFromBinary(data)
        #print threading.currentThread()
        #if self.server.debug:
        #    self.server.osc_io.LOG.debug('_osc_recv: ' + str(element))
#            if isinstance(element, messages.Bundle):
#                self.LOG.debug('_recv_bundle:', [msg.__str__() for msg in element.messages])
#            else:
#                self.LOG.debug('_recv: ', element.address, element.arguments, element.client)
        self.server.osc_tree.dispatch_message(data=data, client=client, timestamp=timestamp)
        
class MulticastUDPServer(SocketServer.ThreadingMixIn, SocketServer.UDPServer):
    def __init__(self, **kwargs):
        self.raw_data_cb = kwargs.get('raw_data_cb')
        self.preprocess_cb = kwargs.get('preprocess_cb')
        self.max_packet_size = MAX_PACKET_SIZE
        self.osc_tree = kwargs.get('osc_tree')
        self.osc_io = kwargs.get('osc_io')
        self.mcastaddr = kwargs.get('mcastaddr')
        self.mcastport = kwargs.get('mcastport')
        args = [kwargs.get(key) for key in ['hostaddress', 'handler_cls']]
        self.debug = kwargs.get('debug')
        SocketServer.UDPServer.__init__(self, *args)
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((ANY, self.mcastport))
        self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
        s = self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, 
                                   socket.inet_aton(self.mcastaddr) + socket.inet_aton(ANY))

class UnicastUDPServer(SocketServer.UDPServer):
    def __init__(self, **kwargs):
        self.raw_data_cb = kwargs.get('raw_data_cb')
        self.preprocess_cb = kwargs.get('preprocess_cb')
        self.osc_tree = kwargs.get('osc_tree')
        self.osc_io = kwargs.get('osc_io')
        self.max_packet_size = MAX_PACKET_SIZE
        #self.allow_reuse_address = True
        self.debug = kwargs.get('debug')
        args = [kwargs.get(key) for key in ['hostaddress', 'handler_cls']]
        SocketServer.UDPServer.__init__(self, *args)


#def print_stuff(message, address):
#    print 'received: ', message.address, message.getValues()
#
#if __name__ == "__main__":
#    app = MulticastOSCReceiver()
#    app.do_connect()
#    r = app.osc_tree
#    n1 = app.add_node(name='test', parent=r)
#    n2 = app.add_node(name='foo', parent=n1)
#    app.add_handler(address='/test/foo/bar', callback=print_stuff)
#    

