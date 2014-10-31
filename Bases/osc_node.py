import sys
import threading
import datetime
import math
import struct
import imp
from txosc import dispatch, osc

from BaseObject import BaseObject


OSC_EPOCH = datetime.datetime(1900, 1, 1, 0, 0, 0)

def seconds_from_timedelta(td):
    return td.seconds + td.days * 24 * 3600 + (td.microseconds / float(10**6))

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
    
class OSCNode(BaseObject, dispatch.Receiver):
    _saved_class_name = 'OSCNode'
    _saved_child_objects = ['_childNodes']
    def __init__(self, **kwargs):
        #super(OSCNode, self).__init__()
        BaseObject.__init__(self, **kwargs)
        dispatch.Receiver.__init__(self)
        self.register_signal('child_added', 'child_removed')
        
        if 'name' in kwargs:
            self.setName(kwargs.get('name'))
        if 'parent' in kwargs:
            self.setParent(kwargs.get('parent'))
            self._oscMaster = self._parent._oscMaster
            self.get_client_cb = self._parent.get_client_cb
        else:
            self._oscMaster = kwargs.get('oscMaster', False)
            self.get_client_cb = kwargs.get('get_client_cb')
        self.is_root_node = kwargs.get('root_node', False)
        self.transmit_callback = kwargs.get('transmit_callback')
        if self.is_root_node:
            self.get_epoch_offset_cb = kwargs.get('get_epoch_offset_cb')
            self._dispatch_thread = OSCDispatchThread(osc_tree=self)
            self._dispatch_thread.start()
        
    def unlink(self):
#        for c in self._childNodes.itervalues():
#            if not isinstance(c, OSCNode):
#                continue
#            #c.unlink()
#            c.unbind(self)
        super(OSCNode, self).unlink()
        
    def unlink_all(self, direction='up', blocking=False):
        self.unlink()
        if self.is_root_node:
            self._dispatch_thread.stop(blocking=blocking)
        if direction == 'up' and not self.is_root_node:
            self._parent.unlink_all(direction, blocking)
        elif direction == 'down':
            for c in self._childNodes.itervalues():
                c.unlink_all(direction, blocking)
        
        
    @property
    def oscMaster(self):
        return self._oscMaster
    @oscMaster.setter
    def oscMaster(self, value):
        if value != self.oscMaster:
            self.get_root_node()._set_oscMaster(value)
            
    @property
    def epoch(self):
        return OSC_EPOCH
        
    @property
    def dispatch_thread(self):
        return self.get_root_node()._dispatch_thread
        
    def setName(self, newname):
        """
        Give this node a new name.
        @type newname: C{str}
        """
        p = self._parent
        if p and self._name in p._childNodes:
            del p._childNodes[self._name]
        self._name = newname
        if self._parent:
            self._parent._childNodes[self._name] = self
        
    def _set_oscMaster(self, value):
        self._oscMaster = value
        for child in self._childNodes.itervalues():
            child._set_oscMaster(value)
        
    def add_new_node(self, **kwargs):
        name = kwargs.get('name')
        address = kwargs.get('address')
        parent = kwargs.get('parent', self)
        if parent == self:
            if address:
                path = self._patternPath(address)
                nodes = self.search_nodes(path)
                node = self
                if nodes:
                    i = len(nodes) - 1
                    if nodes[i] == True:
                        return nodes[i-1]
                    node = nodes[i-1]
                    path = path[i:]
                    
                for s in path[1:]:
                    node = node.add_new_node(name=s)
                return node
            if name in self._childNodes:
                return self._childNodes[name]
            new_node = OSCNode(name=name, parent=self)
            new_node.bind(child_added=self._on_childNode_child_added, 
                          child_removed=self._on_childNode_child_removed)
            self.emit('child_added', node=self, name=name)
            return new_node
        if self._parent is not None:
            return self._parent.add_new_node(**kwargs)
        return None
        
    def search_nodes(self, path, index=0, result=None):
        if result is None:
            result = []
        if index != 0:
            result.append(self)
        if index >= len(path)-1:
            if path[index] == self._name:
                result.append(True)
            else:
                result.append(False)
            return result
        index += 1
        child = self._childNodes.get(path[index])
        if child:
            child.search_nodes(path, index, result)
        else:
            if result and result[len(result)-1] != True:
                result.append(False)
        return result
            
        
    def send_message(self, **kwargs):
        '''Send an OSC message object up through the tree and finally
        out of the root node
        :Parameters:
            'address' : relative OSC address from the node that is sending
            'value' : OSC args to send, can be list, tuple or single value
                        of any type supported by OSC
        '''
        if self.is_root_node:
            now = datetime.datetime.now()
            offset = self.get_epoch_offset_cb()
            kwargs['timetag'] = datetime_to_timetag_value(now - offset)
            self.transmit_callback(**kwargs)
            return
        address = kwargs.get('address')
        if type(address) == str:
            address = [address]
        address[0:0] = [self._name]
        kwargs['address'] = address
        self._parent.send_message(**kwargs)
        
    def get_full_path(self, address=None):
        if self.is_root_node:
            return address
        if address is None:
            address = []
        address[0:0] = [self._name]
        return self._parent.get_full_path(address)
        
    def get_root_node(self):
        if self.is_root_node:
            return self
        return self._parent.get_root_node()
        
    def addNode(self, name, instance):
        super(OSCNode, self).addNode(name, OSCNode())
        self._childNodes[name].bind(child_added=self._on_childNode_child_added, 
                                    child_removed=self._on_childNode_child_removed)
        self.emit('child_added', node=self, name=name)
        
    def removeNode(self, name):
        node = self._childNodes.get(name)
        if not node:
            return False
        for cname in node._childNodes.keys()[:]:
            node.removeNode(cname)
        node.removeCallbacks()
        
            #node.removeAllCallbacks()
        #node.unbind(self)
        #print 'removeNode: ', self, name
        #node.removeCallbacks()
        
    def _checkRemove(self):
        has_parent = self._parent is not None
        if has_parent and self._name in self._parent._childNodes:
            dispatch.Receiver._checkRemove(self)
        if has_parent and self._name not in self._parent._childNodes:
            #self._parent.unbind(self)
            #self.unlink()
            self._parent.emit('child_removed', node=self._parent, name=self._name)
            
    def _on_childNode_child_added(self, **kwargs):
        #if not self._parent:
        #    return
        #print self, 'added', kwargs
        self.emit('child_added', **kwargs)
        
    def _on_childNode_child_removed(self, **kwargs):
        #if not self._parent:
        #    return
        #print self, 'removed', kwargs
        self.emit('child_removed', **kwargs)
    
    def dispatch(self, element, client):
        if isinstance(element, osc.Bundle):
            self.dispatch_thread.add_bundle(element, client)
        else:
            #try:
            super(OSCNode, self).dispatch(element, client)
            #except:
            #    print 'could not dispatch stuff:\n%s\n%s %s' % (sys.exc_info(), element.address, element.getValues())
            

class Bundle(osc.Bundle):
    def toBinary(self):
        """
        Encodes the L{Bundle} to binary form, ready to send over the wire.

        @return: A string with the binary presentation of this L{Bundle}.
        """
        data = osc.StringArgument("#bundle").toBinary()
        data += TimeTagArgument(self.timeTag).toBinary()
        for msg in self.elements:
            binary = msg.toBinary()
            data += osc.IntArgument(len(binary)).toBinary()
            data += binary
        return data
    
    @staticmethod
    def fromBinary(data):
        """
        Creates a L{Bundle} object from binary data that is passed to it.

        This static method is a factory for L{Bundle} objects.

        @param data: String of bytes formatted following the OSC protocol.
        @return: Two-item tuple with L{Bundle} as the first item, and the
        leftover binary data, as a L{str}. That leftover should be an empty string.
        """
        bundleStart, data = osc._stringFromBinary(data)
        if bundleStart != "#bundle":
            raise osc.OscError("Error parsing bundle string")
        saved_data = data[:]
        bundle = Bundle()
        try:
            bundle.timeTag, data = TimeTagArgument.fromBinary(data)
            while data:
                size, data = osc.IntArgument.fromBinary(data)
                size = size.value
                if len(data) < size:
                    raise osc.OscError("Unexpected end of bundle: need %d bytes of data" % size)
                payload = data[:size]
                bundle.elements.append(_elementFromBinary(payload))
                data = data[size:]
            return bundle, ""
        except osc.OscError:
            data = saved_data
            bundle.timeTag, data = osc.TimeTagArgument.fromBinary(data)
            while data:
                size, data = osc.IntArgument.fromBinary(data)
                size = size.value
                if len(data) < size:
                    raise osc.OscError("Unexpected end of bundle: need %d bytes of data" % size)
                payload = data[:size]
                bundle.elements.append(_elementFromBinary(payload))
                data = data[size:]
            return bundle, ""
    
class TimeTagArgument(osc.Argument):
    typeTag = "t"

    def __init__(self, value=True):
        osc.Argument.__init__(self, value)

    def toBinary(self):
        if self.value is True:
            return struct.pack('>qq', 0, 1)
        fr, sec = math.modf(self.value)
        return struct.pack('>qq', long(sec), long(fr * 1e9))
        
    @staticmethod
    def fromBinary(data):
        binary = data[0:16]
        if len(binary) != 16:
            raise osc.OscError("Too few bytes left to get a timetag from %s." % (data))
        leftover = data[16:]

        if binary == '\0\0\0\0\0\0\0\1':
            # immediately
            time = True
        else:
            high, low = struct.unpack(">qq", data[0:16])
            time = float(int(high) + low / float(1e9))
        return TimeTagArgument(time), leftover

def _elementFromBinary(data):
    if data[0] == "/":
        element, data = osc.Message.fromBinary(data)
    elif data[0] == "#":
        element, data = Bundle.fromBinary(data)
    else:
        raise osc.OscError("Error parsing OSC data: " + data)
    return element

def get_ui_module(name):
    if name == 'kivy':
        from kivy.clock import Clock
        return Clock
    elif name == 'gtk':
        return None
    t = imp.find_module(name)
    module = imp.load_module(name, *t)
    return module

## TODO: make this use the threadbases.BaseThread class
class OSCDispatchThread(threading.Thread):
    _ui_mode_dispatch_methods = {'gtk':'gtk_do_dispatch', 
                                 'kivy':'kivy_do_dispatch'}
    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.running = threading.Event()
        self.ready_to_dispatch = threading.Event()
        self.bundles = {}
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
        
    def add_bundle(self, bundle, client):
        tt = bundle.timeTag
        if tt is not None:
            dt = timetag_to_datetime(timetag_obj=tt)
        else:
            dt = datetime.datetime.now()
        self.bundles[dt] = (bundle, client)
        self.ready_to_dispatch.set()
        
    def get_next_datetime(self):
        if len(self.bundles):
            keys = self.bundles.keys()
            keys.sort()
            return keys[0]
        return False
        
    def run(self):
        self.running.set()
        while self.running.isSet():
            self.ready_to_dispatch.wait()
            if not self.running.isSet():
                return
            dt = self.get_next_datetime()
            if dt is False:
                self.ready_to_dispatch.clear()
            else:
                now = datetime.datetime.now()
                offset = self.osc_tree.get_epoch_offset_cb()
                now = now + offset
                if dt <= now:
                    bundle, client = self.bundles[dt]
                    del self.bundles[dt]
                    messages = bundle.getMessages()
                    try:
                        self.do_dispatch(messages, client)
                    except:
                        pass
                else:
                    self.ready_to_dispatch.clear()
                    timeout = seconds_from_timedelta(dt - now)
                    self.ready_to_dispatch.wait(timeout)
                    self.ready_to_dispatch.set()
                    
    def _do_dispatch(self, messages, client):
        for m in messages:
            self.osc_tree.dispatch(m, client)
            
    def gtk_do_dispatch(self, messages, client):
        #self.ui_module.gdk.threads_enter()
        self._do_dispatch(messages, client)
        #self.ui_module.gdk.threads_leave()
                
    def kivy_do_dispatch(self, messages, client):
        obj = Messenger(messages=messages, client=client, callback=self._on_kivy_msg_cb)
        self.kivy_messengers.add(obj)
        self.ui_module.schedule_once(obj.send, 0)
        
    def _on_kivy_msg_cb(self, messenger):
        self._do_dispatch(messenger.messages, messenger.client)
        self.kivy_messengers.discard(messenger)

    def stop(self, **kwargs):
        blocking = kwargs.get('blocking')
        self.running.clear()
        self.ready_to_dispatch.set()
        if blocking and self.isAlive():
            self.join()

class Messenger(object):
    __slots__ = ('messages', 'client', 'callback', '__weakref__')
    def __init__(self, **kwargs):
        for key, val in kwargs.iteritems():
            setattr(self, key, val)
    def send(self, *args):
        self.callback(self)
