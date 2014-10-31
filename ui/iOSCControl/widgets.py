import threading

from Bases import OSCBaseObject
from Bases.Properties import PropertyConnector

def make_css(color_list):
    if type(color_list) == str:
        return color_list
    return '#%s' % (''.join(['%02x' % (i) for i in color_list]))

class BaseWidget(OSCBaseObject, PropertyConnector):
    _widget_type = None
    osc_value_prop = None
    _interface_properties = ['name', 'type', 'min', 'max', 'oninit']
    _attribute_defaults = {'min':0, 'max':1}
    def __init__(self, **kwargs):
        self.interface_properties = set()
        cls = self.__class__
        while cls != BaseWidget.__bases__[0]:
            if hasattr(cls, '_interface_properties'):
                self.interface_properties |= set(cls._interface_properties)
            cls = cls.__bases__[0]
        self.link_state = False
        self.name = kwargs.get('name')
        #self.id = kwargs.get('id', self.name)
        kwargs.setdefault('osc_address', self.name)
        self.parent_widget = kwargs.get('parent_widget')
        if self.parent_widget is None:
            self.root_widget = self
        else:
            self.root_widget = self.parent_widget.root_widget
        super(BaseWidget, self).__init__(**kwargs)
        self.id = kwargs.get('id', '_'.join(self.osc_node.get_full_path().split()))
        self.register_signal('interface_update', 'add_widget', 'remove_widget')
        self.use_int_value = kwargs.get('use_int_value', False)
        self.client = kwargs.get('client')
        self.osc_root_address = kwargs.get('osc_root_address', 'iOSCControl')
        #self.osc_client_address = kwargs.get('osc_client_address')
        self.type = self.__class__._widget_type
        self.min = kwargs.get('min')
        self.max = kwargs.get('max')
        for key in ['oninit', 'onvaluechange']:
            if key in kwargs:
                setattr(self, key, kwargs[key])
        
        cls = self.__class__
        while cls != OSCBaseObject:
            defaults = getattr(cls, '_attribute_defaults', None)
            if defaults:
                for key, val in defaults.iteritems():
                    if not hasattr(self, key) and kwargs.get(key) != val:
                        setattr(self, key, kwargs.get(key))
            cls = cls.__bases__[0]
        
        if self.osc_value_prop is not None:
            self.add_osc_handler(Property=self.osc_value_prop, 
                                 request_initial_value=False, 
                                 #send_root_address=self.client.osc_name, 
                                 send_client=self.client.name)
        
        self.child_widgets = {}
        self.Property = kwargs.get('Property')
            
    def unlink(self):
        self.Property = None
        super(BaseWidget, self).unlink()
        
        
#    def set_src_object(self, **kwargs):
#        if self.link_state and self.src_signal:
#            self.src_object.unbind(self.on_src_object_update)
#        self.src_object = kwargs.get('src_object')
#        self.src_attr = kwargs.get('src_attr')
#        self.src_signal = kwargs.get('src_signal')
#        if self.link_state and self.src_signal:
#            min = getattr(self.src_object, 'value_min', None)
#            max = getattr(self.src_object, 'value_max', None)
#            if min is not None and max is not None:
#                if min != self.min or max != self.max:
#                    self.min = min
#                    self.max = max
#                    self._interface_update('setRange', [self.min, self.max])
#            self.on_src_object_update()
#            id = self.src_object.bind(**{self.src_signal:self.on_src_object_update})
#            print 'widget connect: ', self.name, id, self.src_object
        
    def add_widget(self, cls, **kwargs):
        for key in ['client', 'osc_root_address']:
            kwargs.setdefault(key, getattr(self, key))
        kwargs.setdefault('osc_parent_node', self.osc_node)
        kwargs.setdefault('ParentEmissionThread', self.ParentEmissionThread)
        kwargs['parent_widget'] = self
#        prebind = kwargs.get('prebind', {})
#        prebind.update(dict(interface_update=self.on_child_interface_update, 
#                            add_widget=self.on_child_add_widget, 
#                            remove_widget=self.on_child_remove_widget))
#        kwargs['prebind'] = prebind
        widget = cls(**kwargs)
        widget.bind(interface_update=self.on_child_interface_update, 
                    add_widget=self.on_child_add_widget, 
                    remove_widget=self.on_child_remove_widget)
        self.child_widgets.update({widget.name:widget})
        if not len(self._emitters['add_widget'].weakrefs):
            self.root_widget.emit('add_widget', parent=self, widget=widget)
        else:
            self.emit('add_widget', parent=self, widget=widget)
        return widget
        
    def on_child_add_widget(self, **kwargs):
        self.emit('add_widget', **kwargs)
        
    def remove(self):
        for w in self.child_widgets.values()[:]:
            w.remove()
        #self._interface_update('removeWidget', [])
        if not len(self._emitters['remove_widget'].weakrefs):
            self.root_widget.emit('remove_widget', widget=self)
        else:
            self.emit('remove_widget', widget=self)
        self.unlink()
        
    def refresh_interface(self):
        for w in self.child_widgets.itervalues():
            w.refresh_interface()
        
    def on_child_remove_widget(self, **kwargs):
        widget = kwargs.get('widget')
        self.emit('remove_widget', **kwargs)
        if self.child_widgets.get(widget.name) == widget:
            #widget.unbind(self)
            del self.child_widgets[widget.name]
        
#    def send_value_to_osc(self, value, address='set-value'):
#        if self.osc_client_address is None:
#            self.osc_client_address = 'DWT_iPad'
#        self.osc_node.send_message(root_address=self.osc_client_address, address=address, value=value)
    
    def on_osc_set_value(self, **kwargs):
        pass
        
    def on_src_object_update(self, **kwargs):
        pass
        
    def _interface_update(self, update_type, values, add_widget_id=True):
        sig_kwargs = dict(address=update_type, value=values, widget=self)
        sig_kwargs['add_widget_id'] = add_widget_id
        if True:#not len(self._emitters['interface_update'].weakrefs):
            self.root_widget.emit('interface_update', **sig_kwargs)
        else:
            self.emit('interface_update', **sig_kwargs)
        
    def on_child_interface_update(self, **kwargs):
        self.emit('interface_update', **kwargs)
        
    def build_interface_dict(self, **kwargs):
        #root = kwargs.get('root_address')
        traverse_tree = kwargs.get('traverse_tree', True)
        root = self.client.osc_name
        d = {}
        for key in self.interface_properties:
            val = getattr(self, key, None)
            if key == 'name':
                val = self.id
            if hasattr(self, key) and type(val) != set:
                d.update({key:val})
        if self._widget_type in ['Label']:
            for key in ['min', 'max']:
                if key in d:
                    del d[key]
            
        path = self.osc_node.get_full_path()
#        if root:
#            path[0] = root
#        path[1] = self.osc_root_address
        if self.osc_value_prop is not None:
            path = path.append(self.osc_value_prop)
        #s = '/' + '/'.join(path) + '/set-value'
        path = path.append('set-value')
        d.update({'address':path})
        if 'osc_address' in d:
            del d['osc_address']
        l = [d]
        if traverse_tree:
            for w in self.child_widgets.itervalues():
                wl = w.build_interface_dict(**kwargs)
                if wl:
                    l += wl
        return l
        
class GraphicsWidget(BaseWidget):
    _interface_properties = ['bounds', 'colors', 'ontouchstart', 'ontouchmove', 'ontouchend', 'requiresTouchDown']#, 'backgroundColor', 'foregroundColor', 'strokeColor']
    _color_keys = ['backgroundColor', 'foregroundColor', 'strokeColor']
    def __init__(self, **kwargs):
        super(GraphicsWidget, self).__init__(**kwargs)
        if 'bounds' in kwargs:
            self.bounds = kwargs.get('bounds')
        else:
            self.x = kwargs.get('x', 0)
            self.y = kwargs.get('y', 0)
            self.width = kwargs.get('width', .25)
            self.height = kwargs.get('height', .25)
        self.backgroundColor = kwargs.get('backgroundColor', [32]*4)
        self.foregroundColor = kwargs.get('foregroundColor', [128]*3)
        self.strokeColor = kwargs.get('strokeColor', [255]*3)
        for s in ['start', 'move', 'end']:
            key = 'ontouch' + s
            if key in kwargs:
                setattr(self, key, kwargs[key])
#        if not isinstance(self, Label):
#            self.label_widget = self.add_widget(Label, name='label', 
#                                                       bounds=self.bounds, 
#                                                       foregroundColor=[255]*3, 
#                                                       value=kwargs.get('label', ''))
#                                                       #osc_parent_node=self.osc_node, 
#                                                       #osc_address='label')
#            
#            self.bind(label=self.on_label_set)
#            #if 'label' in kwargs:
#            #    self.label = kwargs.get('label')
            
    @property
    def backgroundColor(self):
        return make_css(self._backgroundColor)
    @backgroundColor.setter
    def backgroundColor(self, value):
        self._backgroundColor = value
    @property
    def foregroundColor(self):
        return make_css(self._foregroundColor)
    @foregroundColor.setter
    def foregroundColor(self, value):
        self._foregroundColor = value
    @property
    def strokeColor(self):
        return make_css(self._strokeColor)
    @strokeColor.setter
    def strokeColor(self, value):
        self._strokeColor = value
    @property
    def bounds(self):
        return [getattr(self, key) for key in ['x', 'y', 'width', 'height']]
    @bounds.setter
    def bounds(self, value):
        for x, key in enumerate(['x', 'y', 'width', 'height']):
            setattr(self, key, value[x])
    @property
    def colors(self):
        return [getattr(self, key) for key in self._color_keys]
    @colors.setter
    def colors(self, value):
        if len(value) == len(self._color_keys):
            for key, val in zip(self._color_keys, value):
                setattr(self, key, val)
            
        
class Button(GraphicsWidget):
    _widget_type = 'Button'
    _interface_properties = ['mode', 'startingValue', 'label']
    state_colors = {False:[[64, 64, 64, 8], [64]*3, [190]*3], 
                    True: [[32, 32, 64, 64], [100, 100, 140], [255]*3]}
    color_keys = ['backgroundColor', 'foregroundColor', 'strokeColor']
    label_colors = [[0]*4, [255]*3, [255]*3]
    _Properties = {'touch_state':dict(default=False, quiet=True), 
                   'widget_value':dict(default=-1., min=-1., max=1., quiet=True), 
                   'label':dict(default='')}
    osc_value_prop = 'widget_value'
    #_attribute_defaults = {'mode':'toggle'}
    def __init__(self, **kwargs):
        kwargs.update({'min':-1., 'max':1.})#, 'requiresTouchDown':False})
        
        for i, key in enumerate(self.color_keys):
            kwargs[key] = self.state_colors[False][i]
            
        self.mode = kwargs.get('mode', 'contact')
        self.startingValue = kwargs.get('min')
        super(Button, self).__init__(**kwargs)
        self.register_signal('clicked')
        self.label = kwargs.get('label', '')
        #self.dummy_label_widget = self.add_widget(DummyButtonLabel, parent=self)
        
        self.bind(touch_state=self._on_touch_state_set, 
                  widget_value=self._on_widget_value_set, 
                  label=self.on_label_set)
    
    def _on_touch_state_set(self, **kwargs):
        state = kwargs.get('value')
        self.update_state_color()
        self.set_Property_value(state)
        self.widget_value = getattr(self, {False:'min', True:'max'}[state])
        #print self.id, ' widgetvalue: ', self.widget_value
        
    def _on_widget_value_set(self, **kwargs):
        prop = kwargs.get('Property')
        value = kwargs.get('value')
        self.touch_state = value > 0
        if value > prop.min:
            self.emit('clicked', obj=self)
        #if value > prop.min:
        #    self.widget_value = prop.min
            
            
        
    def on_Property_value_changed(self, **kwargs):
        state = kwargs.get('value')
        self.touch_state = state
        
        
    def update_state_color(self):
        for i, key in enumerate(self.color_keys):
            setattr(self, key, self.state_colors[self.touch_state][i])
        colors = [getattr(self, key) for key in self.color_keys]
        self._interface_update('setColors', colors)
        self._update_label(text=False, colors=True)
        
    def on_label_set(self, **kwargs):
        value = kwargs.get('value')
        #self.dummy_label_widget.value = value
        self._update_label()
        
    def _update_label(self, text=True, colors=False):
        if text:
            self._interface_update('runScript', "%sLabel.setValue('%s')" % (self.id, self.label), add_widget_id=False)
        if not colors:
            return
        l = [make_css(color) for color in self.label_colors]
        self._interface_update('setColors', ['%sLabel' % (self.id)] + l, add_widget_id=False)
        
    def refresh_interface(self):
        #self.dummy_label_widget.refresh_interface()
        self._update_label()#colors=True)
        super(Button, self).refresh_interface()
        
    def remove(self):
        #self.dummy_label_widget.remove()
        self._interface_update('removeWidget', '%sLabel' % (self.id), add_widget_id=False)
        super(Button, self).remove()
        
        
class MultiButton(GraphicsWidget):
    _widget_type = 'MultiButton'
    _interface_properties = ['rows', 'columns', 'shouldLabel']
    #_Properties = {'button_pressed':dict(type=int)}
    def __init__(self, **kwargs):
        self.rows = kwargs.get('rows', 4)
        self.columns = kwargs.get('columns', 4)
        self.shouldLabel = True
        super(MultiButton, self).__init__(**kwargs)
        self.register_signal('button_pressed')
        self.add_osc_handler(callbacks={'set-value/*':self.on_osc_multi_set_value})
        
    def on_osc_multi_set_value(self, **kwargs):
        method = kwargs.get('method')
        if method.isdigit():
            self.emit('button_pressed', index=int(method))
        
        
class DummyButton(Button):
    def __init__(self, **kwargs):
        self.parent_widget = kwargs.get('parent')
        self.index = kwargs.get('index')
        
        
class Toggle(Button):
    #_widget_type = 'Button'
    def __init__(self, **kwargs):
        #kwargs['mode'] = 'toggle'
        super(Toggle, self).__init__(**kwargs)
    def _on_widget_value_set(self, **kwargs):
        if kwargs.get('value') > kwargs.get('Property').min:
            self.touch_state = not self.touch_state
        super(Toggle, self)._on_widget_value_set(**kwargs)
        

class Slider(GraphicsWidget):
    _widget_type = 'Slider'
    _interface_properties = ['isVertical', 'isXFader']
    _attribute_defaults = {'isVertical':False, 'isXFader':False}
    _Properties = {'widget_value':dict(default=0., min=0., max=1., quiet=True)}
    osc_value_prop = 'widget_value'
    def __init__(self, **kwargs):
        self.throttle_timer = None
        self.throttle_wait = threading.Event()
        self.throttle_timeout = .1
        self.throttle_last_msg = None
        #self._value = 0.
        self.label_widget = None
        self.value_label = None
        self.widget_value_resetting = False
        self.update_label_with_value = kwargs.get('update_label_with_value', True)
        kwargs.setdefault('foregroundColor', [0, 255, 0])
        kwargs.setdefault('backgroundColor', [128, 128, 128, 255])
        kwargs.setdefault('min', 0.)
        kwargs.setdefault('max', 1.)
        super(Slider, self).__init__(**kwargs)
        #self.ontouchstart = 'window.slowSliderCount = 0; PhoneGap.exec(\'OSCManager.send\', this.address, \'f\', this.value)'
        #self.ontouchmove = 'window.slowSliderCount++; if(window.slowSliderCount == 10) { window.slowSliderCount = 0; PhoneGap.exec(\'OSCManager.send\', this.address, \'f\', this.value)'
        
        self.add_label_widgets(**kwargs)
        #self.register_signal('value_update')
        self.bind(widget_value=self._on_widget_value_set)
        
    def add_label_widgets(self, **kwargs):
        pass
        
    def _on_widget_value_set(self, **kwargs):
        value = kwargs.get('value')
        if self.Property is None:
            return
        if self.widget_value_resetting:
            return
        self.Property.normalized_and_offset = value
        
    def attach_Property(self, prop):
        super(Slider, self).attach_Property(prop)
        if self.Property is not None:
            self.on_Property_value_changed(Property=self.Property)
            
    def unlink_Property(self, prop):
        super(Slider, self).unlink_Property(prop)
        self.widget_value_resetting = True
        self.Properties['widget_value'].normalized_and_offset = 0.
        self.widget_value_resetting = False
        
    def on_Property_value_changed(self, **kwargs):
        prop = kwargs.get('Property')
        value = kwargs.get('value')
        self.Properties['widget_value'].normalized_and_offset = prop.normalized_and_offset
        if self.update_label_with_value and self.value_label and type(prop.value) in [int, float]:
            self.value_label.value = '%.2f' % (prop.value)
        
#    @property
#    def value(self):
#        return self._value
#    @value.setter
#    def value(self, value):
#        if self.use_int_value:
#            value = int(value)
#        if value != self.value:
#            self._value = value
#            self.send_value_to_osc(value)
#            if self.update_label_with_value and self.value_label:
#                self.value_label.value = '%.2f' % (value)
#            self.emit('value_update', widget=self, value=value)
        
    @property
    def label(self):
        if not self.label_widget:
            return ''
        return self.label_widget.value
    @label.setter
    def label(self, value):
        if self.label_widget:
            self.label_widget.value = value
        
#    def on_osc_set_value(self, **kwargs):
#        #if self.throttle_wait.isSet():
#        #    self.throttle_last_msg = kwargs.copy()
#        #    return
#        self.process_osc_msg(**kwargs)
#        #self.throttle_wait.set()
#        #self.throttle_timer = threading.Timer(self.throttle_timeout, self.on_throttle_timer)
#        #self.throttle_timer.start()
#        
#    def on_throttle_timer(self):
#        print self, 'timer end', self.throttle_last_msg
#        if self.throttle_last_msg is not None:
#            self.process_osc_msg(**self.throttle_last_msg)
#        self.throttle_last_msg = None
#        self.throttle_wait.clear()
#            
#    def process_osc_msg(self, **kwargs):
#        value = kwargs.get('values')[0]
#        if self.use_int_value:
#            value = int(value)
#        if value != self.value:
#            self._value = value
#            if self.src_object:
#                setattr(self.src_object, self.src_attr, value)
#            if self.update_label_with_value and self.value_label:
#                self.value_label.value = '%.2f' % (value)
#            self.emit('value_update', widget=self, value=value)
#        
#    def on_src_object_update(self, **kwargs):
#        value = getattr(self.src_object, self.src_attr)
#        if value != self.value:
#            self.value = value
        
class VSlider(Slider):
    _widget_type = 'Slider'
    def __init__(self, **kwargs):
        self.isVertical = True
        super(VSlider, self).__init__(**kwargs)
    def add_label_widgets(self, **kwargs):
        original_bounds = self.bounds[:]
        label_h = self.height * .05
        lkwargs = dict(x=self.x, width=self.width, height=label_h)
        add_label = kwargs.get('add_label', True)
        add_value_label = kwargs.get('add_value_label', True)
        for flag in [add_label, add_value_label]:
            if not flag:
                continue
            self.height = self.height - label_h
        if add_label:
            y = self.y + self.height
            lkwargs.update(dict(name=self.name+'Label', y=y, value=kwargs.get('label', self.name)))
            self.label_widget = self.add_widget(Label, **lkwargs)
        if add_value_label:
            y = self.y + self.height
            if add_label:
                y += label_h
            lkwargs.update(dict(name=self.name+'ValueLabel', y=y, value=str(self.widget_value)))
            self.value_label = self.add_widget(Label, **lkwargs)
        
class HSlider(Slider):
    _widget_type = 'Slider'
    def __init__(self, **kwargs):
        #kwargs.update({'add_label':False, 'add_value_label':False})
        super(HSlider, self).__init__(**kwargs)
    def add_label_widgets(self, **kwargs):
        original_bounds = self.bounds[:]
        label_w = self.width * .1
        label_h = self.height
        
        add_label = kwargs.get('add_label', True)
        add_value_label = kwargs.get('add_value_label', True)
        l = [add_label, add_value_label]
        if True in l:
            self.width = self.width - label_w
        if False not in l:
            label_h = label_h / 2
        lkwargs = dict(height=label_h, width=label_w, x=self.x + self.width)
        if add_label:
            #x = self.x + self.width
            lkwargs.update(dict(name=self.name+'Label', y=self.y, value=kwargs.get('label', self.name)))
            self.label_widget = self.add_widget(Label, **lkwargs)
        if add_value_label:
            #x = self.x + self.width
            y = self.y
            if add_label:
                y += label_h
            lkwargs.update(dict(name=self.name+'ValueLabel', y=y, value=str(self.widget_value)))
            self.value_label = self.add_widget(Label, **lkwargs)
        
class MultiSlider(Slider):
    _widget_type = 'MultiSlider'
    _interface_properties = 'numberOfSliders'
    def __init__(self, **kwargs):
        kwargs.update(dict(zip(['add_label', 'add_value_label', 'update_label_with_value'], [False]*3)))
        super(MultiSlider, self).__init__(**kwargs)
        self.numberOfSliders = kwargs.get('numberOfSliders', 4)
    def set_child_colors(self, d):
        for key, val in d.iteritems():
            if type(key) == int:
                css = ', '.join([make_css(l).join(["'", "'"]) for l in val])
                s = "%s.children[%s].setColors([%s])" % (self.id, key, css)
                self._interface_update('runScript', s, add_widget_id=False)

class Label(GraphicsWidget):
    _widget_type = 'Label'
    _interface_properties = ['verticalCenter', 'align', 'value']
    #_Properties = {'widget_value':dict(default='', quiet=True)}
    #osc_value_prop = 'widget_value'
    _Properties = {'value':dict(default=' ', quiet=True)}
    def __init__(self, **kwargs):
        #self._value = ''
        #self._backgroundColor = [0, 0, 0, 0]
        kwargs.setdefault('foregroundColor', [255]*3)
        kwargs.setdefault('strokeColor', [0, 255, 0])
        super(Label, self).__init__(**kwargs)
        self.value = kwargs.get('value', ' ')
        #self.register_signal('value_update')
        self.verticalCenter = kwargs.get('verticalCenter', True)
        self.align = kwargs.get('align', 'center')
        #self._value = kwargs.get('value', '')
        #self.strokeColor = [0, 255, 0]
        self.bind(value=self._on_value_set)
        
    def _on_value_set(self, **kwargs):
        value = kwargs.get('value')
        self.set_label(value)
        
    def on_Property_value_set(self, **kwargs):
        value = kwargs.get('value')
        self.value = value
        
    def set_label(self, text):
        self._interface_update('runScript', "%s.setValue('%s')" % (self.id, text), add_widget_id=False)
            
class xyPad(GraphicsWidget):
    _widget_type = 'MultiTouchXY'
    _interface_properties = ['isMomentary', 'maxTouches']
    _Properties = {'widget_value':dict(default=[.5, .5], min=[0., 0.], max=[1., 1.], quiet=True)}
    osc_value_prop = 'widget_value'
    def __init__(self, **kwargs):
        #self._pos = [0, 0]
        self.widget_set_by_prop = False
        kwargs.update({'min':0., 'max':1.})
        super(xyPad, self).__init__(**kwargs)
        #self.register_signal('value_update')
        self.isMomentary = kwargs.get('isMomentary', False)
        self.xyInverted = kwargs.get('xyInverted', (False, True))
        l = []
        #l.append("children[0].style.width = (window.%(id)s.width / 8) +'px'")
        #l.append("children[0].style.height = (window.%(id)s.width / 8) +'px'")
        l.append("changeValue(window.%(id)s.children[0], %(x)s, %(y)s)")
        #l.append("removeTouch(1)")
        #l.append("addTouch(%(val)s, %(val)s, 0)")
        l = ['window.%(id)s.' + s for s in l]
        self.oninit = ';'.join(l) % {'id':self.id, 'val':self.widget_value[0], 'size':self.width / 16, 
                                     'x':self.x + (self.width / 2), 'y':self.y}
        #self.oninit = "window.%(id)s.setValue(%(val)s, %(val)s, 1)" % {'id':self.id, 'val':self.widget_value[0]}
        self.touch_active = False
#        path = self.osc_node.get_full_path()
#        path[0] = self.client.osc_name
#        path[1] = self.osc_root_address
#        #path.append('touchstart')
#        s = '/' + '/'.join(path)
        #self.ontouchstart = "oscManager.sendOSC('%s')" % (s + '/touchstart')
        #self.ontouchend = "oscManager.sendOSC('%s')" % (s + '/touchend')
        self.maxTouches = 1
        #self.scale_factor = kwargs.get('scale_factor', 1)
        self.add_osc_handler(callbacks={'touchstart':self.on_touch_start, 'touchend':self.on_touch_end})
        self.bind(widget_value=self._on_widget_value_set)
        
    def _on_widget_value_set(self, **kwargs):
        if self.widget_set_by_prop:
            return
        prop = kwargs.get('Property')
        value = prop.normalized_and_offset
        #print 'xy widget: ', value
        value = self._invert_xy(value)
        #print 'inverted: ', value
        
        if isinstance(self.get_Property_value(), list):
            self.Property.normalized_and_offset = value
        elif isinstance(self.get_Property_value(), dict):
            d = dict(zip(self.prop_keys, value))
            self.Property.normalized_and_offset = d
        
            
    def on_Property_value_changed(self, **kwargs):
        ## TODO: make this not suck
        #return
        if self.touch_active:
            return
        self.widget_set_by_prop = True
        prop = kwargs.get('Property')
        value = kwargs.get('value')
        osc_prop = self.Properties['widget_value']
        if isinstance(value, list):
            osc_prop.normalized_and_offset = prop.normalized_and_offset
        elif isinstance(value, dict):
            nvalue = prop.normalized_and_offset
            l = [nvalue[key] for key in self.prop_keys]
            #print 'propval=%s, nvalue=%s, l=%s, proprange=%s' % (value, nvalue, l, prop.range)
            osc_prop.normalized_and_offset = l
        #print osc_prop.value
        x, y = self._invert_xy(osc_prop.value)
        self._interface_update('runScript', "%s.setValue(1,%s,%s)" % (self.id, x, y), add_widget_id=False)
        self.widget_set_by_prop = False
            
    def attach_Property(self, prop):
        super(xyPad, self).attach_Property(prop)
        if isinstance(prop.value, dict):
            if 'x' in prop.value.keys():
                self.prop_keys = ['x', 'y']
            elif 'pan' in prop.value.keys():
                self.prop_keys = ['pan', 'tilt']
            else:
                self.prop_keys = None
        #self.on_Property_value_changed(Property=prop, value=prop.value)
            
    def on_touch_start(self, **kwargs):
        self.touch_active = True
        
    def on_touch_end(self, **kwargs):
        self.touch_active = False
        
    def _invert_xy(self, xy):
        xy = xy[:]
        for i in range(2):
            if self.xyInverted[i]:
                xy[i] = (xy[i] * -1.) + self.max + self.min
        return xy
        
rgb_keys = ['red', 'green', 'blue']
rgb_props = dict(zip(rgb_keys, [dict(default=0., min=0., max=1., quiet=True)]*3))

class ColorSlider(Label):
    rgb_keys = ['red', 'green', 'blue']
    _Properties = rgb_props
    def __init__(self, **kwargs):
        super(ColorSlider, self).__init__(**kwargs)
        self.rgb_set_by_prop = False
        self.sliders = {}
        h = self.height / 3.
        sl_kwargs = dict(x=self.x, width=self.width, height=h)
        for i, key in enumerate(self.rgb_keys):
            sl_kwargs['y'] = self.y + h * i
            sl_kwargs['name'] = key
            col = [0]*3
            col[i] = 255
            sl_kwargs['foregroundColor'] = col
            col = [0]*3
            col[i] = 96
            sl_kwargs['backgroundColor'] = col
            sl_kwargs['Property'] = (self, key)
            sl = self.add_widget(HSlider, **sl_kwargs)
            self.sliders[key] = sl
        self.bind(**dict(zip(self.rgb_keys, [self._on_rgb_set]*3)))
        
    def attach_Property(self, prop):
        super(ColorSlider, self).attach_Property(prop)
        #print 'attached prop: ', prop
        self.update_rgb_props(**prop.normalized_and_offset)
        
    def unlink_Property(self, prop):
        super(ColorSlider, self).unlink_Property(prop)
        self.update_rgb_props(**dict(zip(self.rgb_keys, [0.]*3)))
            
    def on_Property_value_changed(self, **kwargs):
        prop = kwargs.get('Property')
        value = kwargs.get('value')
        #print 'color prop change: ', value
        self.update_rgb_props(**prop.normalized_and_offset)
        
    def update_rgb_props(self, **kwargs):
        self.rgb_set_by_prop = True
        for key, val in kwargs.iteritems():
            setattr(self, key, val)
        self.rgb_set_by_prop = False
            
    def _on_rgb_set(self, **kwargs):
        if self.rgb_set_by_prop:
            return
        if self.Property is None:
            return
        prop = kwargs.get('Property')
        value = kwargs.get('value')
        #print '%s prop change: %s' % (prop.name, value)
        self.get_Property_value()[prop.name] = value
        self.Property.normalized_and_offset = {prop.name:value}
        #self.set_Property_value({prop.name:value})
        

w_list = [Button, Toggle, VSlider, HSlider, Label, xyPad, ColorSlider]
widget_classes = dict(zip([cls.__name__ for cls in w_list], w_list))
