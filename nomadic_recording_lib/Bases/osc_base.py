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
# osc_base.py
# Copyright (c) 2010 - 2011 Matthew Reid

import sys

from BaseObject import BaseObject
from Properties import PropertyConnector

ILLEGAL_ADDRESS_CHARS = ' #*,/?[]{}()'
REPLACE_ADDRESS_CHARS = {' ':'_', ',':'-'}

def join_address(*args):
    s = '/'.join(['/'.join(arg.split('/')) for arg in args])
    return s
    
def pack_args(value):
    if isinstance(value, list) or isinstance(value, tuple):
        return value
    elif value is None:
        return []
    return [value]
    
def get_node_path(node):
    parent = node
    path = []
    while parent is not None:
        path.append(parent._name)
        parent = parent._parent
    path.reverse()
    return join_address(*path)

def format_address(address):
    for c in ILLEGAL_ADDRESS_CHARS:
        if c in address:
            r = REPLACE_ADDRESS_CHARS.get(c, '')
            address = r.join(address.split(c))
    if "'" in address:
        address = ''.join(address.split("'"))
    return address

class OSCBaseObject(BaseObject):
    _saved_attributes = ['osc_address']
    def __init__(self, **kwargs):
        #self.osc_enabled = False
        address = kwargs.get('deserialize', {}).get('attrs', {}).get('osc_address')
        if not address:
            address = kwargs.get('osc_address')
        #address = kwargs.get('deserialize', {}).get('attrs', {}).get('osc_address', kwargs.get('osc_address'))
        if address is None and hasattr(self, 'osc_address'):
            address = getattr(self, 'osc_address')
        if address is not None:
            self.osc_address = format_address(str(address))
        parent = kwargs.get('osc_parent_node')
        if parent is None and hasattr(self, 'osc_parent_node'):
            parent = getattr(self, 'osc_parent_node')
        if parent is not None:
            self.osc_parent_node = parent
        self.init_osc_attrs()
        if not self.osc_enabled:
            self.osc_address = None
        if 'deserialize' in kwargs and self.osc_enabled:
            kwargs['deserialize']['attrs']['osc_address'] = self.osc_address
        super(OSCBaseObject, self).__init__(**kwargs)
            
    @property
    def osc_enabled(self):
        parent = getattr(self, 'osc_parent_node', None)
        addr = getattr(self, 'osc_address', None)
        return None not in [parent, addr]
        
    def init_osc_attrs(self, **kwargs):
        osc_address = kwargs.get('osc_address')
        if osc_address:
            self.osc_address = format_address(osc_address)
        if not self.osc_enabled:
            return
        if not hasattr(self, 'osc_handlers'):
            self.osc_handlers = {}
        if not hasattr(self, 'osc_child_nodes'):
            self.osc_child_nodes = set()
        if not hasattr(self, 'osc_node'):
            self.osc_node = self.osc_parent_node.add_child(name=self.osc_address)
        self.set_osc_address(self.osc_address)
        
    def unlink(self):
        def remove_node(n):
            if n.parent is not None:
                n.parent.remove_node(name=n.name)
        if self.osc_enabled:
            for handler in self.osc_handlers.itervalues():
                handler.unlink()
                #n = handler.osc_node
                #if n != self.osc_node:
                #    remove_node(n)
            #remove_node(self.osc_node)
            if self.osc_node.parent is not None:
                self.osc_node.parent.remove_node(name=self.osc_node.name)
        super(OSCBaseObject, self).unlink()
        
    def set_osc_address(self, address):
        if not self.osc_enabled or address is None:
            return
        address = format_address(address)
        self.osc_address = address
        self.osc_node.name = address
            
    def add_osc_child(self, **kwargs):
        if self.osc_enabled:
            address = kwargs.get('address')
            d = {'osc_address':address, 'osc_parent_node':self.osc_node}
            return d
        return {}
        
    def add_osc_handler(self, **kwargs):
        '''Add an OSC handler
        :Parameters:
            'address' : Relative address to self.osc_node. Default is
                        None which will use the address of self.osc_node
            'callbacks' : Dict of {'address':callback} to handle. Default is None
                          which disables callback mode and requires parameters below.
            'Property' : links a Property object to the osc handler so you don't have
                         to do anything yourself anymore (uses PropertyConnector).
                         give it a Property object or string of the Property name.
            'request_initial_value' : bool
        '''
        if not self.osc_enabled:
            return
        
        address = kwargs.get('address')
        Property = kwargs.get('Property')
        all_sessions = kwargs.get('all_sessions', False)
        if Property is not None:
            if type(Property) == str:
                Property = self.Properties[Property]
                kwargs['Property'] = Property
            address = Property.name
        
        
        if address is None:
            node = self.osc_node
            address = self.osc_address
            kwargs['address'] = address
        else:
            node = self.osc_node.add_child(name=address)
        kwargs.setdefault('osc_node', node)
        
        objhandler = self.osc_handlers.get(address)
        if not objhandler:
            objhandler = OSCHandler(**kwargs)
            self.osc_handlers.update({address:objhandler})
        else:
            objhandler.add_callbacks(**kwargs.get('callbacks', {}))
        return objhandler
            
    def remove_osc_handler(self, **kwargs):
        key = kwargs.get('id')
        if key in self.osc_handlers:
            self.osc_handlers[key].remove_callbacks()
            del self.osc_handlers[key]

class OSCHandler(BaseObject, PropertyConnector):
    def __init__(self, **kwargs):
        super(OSCHandler, self).__init__()
        self.Property_set_by_osc = False
        self.callbacks = {}
        self.request_initial_value = kwargs.get('request_initial_value')
        self.address = kwargs.get('address')
        #self.callbacks = kwargs.get('callbacks')
        self.osc_node = kwargs.get('osc_node')
        #self.osc_node.addCallback(self.address+'/*', self.handle_message)
        callbacks = kwargs.get('callbacks', {})
        self.add_callbacks(**callbacks)
        self.send_root_address = kwargs.get('send_root_address')
        self.send_client = kwargs.get('send_client')
        self.all_sessions = kwargs.get('all_sessions', False)
        self.use_timetags = kwargs.get('use_timetags', True)
        self.Property = kwargs.get('Property')
        
    def unlink(self):
        self.Property = None
        #self.remove_callbacks()
        super(OSCHandler, self).unlink()
        
    def add_callbacks(self, **kwargs):
        self.callbacks.update(kwargs)
        for key in kwargs.iterkeys():
            node = self.osc_node.add_child(name=key)
            node.bind(message_received=self.handle_message)
            #self.osc_node.addCallback('%s/%s' % (self.address, key), self.handle_message)
            #print self.osc_node._name, '%s/%s' % (self.address, key)
            
    def remove_callbacks(self):
        for key in self.callbacks.keys()[:]:
            try:
                self.osc_node.remove_node(name=key)
                #self.osc_node.removeCallback('%s/%s' % (self.address, key), self.handle_message)
                self.LOG.info(self.address, 'callback removed', key)
                del self.callbacks[key]
            except:
                self.LOG.warning(self.address, 'could not remove callback', key)
            
    def handle_message(self, **kwargs):
        message = kwargs.get('message')
        address = message.address
        client = kwargs.get('client')
        #method = address.split('/')[-1:][0]
        method = address.tail
        #print 'received: address=%s, method=%s, args=%s' % (address, method, message.getValues())
        cb_kwargs = dict(method=method, address=address, values=message.get_arguments(), client=client)
        #if self.osc_node.get_client_cb:
        #    cb_kwargs['client'] = self.osc_node.get_client_cb(hostaddr=hostaddr)
        #else:
        #    self.LOG.warning(self, 'no callback!!!!')
        if method in self.callbacks:
            #print 'osc_callback: ', address, message.getValues()
            self.callbacks[method](**cb_kwargs)
        elif '*' in ''.join(self.callbacks.keys()):
            for key, cb in self.callbacks.iteritems():
                if '*' in key:
                    cb(**cb_kwargs)
        else:
            self.LOG.warning('msg not handled: cb_kwargs = ', cb_kwargs)
            
    def send_methods(self):
        pass
        
    def attach_Property(self, prop):
        super(OSCHandler, self).attach_Property(prop)
        self.Property_set_by_osc = False
        self.add_callbacks(**{'set-value':self.on_osc_Property_value_changed, 
                              'current-value':self.on_osc_Property_value_requested})
        if not self.osc_node.oscMaster and self.request_initial_value:
            self.request_Property_value()
                
    def on_Property_value_changed(self, **kwargs):
        self.send_Property_value_to_osc()
        
    def set_message_defaults(self, **kwargs):
        kwargs.setdefault('all_sessions', self.all_sessions)
        if not self.use_timetags:
            kwargs.setdefault('timetag', -1)
        if self.send_client is not None:
            kwargs.setdefault('client', self.send_client)
        if self.send_root_address is not None:
            kwargs.setdefault('root_address', self.send_root_address)
        return kwargs
        
    def send_Property_value_to_osc(self, **kwargs):
        if self.Property_set_by_osc:
            #self.Property_set_by_osc = False
            return
        value = self.get_Property_value()
        if isinstance(value, dict):
            args = []
            for key, val in value.iteritems():
                args.extend([key, val])
        elif isinstance(value, list):
            args = value
        else:
            args = [value]
        kwargs = self.set_message_defaults(**kwargs)
        kwargs.update(address='set-value', value=args)
        self.osc_node.send_message(**kwargs)
            
    def on_osc_Property_value_changed(self, **kwargs):
        args = kwargs.get('values')
        ptype = self.Property._type
        if ptype is not None:
            if issubclass(ptype, dict):
                ## make sure there's an even number of arguments
                if not len(args) or len(args) % 2 != 0:
                    return
                keys = [args[i] for i in range(0, len(args), 2)]
                vals = [args[i] for i in range(1, len(args), 2)]
                value = dict(zip(keys, vals))
            elif issubclass(ptype, list):
                value = args
            else:
                return
        else:
            value = args[0]
        self.Property_set_by_osc = True
        self.set_Property_value(value)
        self.Property_set_by_osc = False
                
    def on_osc_Property_value_requested(self, **kwargs):
        self.send_Property_value_to_osc(client=kwargs.get('client').name)
        
    def request_Property_value(self, **kwargs):
        kwargs = self.set_message_defaults(**kwargs)
        kwargs['address'] = 'current-value'
        self.osc_node.send_message(**kwargs)
