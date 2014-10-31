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
# communication.py (package: comm.dmx.artnet)
# Copyright (c) 2011 Matthew Reid

import socket
import errno
import asyncore
import SocketServer
import threading
import time
import select
import collections

from Bases import BaseThread
from ...BaseIO import BaseIO

ANY = '0.0.0.0'
MAX_SIZE = 8192

class ArtnetIO(BaseIO):
    def __init__(self, **kwargs):
        super(ArtnetIO, self).__init__(**kwargs)
        self.hostaddr = kwargs.get('hostaddr')
        self.hostport = kwargs.get('hostport')
        self.manager = kwargs.get('manager')
        self.sender = None
        self.receiver = None
        
    def do_connect(self, **kwargs):
        self.do_disconnect()
        self.sender = ArtnetSender(artnet_io=self)
        self.sender.do_connect()
        self.receiver = ArtnetReceiver(artnet_io=self)
        self.receiver.do_connect()
        self.connected = True
        
    def do_disconnect(self, blocking=False):
        for key in ['receiver', 'sender']:
            obj = getattr(self, key, None)
            if obj is not None:
                obj.do_disconnect(blocking=blocking)
                setattr(self, key, None)
        self.connected = False
        
    def on_data_received(self, **kwargs):
        #data = kwargs.get('data')
        #print 'artnet received: ', [ord(c) for c in data]
        self.manager.parse_message(**kwargs)
        
    def send(self, string, client=None):
        if self.connected:
            self.sender.add_msg(string, client)

class ArtnetSender(BaseIO):
    def __init__(self, **kwargs):
        super(ArtnetSender, self).__init__(**kwargs)
        self.artnet_io = kwargs.get('artnet_io')
        self.send_thread = None
    def add_msg(self, msg, client):
        if self.connected:
            self.send_thread.add_msg(msg, client)
    def do_connect(self, **kwargs):
        self.do_disconnect()
        self.send_thread = SendThread(sender=self)
        self.send_thread.start()
        self.connected = True
    def do_disconnect(self, blocking=False):
        if self.send_thread is not None:
            if self.send_thread.isAlive():
                self.send_thread.stop(blocking=blocking)
            self.send_thread = None
        self.connected = False
    def build_socket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        return s
        
class SendThread(BaseThread):
    _Events = {'sending':{}}
    def __init__(self, **kwargs):
        kwargs['thread_id'] = 'ArtnetSendThread'
        super(SendThread, self).__init__(**kwargs)
        self.sender = kwargs.get('sender')
    def add_msg(self, msg, client):
        self.insert_threaded_call(self._do_send_msg, msg, client)
    def _do_send_msg(self, msg, client):
        self.sending.set()
        if client is None:
            client = (self.sender.artnet_io.hostaddr, self.sender.artnet_io.hostport)
        s = self.sender.build_socket()
        s.sendto(msg, client)
        self.sending.clear()
        
class oldSendThread(threading.Thread):
    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.sender = kwargs.get('sender')
        self.running = threading.Event()
        self.sending = threading.Event()
        self.queue = collections.deque()
    def add_msg(self, msg, client):
        self.queue.append((msg, client))
        self.sending.set()
    def run(self):
        self.running.set()
        while self.running.isSet():
            self.sending.wait()
            if self.running.isSet():
                self.send_next_msg()
    def stop(self):
        self.running.clear()
        self.sending.set()
    def send_next_msg(self):
        if not len(self.queue):
            return
        msg, client = self.queue.popleft()
        if client is None:
            client = (self.sender.artnet_io.hostaddr, self.sender.artnet_io.hostport)
        s = self.sender.build_socket()
        s.sendto(msg, client)
        #print 'sending: ', [ord(c) for c in msg], client
        if not len(self.queue):
            self.sending.clear()
            
            
class ArtnetReceiver(BaseIO):
    def __init__(self, **kwargs):
        super(ArtnetReceiver, self).__init__(**kwargs)
        self.artnet_io = kwargs.get('artnet_io')
        self.hostaddr = kwargs.get('hostaddr', self.artnet_io.hostaddr)
        self.hostport = kwargs.get('hostport', self.artnet_io.hostport)
        self.server = None
    def do_connect(self, **kwargs):
        self.do_disconnect()
        self.server = UnicastUDPServer(receiver=self)
        self.serve_thread = ServeThread(server=self.server)
        self.serve_thread.start()
        self.connected = True
    def do_disconnect(self, blocking=False):
        if self.server is not None:
            self.serve_thread.stop(blocking=blocking)
            self.server = None
            self.serve_thread = None
            self.connected = False

class UnicastUDPServer(SocketServer.UDPServer):
    def __init__(self, **kwargs):
        self.receiver = kwargs.get('receiver')
        self.artnet_io = self.receiver.artnet_io
        #self.hostaddr = kwargs.get('hostaddr', self.receiver.hostaddr)
        self.hostaddr = '0.0.0.0'
        self.hostport = kwargs.get('hostport', self.receiver.hostport)
        self.allow_reuse_address = True
        args = ((self.hostaddr, self.hostport), RequestHandler)
        SocketServer.UDPServer.__init__(self, *args)

class RequestHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        self.server.artnet_io.on_data_received(data=data, client=self.client_address)
        
class ServeThread(BaseThread):
    def __init__(self, **kwargs):
        kwargs['thread_id'] = 'ArtnetServeThread'
        super(ServeThread, self).__init__(**kwargs)
        self.server = kwargs.get('server')
    def _thread_loop_iteration(self):
        if not self._running:
            return
        self.server.serve_forever()
    def stop(self, **kwargs):
        self.server.shutdown()
        super(ServeThread, self).stop(**kwargs)
