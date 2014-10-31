from Bases import OSCBaseObject

class BaseWidget(OSCBaseObject):
    def __init__(self, **kwargs):
        self.link_state = False
        self.client = kwargs.get('client')
        self.control = kwargs.get('control')
        self.prototype = kwargs.get('prototype', False)
        if self.control:
            self.name = self.control.name
            self.id = self.name
            address = self.control.osc_cs
            kwargs.setdefault('osc_address', address.split('/')[-1:][0])
        else:
            self.name = kwargs.get('name')
            self.id = kwargs.get('name', setID(kwargs.get('id')))
        super(BaseWidget, self).__init__(**kwargs)
        self.register_signal('value_update')
        
        self.src_signal = None
        self.set_src_object(**kwargs)
        if self.src_object:
            print  self.name, 'srcobj:', self.src_object
        
    def set_visible(self, state):
        self.osc_node.send_message(address='visible', value=int(state))
        
    def set_color(self, color):
        self.osc_node.send_message(address='color', value=color)
        
    def send_value_to_osc(self, value, client=None):
        self.osc_node.send_message(root_address='TouchOSC', address='', value=value, client=self.client)
    
    def send_updates(self, **kwargs):
        pass
        
    def set_link_state(self, state):
        if state != self.link_state:
            if state:
                self.osc_node.addCallback(self.osc_address, self._handle_osc_message)
                if self.src_signal:
                    self.src_object.connect(self.src_signal, self.on_src_object_update)
                print self.name, 'linked to', self.src_object
            else:
                self.osc_node.removeCallback(self.osc_address, self._handle_osc_message)
                if self.src_signal:
                    self.src_object.disconnect(callback=self.on_src_object_update)
        self.link_state = state
        self.send_updates()
        
    def set_src_object(self, **kwargs):
        if self.link_state and self.src_signal:
            self.src_object.disconnect(callback=self.on_src_object_update)
        self.src_object = kwargs.get('src_object')
        self.src_attr = kwargs.get('src_attr')
        self.src_signal = kwargs.get('src_signal')
        if self.link_state and self.src_signal:
            id = self.src_object.connect(self.src_signal, self.on_src_object_update)
            print 'widget connect: ', self, id, self.src_object
        
    def on_src_object_update(self, **kwargs):
        pass
    
    def _handle_osc_message(self, message, hostaddr):
        self.on_osc_message(values=message.get_arguments())
        
    def on_osc_message(self, **kwargs):
        values = kwargs.get('values')
        if len(values) == 1:
            values = values[0]
        self.emit('value_update', widget=self, value=values)
    
class Label(BaseWidget):
    _types = ['labelv', 'labelh']
    def __init__(self, **kwargs):
        self._text = ''
        super(Label, self).__init__(**kwargs)
        label = kwargs.get('label')
        if self.src_object:
            self.set_text(getattr(self.src_object, self.src_attr))
        elif label is not None:
            self.set_text(label)
    def set_text(self, text):
        self._text = text
        self.send_value_to_osc(text)
    def send_updates(self, **kwargs):
        client = kwargs.get('client')
        self.send_value_to_osc(self._text, client)
    def on_src_object_update(self, **kwargs):
        self.set_text(getattr(self.src_object, self.src_attr))
    
class Button(BaseWidget):
    _types = ['push']
    def __init__(self, **kwargs):
        super(Button, self).__init__(**kwargs)
        self.register_signal('press', 'release')
        
    def on_osc_message(self, **kwargs):
        state = kwargs.get('values')[0]
        if state:
            self.emit('press', widget=self)
            if self.src_object:
                setattr(self.src_object, self.src_attr, True)
        else:
            self.emit('release', widget=self)
        super(Button, self).on_osc_message(**kwargs)
        
class Toggle(BaseWidget):
    _types = ['toggle']
    def __init__(self, **kwargs):
        self._state = False
        super(Toggle, self).__init__(**kwargs)
        self.register_signal('state_changed')
        self.state = False
        
    @property
    def state(self):
        return self._state
    @state.setter
    def state(self, value):
        self.send_value_to_osc(int(value))
        
    def send_updates(self, **kwargs):
        self.send_value_to_osc(self.state, kwargs.get('client'))
        
    def on_src_object_update(self, **kwargs):
        value = getattr(self.src_object, self.src_attr)
        if value != self.state:
            self.state = value
            
    def on_osc_message(self, **kwargs):
        state = kwargs.get('values')[0] == 1
        if state != self.state:
            self._state = state
            if self.src_object:
                setattr(self.src_object, self.src_attr, state)
            self.emit('state_changed', widget=self, state=state)
        super(Toggle, self).on_osc_message(**kwargs)
        
class Fader(BaseWidget):
    _types = ['faderh', 'faderv']
    def __init__(self, **kwargs):
        if not hasattr(self, '_value'):
            self._value = 0.
        super(Fader, self).__init__(**kwargs)
        self.orientation = kwargs.get('orientation', 'horizontal')
#        if self.control:
#            self.orientation = self.control.orientation
#        else:
#            self.orientation = kwargs.get('orientation', 'horizontal')
        
    @property
    def value(self):
        return self._value
    @value.setter
    def value(self, value):
        self.send_value_to_osc(value)
        
    def send_updates(self, **kwargs):
        self.send_value_to_osc(self.value, kwargs.get('client'))
        
    def on_src_object_update(self, **kwargs):
        value = getattr(self.src_object, self.src_attr)
        if value != self.value:
            self.value = value
            
    def on_osc_message(self, **kwargs):
        value = int(kwargs.get('values')[0])
        if value != self.value:
            self._value = value
            if self.src_object:
                setattr(self.src_object, self.src_attr, value)
            super(Fader, self).on_osc_message(**kwargs)
        
class xyPad(Fader):
    _types = ['xy']
    def __init__(self, **kwargs):
        self._value = [0., 0.]
        super(xyPad, self).__init__(**kwargs)
        if self.control:
            self.orientation = self.control.Layout.orientation
        print self, 'orientation=', self.orientation
    def send_value_to_osc(self, value, client=None):
        if self.orientation == 'horizontal':
            value.reverse()
        super(xyPad, self).send_value_to_osc(value, client)
    def on_osc_message(self, **kwargs):
        #print 'before:', kwargs.get('values')
        #values = [int(v) for v in kwargs.get('values')]
        #print 'after:', values
        values = kwargs.get('values')
        if self.orientation == 'horizontal':
            values.reverse()
        if values != self.value:
            self._value = values
            if self.src_object:
                setattr(self.src_object, self.src_attr, values)
            #kwargs['values'] = values
            #super(xyPad, self).on_osc_message(**kwargs)

widget_classes = {}
for cls in [Label, Button, Toggle, Fader, xyPad]:
    widget_classes.update({cls.__name__:cls})
    
def find_widget_type(control):
    for cls in widget_classes.itervalues():
        if control.type in cls._types:
            return cls
    return False
