import threading
import pickle
import socket
import collections
import SocketServer

from Bases import BaseObject
from base import gstBase
from element import Element


class RTPLinker(gstBase):
    def __init__(self, **kwargs):
        '''
        :Parameters:
        src_elements / sink_elements : dict containing {name_of_element:(rtpIndex, element_object)}
        '''
        super(RTPLinker, self).__init__(**kwargs)
        self.remote_host = kwargs.get('remote_host', 'localhost')
        self.remote_start_port = kwargs.get('remote_start_port', 10000)
        self.control_recv_port = kwargs.get('control_recv_port', 11000)
        self.control_send_port = kwargs.get('control_send_port', 11001)
        self.pipeline = kwargs.get('pipeline')
        self._bin = self._gst_module.element_factory_make('gstrtpbin')
        for key, val in kwargs.get('rtpbin_properties', {}).iteritems():
            self._bin.set_property(key, val)
        self.udp_elements = {'src':{}, 'sink':{}, 'control':{}}
        self.udp_elems_by_port = {}
        self.pipeline.elem_container.add(self._bin)
        src_elements = kwargs.get('src_elements', {})
        sink_elements = kwargs.get('sink_elements', {})
        self.elements_to_link = {'src':src_elements, 'sink':sink_elements}
        self.payloaders = {'src':{}, 'sink':{}}
        self.find_payloaders()
        self.controller = Controller(parent=self)
        self.controller.do_connect()
        #print 'to_link: %s \n\n payloaders: %s \n\n udp_elems: %s' % (self.elements_to_link, self.payloaders, self.udp_elements)
        #self.udp_elements['control']['recv'] = 
        self.pipeline.bind(pipeline_state=self.on_pipeline_state)
        self.controller.send('get sink_caps', (self.remote_host, self.control_recv_port))
        
    def on_pipeline_state(self, **kwargs):
        value = kwargs.get('value')
        if value == 'playing':
            pass
        elif value == 'null':
            self.controller.do_disconnect()
        
    def find_payloaders(self):
        for ptype, elements in self.elements_to_link.iteritems():
            if ptype == 'src':
                padname = 'sink'
                plstr = 'depay'
            elif ptype == 'sink':
                padname = 'src'
                plstr = 'pay'
            #padname = ptype
            for key, val in elements.iteritems():
                index, elem = val
                caps = elem._element.get_pad(padname).get_caps()[0].get_name()
                caps = caps.split('/')[1]
                if 'raw' in caps:
                    caps = 'vraw'
                elif caps == 'mpeg':
                    v = elem._element.get_pad(padname).get_caps()[0]['mpegversion']
                    if v == 4:
                        caps = 'mp4v'
                    elif v == 2:
                        caps = 'mp2t'
                    else:
                        caps = 'mpv'                    
                if 'x-' in caps:
                    caps = caps.split('-')[1]
                elemname = caps.join(['rtp', plstr])
                payloader = self.build_payloader(payload_type=ptype, 
                                                 key=key, 
                                                 payloader_name=elemname, 
                                                 index=index, 
                                                 element=elem, 
                                                 padname=padname)
                        
    def build_payloader(self, **kwargs):
        payload_type = kwargs.get('payload_type')
        key = kwargs.get('key')
        index = kwargs.get('index')
        payloader_name = kwargs.get('payloader_name')
        element = kwargs.get('element')
        padname = kwargs.get('padname')
        try:
            payloader = Payloader(name=key, 
                                  gst_name=payloader_name, 
                                  rtp_index=index, 
                                  payload_type=payload_type, 
                                  linked_element=element, 
                                  parent=self)
        except self._gst_module.PluginNotFoundError:
            print 'could not build payloader: index=%s, element=%s, ptype=%s, key=%s, plname=%s, elem_caps=%s, padname=%s' % (index, element._element.get_name(), payload_type, key, payloader_name, element._element.get_pad(padname).get_caps()[0].get_name(), padname)
            return False
        self.payloaders[payload_type][key] = payloader
        #self.pipeline.add(payloader._element)
        return payloader
        
    def build_udp_elements(self, **kwargs):
        payloader = kwargs.get('payloader')
        d = {}
        for prot in ['rtp', 'rtcp']:
            elem = UDPElement(parent=self, 
                              payloader=payloader, 
                              rtp_protocol=prot)
            self.udp_elems_by_port[elem.port] = elem
            d[prot] = elem
        self.udp_elements[payloader.payload_type][payloader.rtp_index] = d
        if payloader.payload_type == 'src':
            s = 'sink'
        else:
            s = 'src'
        for prot in ['rtcp']:
            elem = UDPElement(parent=self, 
                              payloader=payloader, 
                              payload_type=s, 
                              rtp_protocol=prot, 
                              autolink=False)
            self.udp_elems_by_port[elem.port] = elem
            if payloader.rtp_index not in self.udp_elements[s]:
                self.udp_elements[s][payloader.rtp_index] = {}
            self.udp_elements[s][payloader.rtp_index][prot] = elem
        
    def get_next_remote_port(self):
        if not len(self.udp_elems_by_port):
            return self.remote_start_port
        return max(self.udp_elems_by_port.keys()) + 1
        
    @property
    def sink_caps(self):
        d = {}
        for index, elements in self.udp_elements['sink'].iteritems():
            rtp = elements.get('rtp')
            if rtp is None:
                continue
            d[index] = str(rtp._element.get_pad('sink').get_property('caps'))
        return pickle.dumps(d)
    @sink_caps.setter
    def sink_caps(self, value):
        d = pickle.loads(value)
        for index, capstr in d.iteritems():
            elems = self.udp_elements['src'].get(index)
            rtp = elems.get('rtp')
            if rtp is None:
                continue
            caps = self._gst_module.Caps(capstr)
            rtp._element.set_property('caps', caps)
        
class Payloader(Element):
    def __init__(self, **kwargs):
        super(Payloader, self).__init__(**kwargs)
        self.parent = kwargs.get('parent')
        self.payload_type = kwargs.get('payload_type')
        self.rtp_index = kwargs.get('rtp_index')
        self.linked_element = kwargs.get('linked_element')
        self.parent.pipeline.elem_container.add(self._element)
        if self.payload_type == 'src':
            self._element.link(self.linked_element._element)
            self.rtpbin_sigid = self.rtpbin.connect('pad-added', self.on_rtpbin_pad_added)
            padstr = None
        elif self.payload_type == 'sink':
            self.linked_element._element.link(self._element)
            padstr = 'send_rtp_sink_%s' % (self.rtp_index)
            self._element.link_pads('src', self.rtpbin, padstr)
        print 'payloader built: index=%s, gst_name=%s, linked_element=%s' % (self.rtp_index, kwargs['gst_name'], self.linked_element._element.get_name())
        self.parent.build_udp_elements(payloader=self)
    @property
    def rtpbin(self):
        return self.parent._bin
    def on_rtpbin_pad_added(self, element, pad):
        print 'rtpbin pad added: pad=%s, parent=%s' % (pad.get_name(), pad.get_parent_element())
        print 'all rtpbinpads: ', [(p.get_name(), p.get_parent_element()) for p in self.rtpbin.pads()]
        print 'rtpbin clock: ', self.rtpbin.get_clock()
        pads = [p for p in self.rtpbin.src_pads() if 'rtp' in p.get_caps()[0].get_name()]
        if len(pads):
            print 'LINKING'
            self.rtpbin.link(self._element)
            self.rtpbin.disconnect(self.rtpbin_sigid)
        
class UDPElement(Element):
    def __init__(self, **kwargs):
        self.parent = kwargs.get('parent')
        self.payloader = kwargs.get('payloader')
        self.rtp_index = self.payloader.rtp_index
        self.rtp_protocol = kwargs.get('rtp_protocol')
        self.port = self.parent.get_next_remote_port()
        self.autolink = kwargs.get('autolink', True)
        s = self.payload_type = kwargs.get('payload_type', self.payloader.payload_type)
        #if s == 'src':
        #    elemstr = 'sink'
        #elif s == 'sink':
        #    elemstr = 'src'
        elemstr = s
        kwargs['gst_name'] = 'udp%s' % (elemstr)
        kwargs['name'] = ''.join(['udp', elemstr, self.rtp_protocol, str(self.rtp_index)])
        gst_props = kwargs.get('gst_properties', {})
        if elemstr == 'sink':
            gst_props['host'] = self.parent.remote_host
        elif elemstr == 'src':
            #gst_props['caps'] = self.payloader.get_pad('src').get_caps().copy()
            pass
        gst_props['port'] = self.port
        kwargs['gst_properties'] = gst_props
        super(UDPElement, self).__init__(**kwargs)
        self.parent.pipeline.elem_container.add(self._element)
        if self.payload_type == 'src':# and self.autolink:
            padstr = 'recv_%s_sink_%s' % (self.rtp_protocol, self.rtp_index)
            #pad = self.rtpbin.get_request_pad(padstr)
            self._element.link_pads('src', self.rtpbin, padstr)
        elif self.payload_type == 'sink':
            padstr = 'send_%s_src_%s' % (self.rtp_protocol, self.rtp_index)
            self.rtpbin.link_pads(padstr, self._element, 'sink')
        self.parent.pipeline.bind(pipeline_state=self.on_pipeline_state_changed)
        print 'udpelem built: index=%s, prot=%s, ptype=%s, port=%s' % (self.rtp_index, self.rtp_protocol, self.payload_type, self.port)
    @property
    def rtpbin(self):
        return self.parent._bin
        
    def on_pipeline_state_changed(self, **kwargs):
        value = kwargs.get('value')
        if value == 'playing' and self.rtp_protocol == 'rtcp' and self.payload_type == 'sink':
            self._element.set_locked_state(self._gst_module.STATE_PLAYING)
        

class Controller(BaseObject):
    def __init__(self, **kwargs):
        super(Controller, self).__init__(**kwargs)
        self.parent = kwargs.get('parent')
        
    def do_connect(self):
        self.sender = Sender()
        self.sender.start()
        self.server = Server(controller=self)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.start()
        self.connected = True
        
    def do_disconnect(self):
        self.server.shutdown()
        self.sender.stop()
        self.connected = False
        
    def on_request(self, attr, client):
        value = getattr(self.parent, attr, None)
        if value is None:
            return
        self.send(' '.join(['put', attr, value]), client)
        
    def on_return(self, attr, value, client):
        setattr(self.parent, attr, value)
        
    def send(self, msg, client):
        self.sender.add_message(msg, (client[0], self.parent.control_recv_port))
        
class Sender(threading.Thread):
    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.running = threading.Event()
        self.sending = threading.Event()
        self.queue = collections.deque()
    def add_message(self, msg, client):
        self.queue.append((msg, client))
        self.sending.set()
    def run(self):
        self.running.set()
        while self.running.isSet():
            self.sending.wait()
            if self.running.isSet():
                self.send_next_message()
    def stop(self):
        self.running.clear()
        self.sending.set()
    def send_next_message(self):
        if not len(self.queue):
            return
        msg, client = self.queue.popleft()
        print 'send: ', msg, client
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(msg, client)
        if not len(self.queue):
            self.sending.clear()
        
class Server(SocketServer.UDPServer):
    def __init__(self, **kwargs):
        self.controller = kwargs.get('controller')
        #host = (getattr(self.controller.parent, key) for key in ['remote_host', 'control_recv_port'])
        host = (detect_usable_address(), self.controller.parent.control_recv_port)
        print 'host= ', host
        SocketServer.UDPServer.__init__(self, host, ServerReqHandler)
        
class ServerReqHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        print 'recv: ', data
        if not len(data):
            return
        if data[:3] == 'get':
            attr = data.split(' ')[1]
            self.server.controller.on_request(attr, self.client_address)
        elif data[:3] == 'put':
            attr = data.split(' ')[1]
            value = ' '.join(data.split(' ')[2:])
            self.server.controller.on_return(attr, value, self.client_address)
        
def detect_usable_address():
    for addr in socket.gethostbyname_ex(socket.gethostname())[2]:
        if addr.split('.')[0] != '127':
            return addr
    return socket.gethostbyname('.'.join([socket.gethostname(), 'local']))
    
if __name__ == '__main__':
    class Dummy(object):
        def __init__(self):
            self.controller_hostaddr = '127.0.0.1'
            self.controller_hostport = 50011
            print 'build controller'
            self.controller = Controller(parent=self, is_server=True)
            print 'controller built'
    dummy = Dummy()
