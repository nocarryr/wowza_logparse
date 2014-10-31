import socket
import threading
import array
#import jsonpickle
from Bases import OSCBaseObject, Serialization
from ola_IO import olaIO
from ..osc.osc_io import oscIO
from ..BaseIO import detect_usable_address

class OSCtoOLAHost(OSCBaseObject):
    osc_address = 'OSCtoOLA'
    ui_name = 'OLA (Open Lighting Architecture)'
    _Properties = {'connected':dict(fget='_connected_getter', fset='_connected_setter')}
    def __init__(self, **kwargs):
        self.osc_io = kwargs.get('osc_io')
        self.root_address = 'OSCtoOLA-' + socket.gethostname()
        self.direct_mode = False
#        if not self.osc_io:
#            self.direct_mode = True
#            s = 'OSCtoOLA'
#            io_kwargs = dict(confsection=s + '_io', app_address=s, root_address=s)
#            for key in ['hostaddr', 'hostport', 'mcastaddr', 'mcastport']:
#                if key in kwargs:
#                    io_kwargs.update({key:kwargs[key]})
#            self.osc_io = oscIO(**io_kwargs)
#            self.osc_io.add_client_name(socket.gethostname())
        self.osc_parent_node = self.osc_io.root_node
        super(OSCtoOLAHost, self).__init__(**kwargs)
        self.register_signal('state_changed')
        self.universes = {}
        
        self.olaIO = olaIO()
        #self.osc_io.add_client_name(self.root_address, update_conf=False)
        addr = detect_usable_address()
        port = self.osc_io.hostdata['recvport']
        self.osc_io.add_client(name=self.root_address, address=addr, port=port, 
                               update_conf=False, isLocalhost=False)
        self.osc_io.connect('new_master', self.on_osc_new_master)
        self.olaIO.connect('new_universe', self.on_new_ola_universe)
        self.olaIO.connect('state_changed', self.on_ola_state_changed)
        
        #self.add_osc_handler(callbacks={'request-universes':self.on_universes_requested})
        
        #self.do_connect()
        
#    @property
#    def connected(self):
#        return self.olaIO.connected
#    @connected.setter
#    def connected(self, value):
#        self.olaIO.connected = value
    def _connected_getter(self):
        return self.olaIO.connected
    def _connected_setter(self, value):
        self.olaIO.connected = value
        
    def do_connect(self):
        if self.direct_mode:
            self.osc_io.do_connect()
        self.olaIO.do_connect()
    def do_disconnect(self):
        def _do_disconnect():
            if self.direct_mode:
                self.osc_io.do_disconnect()
            self.olaIO.do_disconnect()
        for univ in self.universes.itervalues():
            univ.set_all_zero(True)
        t = threading.Timer(.5, _do_disconnect)
        t.daemon = True
        t.start()
        
        
    def on_ola_state_changed(self, **kwargs):
        self.emit('state_changed', **kwargs)
        
    def on_new_ola_universe(self, **kwargs):
        univ = kwargs.get('ola_universe')
        if univ.id not in self.universes:
            u_kwargs = self.add_osc_child(address=str(univ.id))
            u_kwargs.update({'ola_universe':univ, 'root_address':self.root_address})
            obj = OSCUniverse(**u_kwargs)
            self.universes.update({obj.id:obj})
            
    def on_universes_requested(self, **kwargs):
        d = {}
        for key, val in self.universes.iteritems():
            d.update({key:{}})
            for attr in ['id', 'name']:
                d[key].update({attr:getattr(val, attr)})
        s = Serialization.to_json(d)
        self.osc_node.send_message(root_address=self.root_address, address='universes-info', value=s)
        
    def on_osc_new_master(self, **kwargs):
        for univ in self.universes.itervalues():
            univ.set_all_zero(not self.osc_node.oscMaster)
        
    def on_app_exit(self, *args, **kwargs):
        self.LOG.info('oscola app exit')
        self.olaIO.on_app_exit()
        
class OSCUniverse(OSCBaseObject):
    def __init__(self, **kwargs):
        self._values = None
        self.all_zero = False
        super(OSCUniverse, self).__init__(**kwargs)
        self.register_signal('value_update')
        self.values = array.array('B', [0]*513)
        #print 'osc path: ', self.osc_node.get_full_path()
        self.root_address = kwargs.get('root_address')
        self.ola_universe = kwargs.get('ola_universe')
        self.ola_universe.Universe = self
        #self.id = self.ola_universe.id
        
        self.add_osc_handler(callbacks={'set-channel':self.on_universe_set_channel, 
                                        'dump-response':self.on_universe_dump_response})
        self.osc_node.send_message(root_address=self.root_address, client=self.root_address, address='request-dump')
        #print 'OSCtoOLA new_universe: uid=%s, name=%s, pyid=%s' % (self.id, self.name, id(self))
        
    @property
    def id(self):
        return self.ola_universe.id
    @property
    def name(self):
        return self.ola_universe.name
        
    @property
    def values(self):
        if self.all_zero:
            return array.array('B', [0]*513)
        return self._values
    @values.setter
    def values(self, values):
        self._values = values
    
    def on_universe_set_channel(self, **kwargs):
        values = kwargs.get('values')
        chan = values[0]
        value = values[1]
        self.values[chan-1] = value
        #print 'oscola univ update: ', chan, value
        #print 'update from osc: chan=%s, value=%s' % (chan, value)
        if not self.all_zero:
            self.emit('value_update', universe=self, values=self.values)
        
    def on_universe_dump_response(self, **kwargs):
        values = kwargs.get('values')
        for i, value in enumerate(values):
            self.values[i] = value
        self.emit('value_update', universe=self, values=self.values)
        
    def set_all_zero(self, state):
        self.all_zero = state
        self.emit('value_update', universe=self, values=self.values)
