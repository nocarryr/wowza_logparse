import os.path
from Bases import OSCBaseObject

import widgets, layout_parser

class TouchOSC(OSCBaseObject):
    osc_address = 'TouchOSC'
    def __init__(self, **kwargs):
        self.MainController = kwargs.get('MainController')
        self.osc_io = self.MainController.comm.osc_io
        self.root_address = 'TouchOSC'
        self.osc_parent_node = self.osc_io.root_node
        super(TouchOSC, self).__init__(**kwargs)
        
        filename = kwargs.get('layout_filename', os.path.join(os.path.dirname(__file__), 'touchosctest1.touchosc'))
        self.layout = layout_parser.Layout(filename=filename)
        self.ui_prototype = UIPrototype(MainController=self.MainController, 
                                        layout=self.layout, 
                                        osc_address=self.osc_address, 
                                        osc_parent_node=self.osc_parent_node)
        #self.build_test_src_obj()
        self.clients = {}
        self.client_obj = {}
        self.osc_io.add_client(name=self.root_address)
        #self.osc_node.addCallback('TouchOSC/1/*', self.on_message_test)
        #self.osc_node.addCallback('TouchOSC/1/*/*', self.on_message_test)
        #self.mrmrtest = mrmrIB(clients=['192.168.168.90'])
        self.MainController.comm.connect('state_changed', self.on_comm_state)
        self.testwidgets = {}
        
            
        self.osc_io.connect('client_added', self.on_osc_client_added)
        self.osc_io.connect('client_removed', self.on_osc_client_removed)
        self.osc_io.connect('new_master', self.on_osc_new_master)
            
    def build_test_src_obj(self):
        d = {'fdrtest1':{'group':'Dimmer', 'attr':'value'}, 
             'xytest1':{'group':'Position', 'attr':'value_seq'}}
        for name, info in d.iteritems():
            if 'group' in info:
                g = self.MainController.Selection.AttributeGroups[info['group']]
                uikwargs = {'src_object':g, 'src_attr':info['attr'], 'src_signal':'value_changed'}
                self.ui_prototype.set_src_object(name, **uikwargs)
            
    def add_client(self, **kwargs):
        client = kwargs.get('client')
        name = client.name
        self.clients.update({name:tuple([kwargs.get(key) for key in ['address', 'port']])})
        c = Client(name=name, addr=tuple([kwargs.get(key) for key in ['address', 'port']]), 
                   prototype=self.ui_prototype)
        c.set_link_state(self.osc_node.oscMaster)
        self.client_obj.update({name:c})
            
    def remove_client(self, **kwargs):
        client = kwargs.get('client')
        if client.name in self.clients:
            if client.name in self.testwidgets:
                for w in self.testwidgets[client.name].itervalues():
                    w.set_link_state(False)
                del self.testwidgets[client.name]
            self.client_obj[client.name].set_link_state(False)
            del self.client_obj[client.name]
    
    def build_client_widgets(self, client):
        d = {'tgltest1':{'cls':widgets.Toggle}, 
             'btntest1':{'cls':widgets.Button}, 
             'fdrtest1':{'cls':widgets.Fader, 'group':'Dimmer', 'attr':'value'}, 
             'xytest1':{'cls':widgets.xyPad, 'group':'Position', 'attr':'value_seq'}, 
             'label1':{'cls':widgets.Label}}
        self.testwidgets.update({client:{}})
        for name, info in d.iteritems():
            w_kwargs = dict(osc_address=name, osc_parent_node=self.osc_node, label=name, client=client)
            if 'group' in info:
                g = self.MainController.Selection.AttributeGroups[info['group']]
                w_kwargs.update({'src_object':g, 'src_attr':info['attr'], 'src_signal':'value_changed'})
            w = info['cls'](**w_kwargs)
            w.connect('value_update', self.on_testwidget_update)
            self.testwidgets[client].update({name:w})
            w.set_link_state(True)
        for x in range(1, 9):
            csnode = self.osc_node.add_new_node(name='CueStack')
            btnnode = csnode.add_new_node(name='push')
            lblnode = csnode.add_new_node(name='label')
            
            w_kwargs = dict(osc_address=str(x), client=client)
            stack = self.MainController.CueStacks.values()[0]
            snapshot = stack.snapshots_indexed.get(x)
            if snapshot:
                w_kwargs.update({'src_object':snapshot, 
                                 'src_attr':'active', 
                                 'src_signal':'active_changed', 
                                 'osc_parent_node':btnnode})
                w = widgets.Button(**w_kwargs)
                self.testwidgets[client].update({'/'.join(['push', w.osc_address]):w})
                w.set_link_state(True)
                w_kwargs.update({'src_attr':'name', 
                                 'src_signal':'property_changed', 
                                 'osc_parent_node':lblnode, 
                                 'label':snapshot.name})
                w = widgets.Label(**w_kwargs)
                self.testwidgets[client].update({'/'.join(['push', w.osc_address]):w})
                w.set_link_state(True)
        
    def on_testwidget_update(self, **kwargs):
        print 'value_update:', kwargs
        
    def on_message_test(self, *args):
        print args
        
    def on_comm_state(self, **kwargs):
        if kwargs.get('state'):
            #r = self.osc_node.get_root_node()
            #btnargs = ['nil', .1, 4, 4, 1, 1, 1, 1, 'test']
            #r.send_message(root_address='mrmrIB', address=['mrmrIB', 'pushbutton'], value=btnargs)
            #self.osc_node.send_message(root_address=self.root_address, address='1/label1', value='test')
            
            pass
            
    def on_osc_client_added(self, **kwargs):
        client = kwargs.get('client')
        if self.root_address in client.name:
            self.add_client(**kwargs)
        
    def on_osc_client_removed(self, **kwargs):
        self.remove_client(**kwargs)
            
    def on_osc_new_master(self, **kwargs):
       for c in self.client_obj.itervalues():
           c.set_link_state(self.osc_node.oscMaster)
                
class UIPrototype(OSCBaseObject):
    def __init__(self, **kwargs):
        super(UIPrototype, self).__init__(**kwargs)
        self.MainController = kwargs.get('MainController')
        self.layout = kwargs.get('layout')
        self.widgets = {}
        self.src_objects = kwargs.get('src_objects', {})
        for key, val in self.layout.AllControls.iteritems():
            cls = widgets.find_widget_type(val)
            if cls:
                address = '/'.join(val.osc_cs.split('/'))
                node = self.osc_parent_node.add_new_node(address=address)
                w = cls(osc_parent_node=node._parent, control=val, prototype=True)
                self.widgets.update({w.id:w})
    def set_src_object(self, name, **kwargs):
        self.src_objects.update({name:kwargs.copy()})
        

class Client(OSCBaseObject):
    def __init__(self, **kwargs):
        self.prototype = kwargs.get('prototype')
        for key in ['osc_address', 'osc_parent_node']:
            kwargs.setdefault(key, getattr(self.prototype, key))
        super(Client, self).__init__(**kwargs)
        self.name = kwargs.get('name')
        self.addr = kwargs.get('addr')
        self.widgets = {}
        self.src_objects = {}
        for key, val in self.prototype.widgets.iteritems():
            cls = val.__class__
            w_kwargs = dict(osc_parent_node=val.osc_parent_node, 
                    control=val.control, client=self.name)
            w_kwargs.update(self.prototype.src_objects.get(key, {}))
            w = cls(**w_kwargs)
            self.widgets.update({key:w})
        
    def set_link_state(self, state):
        for w in self.widgets.itervalues():
            w.set_link_state(state)
        