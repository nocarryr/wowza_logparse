import sys
import traceback
import threading
import time
import datetime
import weakref
if __name__ == '__main__':
    import sys
    import os.path
    p = os.path.dirname(__file__)
    for i in range(2):
        p = os.path.split(p)[0]
    sys.path.append(p)
from Bases import BaseObject, Scheduler
from messages import Address, Message, Bundle, parse_message


def seconds_from_timedelta(td):
    return td.seconds + td.days * 24 * 3600 + (td.microseconds / float(10**6))
    
OSC_EPOCH = datetime.datetime(1900, 1, 1, 0, 0, 0)
PY_EPOCH = datetime.datetime.utcfromtimestamp(0.)
OSC_EPOCH_TIMESTAMP = seconds_from_timedelta(PY_EPOCH - OSC_EPOCH)

def timetag_to_datetime(**kwargs):
    timetag_obj = kwargs.get('timetag_obj')
    if timetag_obj is not None:
        value = timetag_obj.value
    else:
        value = kwargs.get('value')
    td = datetime.timedelta(seconds=value)
    return OSC_EPOCH + td
    
def datetime_to_timetag_value(dt):
    td = dt - OSC_EPOCH
    return seconds_from_timedelta(td)
    
def timestamp_to_timetag_value(ts):
    return ts + OSC_EPOCH_TIMESTAMP
    
def timetag_to_timestamp(tt):
    return tt - OSC_EPOCH_TIMESTAMP
    
def pack_args(value):
    if isinstance(value, list) or isinstance(value, tuple):
        return value
    elif value is None:
        return []
    return [value]
    
class MyWVDict(weakref.WeakValueDictionary):
    def __init__(self, *args, **kwargs):
        weakref.WeakValueDictionary.__init__(self, *args, **kwargs)
        def remove(wr, selfref=weakref.ref(self)):
            self = selfref()
            if self is not None:
                print 'REMOVE oscnode: ', wr.key
                del self.data[wr.key]
                print 'len = ', len(self.data)
        self._remove = remove
    def __setitem__(self, key, value):
        weakref.WeakValueDictionary.__setitem__(self, key, value)
        print 'ADD oscnode: ', value
        print 'add len = ', len(self.data)
    def __delitem__(self, key):
        print 'DEL oscnode: ', key, id(self[key])

all_osc_nodes = MyWVDict()

class OSCNode(BaseObject):
    _Properties = {'name':dict(default=''), 
                   'children':dict(type=dict), 
                   'send_interrupt_enabled':dict(default=False), 
                   'send_interrupt_recursive':dict(default=False), 
                   'receive_interrupt_enabled':dict(default=False), 
                   'receive_interrupt_recursive':dict(default=False)}
    def __init__(self, **kwargs):
        super(OSCNode, self).__init__(**kwargs)
        self.register_signal('message_received', 'message_not_dispatched')
        self.parent = kwargs.get('parent')
        self.is_root_node = kwargs.get('root_node', False)
        #self.bind(name=self._on_name_set)
        self.name = kwargs.get('name')
        if self.name is None or not len(self.name):
            self.name = str(id(self))
        if self.is_root_node:
            self.debug = self.GLOBAL_CONFIG.get('arg_parse_dict', {}).get('debug_osc')
            self._oscMaster = kwargs.get('oscMaster', False)
            self.get_client_cb = kwargs.get('get_client_cb')
            self.transmit_callback = kwargs.get('transmit_callback')
            self.get_epoch_offset_cb = kwargs.get('get_epoch_offset_cb')
            self._dispatch_thread = OSCDispatchThread(osc_tree=self)
            self._dispatch_thread.start()
        else:
            self.get_client_cb = self.parent.get_client_cb
            self._oscMaster = self.parent._oscMaster
            for key in ['send', 'receive']:
                for attr in ['enabled', 'recursive']:
                    propname = '_'.join([key, 'interrupt', attr])
                    setattr(self, propname, getattr(self.parent, propname))
            self.parent.bind(property_changed=self.on_parent_property_changed)
        if self.GLOBAL_CONFIG.get('debug_osc_nodes'):
            all_osc_nodes[str(self.get_full_path())] = self
    @property
    def oscMaster(self):
        return self._oscMaster
    @oscMaster.setter
    def oscMaster(self, value):
        if value != self.oscMaster:
            self.get_root_node()._set_oscMaster(value)
        
    @property
    def dispatch_thread(self):
        return self.get_root_node()._dispatch_thread
        
    def on_parent_property_changed(self, **kwargs):
        prop = kwargs.get('Property')
        if 'interrupt' not in prop.name:
            return
        value =  kwargs.get('value')
        key, i, attr = prop.name.split('_')
        if attr == 'recursive':
            setattr(self, prop.name, value)
        elif attr == 'enabled':
            recursive = getattr(self, '_'.join([key, 'interrupt', 'recursive']))
            if recursive:
                setattr(self, prop.name, value)
        
    def _set_oscMaster(self, value):
        self._oscMaster = value
        for child in self.children.itervalues():
            child._set_oscMaster(value)
    def add_child(self, **kwargs):
        name = kwargs.get('name')
        address = kwargs.get('address', '')
        if len(address) and address[0] == '/':
            if not self.is_root_node:
                return self.get_root_node().add_child(**kwargs)
        parent = kwargs.get('parent', self)
        def do_add_node(**nkwargs):
            nkwargs.setdefault('parent', self)
            new_node = OSCNode(**nkwargs)
            #print 'new_node: parent=%s, name=%s, root=%s' % (self.name, new_node.name, new_node.is_root_node)
            self.children[new_node.name] = new_node
            new_node.bind(name=self.on_childnode_name_set, 
                          children=self.on_childnode_children_update)
            return new_node
        if parent != self:
            return parent.add_child(**kwargs)
        if not isinstance(address, Address):
            address = Address(address)
        if name is not None:
            address = address.append(name)
        #print address
        #elif 'name' in kwargs:
        #    address = Address(name)
        current, address = address.pop()
        #print 'current=%s, address=%s' % (current, address)
        node = self.children.get(current)
        if not node:
            node = do_add_node(name=current)
        if not len(address.split()):
            return node
        return node.add_child(address=address)
        
    def unlink(self):
        if self.GLOBAL_CONFIG.get('debug_osc_nodes'):
            key = self.get_full_path()
            if key in all_osc_nodes:
                del all_osc_nodes[key]
        if not self.is_root_node:
            for key in self.children.keys()[:]:
                self.remove_node(name=key)
        super(OSCNode, self).unlink()
        
    def remove_node(self, **kwargs):
        name = kwargs.get('name')
#        address = kwargs.get('address', '')
#        if not isinstance(address, Address):
#            address = Address(address)
#        if name is not None:
#            address = address.append(name)
#        current, address = address.pop()
        current = name
        node = self.children.get(current)
        if not node:
            return False
        #result = node.remove_node(address=address)
        
        if True:#result:
            node.unbind(self)
            node.unlink()
            del self.children[node.name]
        if not len(self.children):
            return True
            
    def unlink_all(self, direction='up', blocking=False):
        self.unlink()
        if self.is_root_node:
            self._dispatch_thread.stop(blocking=blocking)
        if direction == 'up' and not self.is_root_node:
            self.parent.unlink_all(direction, blocking)
        elif direction == 'down':
            for c in self.children.itervalues():
                c.unlink_all(direction, blocking)
                
    def on_childnode_name_set(self, **kwargs):
        old = kwargs.get('old')
        value = kwargs.get('value')
        node = kwargs.get('obj')
        #if not self.parent:
        #    return
        print self.name, ' : ', kwargs
        self.children[value] = node
        if self.children.get(old) == node:
            del self.children[old]
        
    def on_childnode_children_update(self, **kwargs):
        return
        old = kwargs.get('old')
        value = kwargs.get('value')
        node = kwargs.get('obj')
        removed = set(old.keys()) - set(value.keys())
        if len(removed) and not len(value):
            self.remove_node(name=obj.name)
            
    def get_full_path(self, address=None):
        if address is None:
            address = Address(self.name)
        else:
            address = address.append_right(self.name)
        if self.is_root_node:
            #print 'full path: ', address
            return address.as_root()
        return self.parent.get_full_path(address)
        
    def get_root_node(self):
        if self.is_root_node:
            return self
        return self.parent.get_root_node()
        
    def match_address(self, address):
        if not isinstance(address, Address):
            address = Address(address)
        if self.is_root_node:
            current, address = address.pop()
        #print self.name, ' match: ', address
        current, address = address.pop()
        if not len(current):
            return set([self])
        matched = set()
        nodes = set()
        node = self.children.get(current)
        if node:
            nodes.add(node)
        nodes |= self.match_wildcard(current)
        for node in nodes:
            matched |= node.match_address(address)
        return matched
        
    def match_wildcard(self, s):
        #print self.name, ' match wildcard ', s
        matched = set()
        children = self.children
        #if not len(set('*?[]{}') & set(s)):
        #    return matched
        if '*' in s:
            matched |= set(children.keys())
        elif '{' in s:
            keys = s.strip('{').strip('}').split(',')
            print 'matching {} wildcard: %s, keys=%s' % (s, keys)
            matched |= set(keys) & set(children.keys())
        for key in children.iterkeys():
            if not len(set('*?[]{}') & set(key)):
                continue
            if '*' in key:
                matched.add(key)
            elif '{' in key:
                if s in key:
                    matched.add(key)
        return set([children[key] for key in matched])
            
        
    def dispatch_message(self, **kwargs):
        if self.receive_interrupt_enabled:
            return
        if not self.is_root_node:
            self.get_root_node().dispatch_message(**kwargs)
            return
        element = kwargs.get('element')
        data = kwargs.get('data')
        client = kwargs.get('client')
        timestamp = kwargs.get('timestamp')
        if data:
            element = parse_message(data, client=client, timestamp=timestamp)
        if self.debug:
            self.LOG.info('osc recv: ' + str(element))
        self.dispatch_thread.add_element(element)
            
    def _do_dispatch_message(self, element):
        if isinstance(element, Bundle):
            m = element.get_flat_messages()
        else:
            m = [element]
        for msg in m:
            matched = self.match_address(msg.address)
            for node in matched:
                #print 'dispatching msg: ', msg.address, msg.get_arguments(), '(from %s)' % msg.client.name
                node.emit('message_received', message=msg, client=msg.client)
            if not len(matched):
                self.emit('message_not_dispatched', message=msg, client=msg.client)
                self.LOG.info('OSC msg not dispatched: ', msg.address, msg.get_arguments(), self.children.keys(), msg.client.name)
            
    def send_message(self, **kwargs):
        if self.send_interrupt_enabled:
            return
        if 'full_path' not in kwargs:
            address = kwargs.get('address')
            full_path = self.get_full_path()
            if address is not None:
                if not isinstance(address, Address):
                    address = Address(address)
                if len(address) and address[0] == '/':
                    full_path = address
                else:
                    full_path = full_path.append(address)
                del kwargs['address']
            kwargs['full_path'] = full_path
        if not self.is_root_node:
            return self.get_root_node().send_message(**kwargs)
        timetag = kwargs.get('timetag')
        if timetag is None:
            #now = datetime.datetime.now()
            now = time.time()
            offset = self.get_epoch_offset_cb()
            #timetag = datetime_to_timetag_value(now - offset)
            timetag = timestamp_to_timetag_value(now - offset)
        value = pack_args(kwargs.get('value'))
        message = Message(*value, address=kwargs['full_path'])
        bundle = Bundle(message, timetag=timetag)
        kwargs['element'] = bundle
        self.transmit_callback(**kwargs)
        return bundle
        

def get_ui_module(name):
    if name == 'kivy':
        return None
        #from kivy.clock import Clock
        #return Clock
    elif name == 'gtk':
        return None
    t = imp.find_module(name)
    module = imp.load_module(name, *t)
    return module

class OSCDispatchThread(Scheduler):
    _ui_mode_dispatch_methods = {'gtk':'gtk_do_dispatch', 
                                 'kivy':'kivy_do_dispatch'}
    def __init__(self, **kwargs):
        kwargs.setdefault('thread_id', 'OSCDispatcher')
        super(OSCDispatchThread, self).__init__(**kwargs)
        #self.running = threading.Event()
        #self.ready_to_dispatch = threading.Event()
        #self.LOG = BaseObject().LOG
        #self.bundles = {}
        self.osc_tree = kwargs.get('osc_tree')
        self.do_dispatch = self._do_dispatch
        self.ui_module = None
        self.kivy_messengers = set()
        ui = self.osc_tree.GLOBAL_CONFIG.get('ui_mode')
        if ui is not None and ui != 'text':
            self.ui_module = get_ui_module(ui)
            attr = self._ui_mode_dispatch_methods.get(ui)
            if attr:
                self.do_dispatch = getattr(self, attr)
        self.callback = self.do_dispatch
        
    def add_element(self, element):
        if not isinstance(element, Bundle) or element.timetag < 0:
            self._do_dispatch(element, element.timestamp)
        else:
            offset = self.osc_tree.get_epoch_offset_cb()
            bundles = element.split_bundles()
            for bundle in bundles.itervalues():
                ts = timetag_to_timestamp(bundle.timetag)
                ts += offset
                self.add_item(ts, bundle)
        
    def old_run(self):
        self.running.set()
        while self.running.isSet():
            self.ready_to_dispatch.wait()
            if not self.running.isSet():
                return
            ts = self.get_next_timestamp()
            if ts is False:
                self.ready_to_dispatch.clear()
            else:
                #now = datetime.datetime.now()
                now = time.time()
                #orig_now = now
                offset = self.osc_tree.get_epoch_offset_cb()
                now = now + offset
                if ts <= now:
                    #print 'now=%s, ts=%s, offset=%s' % (orig_now.__repr__(), ts.__repr__(), offset.__repr__())
                    bundle = self.bundles[ts]
                    del self.bundles[ts]
                    #messages = bundle.get_messages()
                    try:
                        self.do_dispatch(bundle)
                    except:
                        tb = traceback.format_exc()
                        self.LOG.warning('OSC dispatch Exception Caught: \n' + tb)
                else:
                    self.ready_to_dispatch.clear()
                    #timeout = seconds_from_timedelta(dt - now)
                    timeout = ts - now
                    self.ready_to_dispatch.wait(timeout)
                    self.ready_to_dispatch.set()
                    
    def _do_dispatch(self, element, time):
        #for m in messages:
        try:
            self.osc_tree._do_dispatch_message(element)
        except:
            tb = traceback.format_exc()
            self.LOG.warning('OSC dispatch Exception Caught: \n' + tb)
            
    def gtk_do_dispatch(self, element, time):
        #self.ui_module.gdk.threads_enter()
        self._do_dispatch(element, time)
        #self.ui_module.gdk.threads_leave()
                
    def kivy_do_dispatch(self, element, time):
        #obj = Messenger(element=element, time=time, callback=self._on_kivy_msg_cb)
        #self.kivy_messengers.add(obj)
        #self.ui_module.schedule_once(obj.send, 0)
        self._do_dispatch(element, time)
        
    def _on_kivy_msg_cb(self, messenger):
        self._do_dispatch(messenger.element, messenger.time)
        self.kivy_messengers.discard(messenger)

class Messenger(object):
    __slots__ = ('element', 'time', 'callback', '__weakref__')
    def __init__(self, **kwargs):
        for key, val in kwargs.iteritems():
            setattr(self, key, val)
    def send(self, *args):
        self.callback(self)
        
if __name__ == '__main__':
    td = datetime.timedelta()
    def get_client(*args, **kwargs):
        pass
    def get_epoch(*args, **kwargs):
        return td
    def transmit(*args, **kwargs):
        element = kwargs.get('element')
        print str(element)
        e2 = parse_message(element.build_string())
        print [element.build_string()]
        print str(e2)
        root.dispatch_message(data=element.build_string())
    root = OSCNode(name='root', 
                   root_node=True, 
                   get_client_cb=get_client, 
                   get_epoch_offset_cb=get_epoch, 
                   transmit_callback=transmit)
    tail = root.add_child(address='blah/stuff/things')
    print tail.get_full_path()
    tail.send_message(value=[1, True, 'a'])
    print root.match_address('/root/blah/stuff/things')
