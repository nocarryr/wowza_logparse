from Bases import OSCBaseObject, ChildGroup

class MidiOSCRoot(OSCBaseObject):
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', 'MIDI')
        kwargs.setdefault('osc_address', self.name)
        super(MidiOSCRoot, self).__init__(**kwargs)
        self.register_signal('event')
        self.ioTypes = kwargs.get('ioTypes', ['in', 'out'])
        self.ioNodes = {}
        for key in self.ioTypes:
            n = IONode(name=key, osc_parent_node=self.osc_node)
            n.bind(event=self.on_child_event)
            self.ioNodes[key] = n
    def unlink(self):
        for n in self.ioNodes.itervalues():
            n.unlink()
        super(MidiOSCRoot, self).unlink()
    def trigger_event(self, **kwargs):
        ioType = kwargs.get('ioType')
        n = self.ioNodes.get(ioType)
        if not n:
            return
        n.trigger_event(**kwargs)
    def on_child_event(self, **kwargs):
        kwargs.setdefault('device_name', self.name)
        self.emit('event', **kwargs)
        
class IONode(OSCBaseObject):
    def __init__(self, **kwargs):
        self.name = kwargs.get('name')
        kwargs.setdefault('osc_address', self.name)
        super(IONode, self).__init__(**kwargs)
        self.register_signal('event')
        self.channels = {}
        for i in range(16):
            c = Channel(channel=i, osc_parent_node=self.osc_node)
            c.bind(event=self.on_child_event)
            self.channels[i] = c
    def unlink(self):
        for c in self.channels.itervalues():
            c.unlink()
        super(IONode, self).unlink()
    def trigger_event(self, **kwargs):
        channel = kwargs.get('channel')
        c = self.channels.get(channel)
        if not c:
            return
        c.trigger_event(**kwargs)
    def on_child_event(self, **kwargs):
        kwargs.setdefault('iotype', self.name)
        self.emit('event', **kwargs)
        
class Channel(OSCBaseObject):
    def __init__(self, **kwargs):
        self.channel = kwargs.get('channel')
        kwargs.setdefault('osc_address', str(self.channel + 1))
        super(Channel, self).__init__(**kwargs)
        self.register_signal('event')
        self.notes = ChildGroup(name='note', osc_parent_node=self.osc_node)
        self.controllers = ChildGroup(name='controller', osc_parent_node=self.osc_node)
        for i in range(128):
            n = self.notes.add_child(Note, note=i, channel=self, Index=i)
            n.bind(event=self.on_child_event)
            c = self.controllers.add_child(Controller, controller=i, channel=self)
            c.bind(event=self.on_child_event)
    def unlink(self):
        for n in self.notes.iteritems():
            n.unlink()
        for c in self.controllers.iteritems():
            c.unlink()
        super(Channel, self).unlink()
    def trigger_event(self, **kwargs):
        type = kwargs.get('type')
        attr = type + 's'
        if not hasattr(self, attr):
            return
        obj = getattr(self, attr).get(kwargs.get(type))
        if not obj:
            return
        obj.trigger_event(**kwargs)
    def on_child_event(self, **kwargs):
        kwargs.setdefault('channel', self.channel)
        self.emit('event', **kwargs)
        
class ChannelEvent(OSCBaseObject):
    def __init__(self, **kwargs):
        self.channel = kwargs.get('channel')
        kwargs.setdefault('osc_parent_node', self.channel.osc_node)
        super(ChannelEvent, self).__init__(**kwargs)
        self.register_signal('event')
    def emit_event(self, **kwargs):
        self.emit('event', **kwargs)
    

class Note(ChannelEvent):
    _Properties = {'velocity':dict(default=100, min=0, max=127, quiet=True), 
                   'state':dict(default=False, quiet=True)}
    def __init__(self, **kwargs):
        self.note = kwargs.get('note')
        self.id = self.note
        kwargs.setdefault('osc_address', str(self.note))
        super(Note, self).__init__(**kwargs)
        self.triggered_by_osc = False
        self.add_osc_handler(callbacks={'on':self._on_osc_on, 
                                        'off':self._on_osc_off})
        self.bind(state=self._on_state_set)
    def _on_osc_on(self, **kwargs):
        v = kwargs.get('values')[0]
        self.triggered_by_osc = True
        self.velocity = v
        self.state = True
        self.triggered_by_osc = False
        self.emit_event()
    def _on_osc_off(self, **kwargs):
        v = kwargs.get('values')[0]
        self.triggered_by_osc = True
        self.velocity = v
        self.state = False
        self.triggered_by_osc = False
        self.emit_event()
    def _on_state_set(self, **kwargs):
        if self.triggered_by_osc:
            return
        state = kwargs.get('value')
        if state:
            key = 'on'
        else:
            key = 'off'
        self.osc_node.send_message(address=key, value=self.velocity)
    def trigger_event(self, **kwargs):
        self.velocity = kwargs.get('velocity')
        self.state = kwargs.get('state')
    def emit_event(self, **kwargs):
        kwargs.update(dict(type='note', note=self.note, state=self.state, velocity=self.velocity))
        super(Note, self).emit_event(**kwargs)
        
class Controller(ChannelEvent):
    _Properties = {'value':dict(default=0, min=0, max=127, quiet=True)}
    def __init__(self, **kwargs):
        self.controller = kwargs.get('controller')
        self.id = self.controller
        kwargs.setdefault('osc_address', str(self.controller))
        super(Controller, self).__init__(**kwargs)
        self.add_osc_handler(Property='value')
        self.bind(value=self._on_value_set)
    def _on_value_set(self, **kwargs):
        if not self.osc_handlers['value'].Property_set_by_osc:
            return
        self.emit_event()
    def trigger_event(self, **kwargs):
        self.value = kwargs.get('value')
    def emit_event(self, **kwargs):
        kwargs.update(dict(type='controller', controller=self.controller, value=self.value))
        super(Controller, self).emit_event(**kwargs)
