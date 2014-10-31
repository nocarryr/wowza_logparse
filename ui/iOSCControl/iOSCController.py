import os
import socket
import threading

from Bases import OSCBaseObject, ChildGroup

import jsonhandler
import widgets

from pagemenu import PageMenu
from sessionselect import SessionSelect

class iOSCController(OSCBaseObject):
    BuildEmissionThread = True
    def __init__(self, **kwargs):
        self.comm = kwargs.get('comm')
        #kwargs.setdefault('osc_parent_node', self.MainController.osc_parent_node)
        kwargs.setdefault('osc_address', 'iOSCControl')
        super(iOSCController, self).__init__(**kwargs)
        self.widgets = {}
        self.clients = {}
        
        for client in self.comm.osc_io.clients.itervalues():
            self.on_osc_client_added(client=client)
        self.comm.osc_io.bind(client_added=self.on_osc_client_added, 
                              client_removed=self.on_osc_client_removed)
        self.comm.osc_io.SessionManager.bind(oscMaster=self.on_osc_new_master)
        
        #self.SelectionGroup = self.MainController.add_group(name='OSCControl', id='OSCControl', index=999)
        self.add_osc_handler(callbacks={'dummy':self.dummy_cb})
        
    def unlink(self):
        for c in self.clients.values()[:]:
            self.remove_client(client=c)
        self.stop_ParentEmissionThread()
        super(iOSCController, self).unlink()
        
    def dummy_cb(self, **kwargs):
        pass
        
    def _send_widget_to_client(self, **kwargs):
        w = kwargs.get('widget')
        clients = kwargs.get('clients')
        if not clients:
            #clients = self.clients.values()
            clients = [w.client]
        if self.osc_node.oscMaster:
            root = self.osc_node.get_root_node()
            for client in clients:
                l = w.build_interface_dict(traverse_tree=False)#root_address=client.osc_name)
                for d in l:
                    s = jsonhandler.build_json(d)
                    #s = s.join(["\'"]*2)
                    root.send_message(address='/control/addWidget', value=s, 
                                      client=client.name)
        
    def add_widget(self, obj, **kwargs):
        client = kwargs.get('client')
        def do_add_widget(w):
            if client.name not in self.widgets:
                self.widgets[client.name] = {}
            self.widgets[client.name].update({w.id:w})
            w.bind(interface_update=self.on_widget_interface_update, 
                   add_widget=self.on_widget_add_child, 
                   remove_widget=self.on_widget_remove_child)
            self._send_widget_to_client(widget=w)
            return w
        if isinstance(obj, widgets.BaseWidget):
#            d = dict(osc_root_address=self.osc_address, 
#                     osc_client_address='DWT_iPad')
#            for key, val in d.iteritems():
#                if getattr(obj, key) is None:
#                    setattr(obj, key, val)
            return do_add_widget(obj)
            
        cls = None
        if type(obj) == str:
            cls = widgets.widget_classes.get(obj)
        elif issubclass(obj, widgets.BaseWidget):
            cls = obj
        if cls:
            w_kwargs = kwargs.copy()
            d = dict(osc_parent_node=self.osc_node, 
                     osc_root_address=self.osc_address, 
                     ParentEmissionThread=self.ParentEmissionThread)
            for key, val in d.iteritems():
                if key not in w_kwargs:
                    w_kwargs[key] = val
            w = cls(**w_kwargs)
            return do_add_widget(w)
        
#    def build_interface(self, **kwargs):
#        client_name = kwargs.get('client_name')
#        template = kwargs.get('template')
#        name = kwargs.get('interface_name')
#        orientation = kwargs.get('orientation')
#        
#        if not template:
#            template = jsonhandler.load_template()
#        script = template['script']
#        if name:
#            script = jsonhandler.set_script_vars(script, loadedInterfaceName=name)
#        if orientation:
#            script = jsonhandler.set_script_vars(script, interfaceOrientation=orientation)
#        #dest = [str(self.comm.osc_io.hostdata[key]) for key in ['hostaddr', 'recvport']]
#        #script += 'destinationManager.selectIPAddressAndPort("%s", "%s");' % (dest[0], dest[1])
#        
#        template['script'] = script
#        
#        for w in self.widgets.itervalues():
#            l = w.build_interface_dict(root_address=client_name)
#            template['pages'][0].extend(l)
#            
#        if 'js_kwargs' in kwargs:
#            template['js_kwargs'] = kwargs['js_kwargs']
#        return jsonhandler.build_interface(**template)
        
    def send_client_interface(self, **kwargs):
        name = kwargs.get('name')
        client = self.clients.get(name)
        if client:
            #s = self.build_interface(client_name=client.osc_name, orientation='landscape', interface_name='test1')
            #if len(s) > 4000:
            #    raise MsgLengthError
            #self.osc_node.get_root_node().send_message(root_address='control', address=['','pushInterface'],
            #                                           value=s, client=client.name)
            root = self.osc_node.get_root_node()
            local = self.comm.osc_io.local_client
            root.send_message(address='/control/pushDestination', 
                              value=':'.join([local.address, str(local.port)]), 
                              client=client.name)
            root.send_message(address='/control/createBlankInterface', 
                              value=['test2', 'landscape'], client=client.name)
            #root.send_message(root_address='control', address=['', 'setBounds'], 
            #                  value=['menuButton', .8, .85, .2, .15], client=client.name)
            for key in ['menuButton', 'menuButtonLabel']:
                root.send_message(address='/control/removeWidget', 
                                  value=[key], client=client.name)
            for w in self.widgets.get(client.name, {}).itervalues():
                l = w.build_interface_dict()#root_address=client.osc_name)
                for d in l:
                    s = jsonhandler.build_json(d)
                    #s = s.join(["\'"]*2)
                    root.send_message(address='/control/addWidget', value=s, 
                                      client=client.name)
                w.refresh_interface()
        
    def reset_interface(self, **kwargs):
        client = kwargs.get('client')
        root = self.osc_node.get_root_node()
        local = self.comm.osc_io.local_client
        root.send_message(address='/control/pushDestination', 
                          value=':'.join([local.address, str(local.port)]), 
                          client=client.name)
        root.send_message(address='/control/createBlankInterface', 
                          value=['test2', 'landscape'], client=client.name)
        for key in ['menuButton', 'menuButtonLabel']:
            root.send_message(address='/control/removeWidget', 
                              value=[key], client=client.name)
        
    def add_client(self, **kwargs):
        client = kwargs.get('client')
        if client.name not in self.clients:
            iosc_client = iOscClient(iOsc=self, client=client)
            self.clients[client.name] = iosc_client
            if self.osc_node.oscMaster:
                iosc_client.activate()
            
    def remove_client(self, **kwargs):
        client = kwargs.get('client')
        if client.name in self.clients:
            #self.clients[client.name].unlink()
            self.clients[client.name].deactivate()
            widgets = self.widgets.get(client.name)
            if widgets is not None:
                for key in widgets.keys()[:]:
                    widgets[key].remove()
                self.widgets[client.name].clear()
            del self.clients[client.name]
        
    def on_widget_interface_update(self, **kwargs):
        widget = kwargs.get('widget')
        address = kwargs.get('address')
        value = kwargs.get('value')
        add_id = kwargs.get('add_widget_id')
        if add_id:
            value = [widget.id] + value
        #print 'interface_update: widget=%s, address=%s, value=%s' % (widget.id, address, value)
        self.osc_node.get_root_node().send_message(address='/control/' + address, 
                                                   value=value, 
                                                   client=widget.client.name)
        
    def on_widget_add_child(self, **kwargs):
        widget = kwargs.get('widget')
        client = widget.client.name
        #print 'widget %s add_child %s' % (kwargs['parent'].name, widget.name)
        #self.widgets[client][widget.id] = widget
        self._send_widget_to_client(widget=widget)
        
    def on_widget_remove_child(self, **kwargs):
        widget = kwargs.get('widget')
        client = widget.client.name
        #print 'widget %s remove' % (widget.name)
        self.osc_node.get_root_node().send_message(address='/control/removeWidget', 
                                                   value=[widget.id], 
                                                   client=client)
        if widget.id in self.widgets.get(client, {}):
            #widget.unbind(self)
            del self.widgets[client][widget.id]
        
    def on_osc_new_master(self, **kwargs):
        ## link if master is local, unlink if not
        #print kwargs
        #print self.clients
        if self.osc_node.oscMaster:
            for c in self.clients.itervalues():
                self.LOG.info('sending to ', c.name)
                c.activate()
        else:
            for c in self.clients.itervalues():
                c.deactivate()
        #self.set_widget_links(self.osc_node.oscMaster)
    
    def on_osc_client_added(self, **kwargs):
        client = kwargs.get('client')
        #if 'Control' in client.name:
        if client.port == 8080:
            client.sendAllUpdates = True
            client.accepts_timetags = False
            self.add_client(**kwargs)
            
            
    def on_osc_client_removed(self, **kwargs):
        client = kwargs.get('client')
        #if 'Control' in client.name:
        if client.port == 8080:
            self.remove_client(**kwargs)
            

class iOscClient(OSCBaseObject):
    def __init__(self, **kwargs):
        self.iOsc = kwargs.get('iOsc')
        self.osc_io = self.iOsc.comm.osc_io
        client_obj = kwargs.get('client')
        kwargs.setdefault('osc_parent_node', self.iOsc.osc_node)
        kwargs.setdefault('osc_address', client_obj.name)
        kwargs.setdefault('ParentEmissionThread', self.iOsc.ParentEmissionThread)
        self.session_select_remove_thread = None
        super(iOscClient, self).__init__(**kwargs)
        print 'IOSC_CLIENT: ', client_obj.name, self.osc_node.name, self.osc_node.get_full_path()
        for key in client_obj.Properties.iterkeys():
            setattr(self, key, getattr(client_obj, key))
        client_obj.bind(property_changed=self.on_client_obj_property_changed)
        self.osc_name = self.client_obj.osc_name
        self.Menu = None
        self.session_select = None
        
    @property
    def client_obj(self):
        return self.osc_io.clients.get(self.name)
        
    def unlink(self):
        self.deactivate()
        super(iOscClient, self).unlink()
        
    def activate(self):
        sessions = self.osc_io.discovered_sessions
        if len(sessions) == 1:
            self.build_menu()
        elif self.osc_io.isRingMaster:
            self.build_session_select()
        
    def deactivate(self):
        if self.Menu is not None:
            self.Menu.unlink()
            self.Menu = None
        if self.session_select is not None:
            self.session_select.unlink()
            self.session_select = None

    def build_menu(self):
        if self.Menu is not None:
            return
        self.iOsc.reset_interface(client=self)
        self.Menu = PageMenu(iOsc=self.iOsc, client=self)
        
    def build_session_select(self):
        if self.session_select is not None:
            return
        self.iOsc.reset_interface(client=self)
        self.session_select = SessionSelect(iOsc=self.iOsc, client=self)
        self.session_select.bind(selection=self.on_session_selected)
        
    def on_session_selected(self, **kwargs):
        session = kwargs.get('value')
        self.session_select.unlink()
        self.session_select = None
        self.client_obj.session_name = session
        
    def on_client_obj_property_changed(self, **kwargs):
        prop = kwargs.get('Property')
        value = kwargs.get('value')
        setattr(self, prop.name, value)
        if prop.name == 'session_name':
            #if self.osc_io.isMaster and self.client_obj.session_name == self.GLOBAL_CONFIG['session_name']:
            if self.osc_io.discovered_sessions[value].master == self.osc_io.local_client:
                self.build_menu()

class MsgLengthError(Exception):
    def __str__(self):
        return 'message length exceeded'
        
