import telnetlib
import threading
from collections import deque

from cli_messages import MessageIO

class TelnetIO(object):
    def __init__(self, **kwargs):
        self.host = kwargs.get('host')
        self.thread = kwargs.get('thread', False)
        self.connected = threading.Event()
        self.io_ready = threading.Event()
        self.tx_ready = threading.Event()
        self.rx_ready = threading.Event()
        self.rx_complete = threading.Event()
        self.message_queue = deque()
        self.read_queue = deque()
        self.last_rx = None
        self.connection = None
        self.message_io = MessageIO(tx_fn=self.send, rx_fn=self.read_until)
    def connect(self):
        if self.connected.isSet():
            self.disconnect()
        self.connection = telnetlib.Telnet(self.host)
        self.connected.set()
    def disconnect(self):
        if not self.connected.isSet():
            return
        self.connection.close()
        self.connection = None
        self.connected.clear()
    def send(self, msg):
        self.message_queue.append(msg)
        if not self.connected.isSet():
            self.connect()
        if False:#self.thread is not None:
            self.tx_ready.set()
            self.io_ready.set()
        else:
            self._send_next_message()
    def _send_next_message(self):
        try:
            msg = self.message_queue.popleft()
        except IndexError:
            return
        self.connection.write(msg)
        self.tx_ready.clear()
    def read_until(self, s):
        self.read_queue.append(s)
        if False:#self.thread is not None:
            self.rx_ready.set()
            self.io_ready.set()
        else:
            self._read_until()
        self.rx_complete.wait()
        self.rx_complete.clear()
        return self.last_rx
    def _read_until(self):
        self.last_rx = None
        try:
            s = self.read_queue.popleft()
        except IndexError:
            return
        self.last_rx = self.connection.read_until(s)
        self.rx_ready.clear()
        self.rx_complete.set()
        

class TelnetThread(threading.Thread):
    def __init__(self, **kwargs):
        super(TelnetThread, self).__init__()
        self.running = threading.Event()
        self.stopped = threading.Event()
        self.id = kwargs.get('id')
        kwargs['thread'] = self
        self.telnet_io = TelnetIO(**kwargs)
        self.commands = kwargs.get('commands')
    def run(self):
        t_io = self.telnet_io
        t_io.connect()
        r = self.running
        r.set()
        commands = self.commands
        commands['auth']()
        if commands['auth'].context.active:
            commands['root']()
            if not commands['root'].context.complete:
                commands['root'].context.wait()
#        while r.isSet():
#            t_io.io_ready.wait()
#            if t_io.tx_ready.isSet():
#                t_io._send_next_message()
#            elif t_io.rx_ready.isSet():
#                t_io._read_until()
#            t_io.io_ready.clear()
        r.clear()
        t_io.disconnect()
        t_io.connected.wait()
        self.stopped.set()
    def stop(self):
        self.running.clear()
        self.telnet_io.io_ready.set()
        self.stopped.wait()
