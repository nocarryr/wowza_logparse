import os.path
import sys
import time
import socket
import SocketServer
import collections
import datetime
import json
import threading
import traceback
from Crypto.Cipher import AES


if __name__ == '__main__':
    dirname = os.path.dirname(__file__)
    if dirname == '':
        dirname = os.getcwd()
        sys.path.append(dirname)
    i = sys.path.index(dirname)
    sys.path[i] = os.path.split(sys.path[i])[0]
    sys.path[i] = os.path.split(sys.path[i])[0]

from Bases import BaseObject, BaseThread, Scheduler, setID
from comm.BaseIO import BaseIO

DEFAULT_PORT = 51515
BUFFER_SIZE = 4096
SEND_RETRIES = 20
SEND_RETRY_TIMEOUT = 10.
SEND_RETRY_TIMEDELTA = datetime.timedelta(seconds=SEND_RETRY_TIMEOUT)
POLL_INTERVAL = datetime.timedelta(minutes=1)

DATETIME_FMT_STR = '%Y-%m-%d %H:%M:%S.%f'
def datetime_to_str(dt):
    return dt.strftime(DATETIME_FMT_STR)
def str_to_datetime(s):
    return datetime.datetime.strptime(s, DATETIME_FMT_STR)

class QueueMessage(object):
    _message_keys = ['sender_id', 'sender_address', 'recipient_id', 
                     'recipient_address', 'timestamp', 
                     'message_id', 'message_type', 'data']
    def __init__(self, **kwargs):
        self.message_handler = kwargs.get('message_handler')
        raw_data = kwargs.get('raw_data')
        if raw_data is not None:
            d = self.deserialize(raw_data)
            d.update(kwargs)
        else:
            d = kwargs
        self.load_data(d)
        if self.timestamp is None:
            self.timestamp = self.message_handler.message_queue.now()
        if self.message_id is None:
            self.message_id = (self.recipient_id, datetime_to_str(self.timestamp))
        for key in ['recipient_address', 'sender_address', 'message_id']:
            val = getattr(self, key)
            if type(val) == list:
                setattr(self, key, tuple(val))
    def load_data(self, data):
        for key in self._message_keys:
            val = data.get(key)
            setattr(self, key, val)
    def serialize(self):
        keys = self._message_keys
        d = {}
        for key in keys:
            val = getattr(self, key)
            if isinstance(val, datetime.datetime):
                val = datetime_to_str(val)
            d[key] = val
        return json.dumps(d)
    def deserialize(self, data):
        d = json.loads(data)
        ts = d.get('timestamp')
        if ts is not None:
            dt = str_to_datetime(ts)
            d['timestamp'] = dt
        return d
    def __repr__(self):
        return '<%s object (%s)>' % (self.__class__.__name__, self)
    def __str__(self):
        return str(dict(zip(self._message_keys, [getattr(self, key, None) for key in self._message_keys])))
    
class AESEncryptedMessage(QueueMessage):
    cipher = None
    def __init__(self, **kwargs):
        if self.cipher is None:
            mh = kwargs.get('message_handler')
            key = mh.queue_parent.message_key
            if key is None:
                key = ''.join([chr(i) for i in range(32)])
            self.set_message_key(key)
        super(AESEncryptedMessage, self).__init__(**kwargs)
    @staticmethod
    def pad_zeros(s, size=16):
        if len(s) == size:
            return s
        padlen = size - len(s)
        s += '\0' * padlen
        return s
    @classmethod
    def set_message_key(cls, key):
        sizes = [32, 24, 16]
        if len(key) in sizes:
            padded = key
        if len(key) > max(sizes):
            size = max(sizes)
            padded = key[size:]
        else:
            for size in sizes:
                if len(key) > size:
                    continue
                padded = cls.pad_zeros(key, size)
                break
        cls.cipher = AES.new(padded)
    def serialize(self):
        msg = super(AESEncryptedMessage, self).serialize()
        size = len(msg)
        while size % 16 != 0:
            size += 1
        padded = self.pad_zeros(msg, size)
        c = self.cipher
        if c is None:
            return
        s = c.encrypt(padded)
        return s
        
    def deserialize(self, data):
        c = self.cipher
        if c is None:
            return
        msg = c.decrypt(data)
        msg = msg.strip('\0')
        return super(AESEncryptedMessage, self).deserialize(msg)
    
MESSAGE_CLASSES = {'Message':QueueMessage, 'AES':AESEncryptedMessage}

class MessageHandler(BaseObject):
    def __init__(self, **kwargs):
        super(MessageHandler, self).__init__(**kwargs)
        self.register_signal('new_message')
        self.queue_parent = kwargs.get('queue_parent')
        mcls = kwargs.get('message_class', getattr(self.queue_parent, 'message_class', 'Message'))
        self.message_class = MESSAGE_CLASSES.get(mcls)
        self.queue_time_method = kwargs.get('queue_time_method', 'datetime_utc')
        self.message_queue = Scheduler(time_method=self.queue_time_method, 
                                       callback=self.dispatch_message)
        self.message_queue.start()
    def unlink(self):
        self.message_queue.stop(blocking=True)
        q = self.message_queue
        super(MessageHandler, self).unlink()
    def create_message(self, **kwargs):
        cls = self.message_class
        kwargs['message_handler'] = self
        return cls(**kwargs)
    def incoming_data(self, **kwargs):
        data = kwargs.get('data')
        client = kwargs.get('client')
        mq = self.message_queue
        try:
            msg = self.create_message(raw_data=data)
        except:
            self.LOG.warning('message parse error: client = (%s), data = (%s)' % (client, data))
            return
        self.LOG.debug('incoming message: %s' % (msg))
        if msg.recipient_address is None:
            msg.recipient_address = client
        ts = msg.timestamp
        if ts is None:
            ts = mq.now()
        mq.add_item(ts, msg)
    
    def dispatch_message(self, msg, ts):
        self.emit('new_message', message=msg, timestamp=ts)
    
class Client(BaseObject):
    MAX_TX_FAILURES = 20
    _Properties = {'hostaddr':dict(ignore_type=True), 
                   'hostport':dict(ignore_type=True), 
                   'active':dict(default=True), 
                   'tx_failures':dict(default=0)}
    def __init__(self, **kwargs):
        super(Client, self).__init__(**kwargs)
        self.register_signal('new_message')
        self.id = kwargs.get('id')
        self.hostaddr = kwargs.get('hostaddr')
        self.hostport = kwargs.get('hostport', DEFAULT_PORT)
        self.is_local_client = kwargs.get('is_local_client', False)
        self.queue_parent = kwargs.get('queue_parent')
        self.pending_messages = {}
        self.pending_msg_timestamps = {}
        self.bind(tx_failures=self.on_tx_failures_set)
    def unlink(self):
        self.active = False
        super(Client, self).unlink()
    def send_message(self, **kwargs):
        if not self.active:
            return
        kwargs = kwargs.copy()
        self._update_message_kwargs(kwargs)
        msg = self.queue_parent._do_send_message(**kwargs)
        return msg
    def _on_message_built(self, msg):
        return
        if msg.recipient_id != self.id:
            return
        if msg.message_type == 'message_receipt':
            return
        d = self.pending_messages.get(msg.recipient_id)
        if d is None:
            d = {}
            self.pending_messages[msg.recipient_id] = d
        ts = msg.timestamp
        d[ts] = {'message':msg, 'attempts':1, 'last_attempt':ts}
        by_ts = self.pending_msg_timestamps
        if ts not in by_ts:
            by_ts[ts] = set()
        by_ts[ts].add(msg.recipient_id)
    def _update_message_kwargs(self, kwargs):
        d = {'recipient_id':self.id, 
             'recipient_address':(self.hostaddr, self.hostport)}
        kwargs.update(d)
    def _send_message_receipt(self, msg, **kwargs):
        return
        kwargs = kwargs.copy()
        msg_data = dict(message_type='message_receipt', 
                        data={'timestamp':msg.timestamp, 'client_id':self.id}, 
                        message_id=None, 
                        timestamp=None, 
                        client_id=msg.sender_id)
        #kwargs.update(msg_data)
        newmsg = self.queue_parent.send_message(**msg_data)
        self.LOG.info('sent msg receipt: msg=(%s), newmsg=(%s)' % (msg, newmsg))
    def update_hostdata(self, data):
        for attr in ['hostaddr', 'hostport']:
            if attr not in data:
                continue
            val = data[attr]
            if getattr(self, attr) == val:
                continue
            setattr(self, attr, val)
        if self.tx_failures > 0:
            self.tx_failures = 0
    def handle_message(self, **kwargs):
        msg = kwargs.get('message')
        if msg.message_type == 'message_receipt':
            c_id = msg.data['client_id']
            ts = msg.data['timestamp']
            self.LOG.info('got msg receipt. msg=%s' % (msg))
            by_ts = self.pending_msg_timestamps
            pending = self.pending_messages
            s = by_ts.get(ts)
            if s is not None:
                s.discard(c_id)
                if not len(s):
                    del by_ts[ts]
            d = pending.get(c_id)
            if d is None:
                return
            if ts in msgdata:
                del msgdata[ts]
            if not len(msgdata):
                del pending[c_id]
            return
        elif msg.message_type == 'hostdata_update':
            if not isinstance(msg.data, dict):
                return
            self.update_hostdata(msg.data)
            self._send_message_receipt(msg, **kwargs)
            return
        self._send_message_receipt(msg, **kwargs)
        self.update_hostdata(dict(zip(['hostaddr', 'hostport'], msg.sender_address)))
        kwargs['obj'] = self
        self.emit('new_message', **kwargs)
    def send_pending_messages(self, now=None):
        if not self.active:
            return
        by_ts = self.pending_msg_timestamps
        pending = self.pending_messages
        qp = self.queue_parent
        if not len(by_ts):
            return
        if now is None:
            now = qp.message_handler.message_queue.now()
        dead = set()
        for ts in sorted(by_ts.keys()):
            for c_id in by_ts[ts]:
                msgdata = pending[c_id][ts]
                if msgdata['last_attempt'] + SEND_RETRY_TIMEDELTA < now:
                    continue
                if msgdata['attempts'] >= SEND_RETRIES:
                    dead.add(c_id)
                    continue
                msgdata['last_attempt'] = now
                msgdata['attempts'] += 1
                qp._do_send_message(existing_message=msgdata['message'])
        for c_id in dead:
            msgdata = pending[c_id]
            for ts in msgdata.keys():
                if ts not in by_ts:
                    continue
                by_ts[ts].discard(c_id)
                if not len(by_ts[ts]):
                    del by_ts[ts]
            del pending[c_id]
        
    def on_tx_failure(self, msg):
        if not self.active:
            return
        txf = self.tx_failures
        self.tx_failures = txf + 1
    def on_tx_success(self, msg):
        if self.tx_failures == 0:
            return
        self.tx_failures = 0
    def on_tx_failures_set(self, **kwargs):
        value = kwargs.get('value')
        self.active = value < self.MAX_TX_FAILURES
        if not self.active:
            self.pending_messages.clear()
            self.pending_msg_timestamps.clear()
    def __repr__(self):
        return '<%s>' % (self)
    def __str__(self):
        return 'Client: %s, hostdata=(%s, %s)' % (self.id, self.hostaddr, self.hostport)
        
class RetryThread(BaseThread):
    def __init__(self, **kwargs):
        super(RetryThread, self).__init__(**kwargs)
        self.queue_parent = kwargs.get('queue_parent')
        self._threaded_call_ready.wait_timeout = SEND_RETRY_TIMEOUT
    def _thread_loop_iteration(self):
        if not self._running:
            return
        qp = self.queue_parent
        now = qp.message_handler.message_queue.now()
        for c in qp.clients.itervalues():
            c.send_pending_messages(now)
    
class QueueBase(BaseIO):
    _ChildGroups = {'clients':dict(child_class=Client, ignore_index=True)}
    def __init__(self, **kwargs):
        self.shutting_down = False
        super(QueueBase, self).__init__(**kwargs)
        self.register_signal('new_message')
        self.id = setID(kwargs.get('id'))
        self.message_key = kwargs.get('message_key')
        hostaddr = kwargs.get('hostaddr', '127.0.0.1')
        hostport = int(kwargs.get('hostport', DEFAULT_PORT))
        self.message_class = kwargs.get('message_class', 'Message')
        self.message_handler = MessageHandler(queue_parent=self)
        self.message_handler.bind(new_message=self.on_handler_new_message)
        self.local_client = self.add_client(hostaddr=hostaddr, 
                                            hostport=hostport, 
                                            id=self.id, 
                                            is_local_client=True)
        self.local_client.bind(property_changed=self.on_local_client_property_changed)
        self.retry_thread = RetryThread(queue_parent=self)
        self.retry_thread.start()
    @property
    def hostaddr(self):
        return self.local_client.hostaddr
    @hostaddr.setter
    def hostaddr(self, value):
        self.local_client.hostaddr = value
    @property
    def hostport(self):
        return self.local_client.hostport
    @hostport.setter
    def hostport(self, value):
        self.local_client.hostport = value
    def unlink(self):
        self.retry_thread.stop(blocking=True)
        self.message_handler.unlink()
        #self.clients.clear()
        super(QueueBase, self).unlink()
    def add_client(self, **kwargs):
        kwargs['queue_parent'] = self
        c = self.clients.add_child(**kwargs)
        if not c.is_local_client:
            self.send_hostdata_to_clients(clients=c)
        return c
    def del_client(self, **kwargs):
        c_id = kwargs.get('id')
        client = kwargs.get('client')
        if client is None:
            client = self.clients.get(c_id)
        if client is None:
            return
        self.clients.del_child(client)
    def on_handler_new_message(self, **kwargs):
        msg = kwargs.get('message')
        if msg == 'POLL':
            self.on_poll_interval()
            return
        c_id = msg.sender_id
        client = self.clients.get(c_id)
        #self.LOG.info('handling message: %s, client=%s' % (msg, client))
        if client is not None:
            client.handle_message(**kwargs)
        else:
            self.emit('new_message', **kwargs)
    def _update_message_kwargs(self, kwargs):
        d = {'sender_id':self.id, 'sender_address':(self.hostaddr, self.hostport)}
        kwargs.update(d)
    def send_message(self, **kwargs):
        if self.shutting_down:
            return
        kwargs = kwargs.copy()
        client = kwargs.get('client')
        c_id = kwargs.get('client_id')
        if not isinstance(client, Client):
            if client is not None:
                client = self.clients.get(client)
            if client is None:
                client = self.clients.get(c_id)
        if isinstance(client, Client):
            if not client.active:
                return
            client._update_message_kwargs(kwargs)
        msg = self._do_send_message(**kwargs)
        return msg
    def _do_send_message(self, **kwargs):
        msg = kwargs.get('existing_message')
        if self.shutting_down:
            return msg
        existing = True
        if msg is None:
            msg = self.create_message(**kwargs)
            existing = False
        client = self.clients.get(msg.recipient_id)
        if not existing and client is not None and client.active:
            client._on_message_built(msg)
        self.LOG.debug('sending message: %s' % (msg))
        s = msg.serialize()
        h = kwargs.get('handler')
        sock = None
        try:
            if h is not None:
                sock = h.request
            else:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect(msg.recipient_address)
            sock.sendall(s)
            if h is None:
                sock.close()
            if client is not None:
                client.on_tx_success(msg)
        except:
            self.LOG.warning('Error sending msg (%s)' % (msg))
            if client is not None:
                client.on_tx_failure(msg)
            self.LOG.warning(traceback.format_exc())
        return msg
        
    def create_message(self, **kwargs):
        self._update_message_kwargs(kwargs)
        msg = self.message_handler.create_message(**kwargs)
        return msg
        
    def on_poll_interval(self):
        self.send_hostdata_to_clients()
        mq = self.message_handler.message_queue
        nextpoll = mq.now() + POLL_INTERVAL
        mq.add_item(nextpoll, 'POLL')
        
    def send_hostdata_to_clients(self, **kwargs):
        keys = kwargs.get('keys')
        clients = kwargs.get('clients')
        if not keys:
            keys = ['hostaddr', 'hostport']
        if clients is not None and type(clients) not in [list, tuple, set]:
            clients = [clients]
        elif clients is None:
            clients = self.clients
        d = dict(zip(keys, [getattr(self, key) for key in keys]))
        for c_id in self.clients.keys()[:]:
            c = self.clients.get(c_id)
            if c is None:
                continue
            if c.is_local_client:
                continue
            c.send_message(message_type='hostdata_update', data=d)
            
    def on_local_client_property_changed(self, **kwargs):
        prop = kwargs.get('Property')
        value = kwargs.get('value')
        if prop.name in ['hostaddr', 'hostport']:
            self.send_hostdata_to_clients(keys=[prop.name])
        
class QueueServer(QueueBase):
    def __init__(self, **kwargs):
        super(QueueServer, self).__init__(**kwargs)
        self.serve_thread = None
        
    def do_connect(self):
        self.do_disconnect(blocking=True)
        t = self.serve_thread = self.build_server()
        t.bind(hostport=self.on_server_hostport_changed)
        t.start()
        self.connected = True
        self.on_poll_interval()
    def do_disconnect(self, **kwargs):
        t = self.serve_thread
        if t is not None:
            t.unbind(self)
            t.stop(blocking=True)
            self.serve_thread = None
        self.connected = False
    def shutdown(self):
        self.shutting_down = True
        self.do_disconnect(blocking=True)
        self.unlink()
    def build_server(self):
        t = ServeThread(hostaddr='', 
                        hostport=self.hostport, 
                        message_handler=self.message_handler)
        return t
    def on_server_hostport_changed(self, **kwargs):
        value = kwargs.get('value')
        if value != self.hostport:
            self.hostport = value
    
    
class QueueClient(QueueBase):
    def __init__(self, **kwargs):
        super(QueueClient, self).__init__(**kwargs)
        
        
class _Server(SocketServer.TCPServer):
    pass
    #def __init__(self, *args):
    #    SocketServer.TCPServer.__init__(self, *args)
class _RequestHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        data = self.request.recv(BUFFER_SIZE)
        client = self.client_address
        mh = self.server.message_handler
        mh.incoming_data(data=data, client=client, handler=self)
        
class ServeThread(BaseThread):
    _Properties = {'hostaddr':dict(ignore_type=True), 
                   'hostport':dict(ignore_type=True)}
    def __init__(self, **kwargs):
        super(ServeThread, self).__init__(**kwargs)
        self.hostaddr = kwargs.get('hostaddr')
        self.hostport = kwargs.get('hostport')
        self.message_handler = kwargs.get('message_handler')
        self._server = None
    def build_server(self):
        addr = self.hostaddr
        port = int(self.hostport)
        count = 0
        maxtries = 100
        while count < maxtries:
            try:
                s = _Server((addr, port), _RequestHandler)
                break
            except socket.error:
                port += 1
            count += 1
        self.hostport = port
        s.message_handler = self.message_handler
        return s
    def run(self):
        self._running = True
        s = self._server = self.build_server()
        self.message_handler.LOG.info('%r STARTING' % (self))
        s.serve_forever()
        self._running = False
        self._stopped = True
        self.message_handler.LOG.info('%r STOPPED' % (self))
    def stop(self, **kwargs):
        s = self._server
        if s is not None:
            s.shutdown()
        self._stopped.wait()

if __name__ == '__main__':
    import argparse
    class TestObj(object):
        def on_message(self, **kwargs):
            print 'message received: ', kwargs
    p = argparse.ArgumentParser()
    p.add_argument('--host', dest='host')
    p.add_argument('--client', dest='client')
    args, remaining = p.parse_known_args()
    o = vars(args)
    testobj = TestObj()
    serv = QueueServer(id=o['host'], hostaddr=o['host'])
    serv.bind(new_message=testobj.on_message)
    serv.local_client.bind(new_message=testobj.on_message)
    serv.do_connect()
    print 'server connected'
    c = serv.add_client(id=o['client'], hostaddr=o['client'])
    c.bind(new_message=testobj.on_message)
    time.sleep(1.)
    print 'sending message'
    msg = c.send_message(data='hi')
    print 'message sent', msg
    while True:
        try:
            time.sleep(.5)
        except KeyboardInterrupt:
            print 'disconnecting'
            serv.shutdown()
            break
    print 'disconnected'
    
