import time
import threading

class MessageBase(object):
    def __init__(self, **kwargs):
        self.timestamp = time.time()
        self.content = kwargs.get('content')
        self.message_io = kwargs.get('message_io')
        
class RXMessage(MessageBase):
    pass
    
class TXMessage(MessageBase):
    def __init__(self, **kwargs):
        super(TXMessage, self).__init__(**kwargs)
        self.reading = threading.Event()
        self.read_until = kwargs.get('read_until')
        self.response = None
    def __call__(self):
        return self.do_transmit()
    def do_transmit(self):
        self.message_io.tx_fn(self)
        if self.read_until:
            self.wait_for_response()
        return self.response
    def wait_for_response(self):
        self.reading.set()
        resp = self.message_io.rx_fn(self.read_until)
        if resp is not None:
            
            self.response = RXMessage(content=resp, message_io=self.message_io)
        self.reading.clear()
    def __str__(self):
        return self.content
        
class MessageIO(object):
    def __init__(self, **kwargs):
        self.message_cls = {'tx':TXMessage, 'rx':RXMessage}
        self._tx_fn = kwargs.get('tx_fn')
        self._rx_fn = kwargs.get('rx_fn')
    def tx_fn(self, msg):
        if self._tx_fn is not None:
            self._tx_fn(msg.content)
    def rx_fn(self, read_until=None):
        if self._rx_fn is not None:
            rx = self._rx_fn(read_until)
            return self.build_rx(content=rx)
    def build_tx(self, **kwargs):
        kwargs.setdefault('message_io', self)
        return self.message_cls['tx'](**kwargs)
    def build_rx(self, **kwargs):
        kwargs.setdefault('message_io', self)
        return self.message_cls['rx'](**kwargs)
