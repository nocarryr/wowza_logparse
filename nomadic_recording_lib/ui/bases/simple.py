#import gtk

from Bases import BaseObject, Scaler
from Bases import Color as ColorObj
from Bases.Properties import PropertyConnector

class Color(BaseObject, PropertyConnector):
    color_keys = {'red':'red_float', 'green':'green_float', 'blue':'blue_float'}
    hsv_keys = ['hue', 'sat', 'val']
    def __init__(self, **kwargs):
        self._attribute = None
        super(Color, self).__init__(**kwargs)
        self.widget_set_by_program = False
        self.color_obj_set_by_program = False
        self.register_signal('color_changed')
        self.scale_factor = float(kwargs.get('scale_factor', 255))
        self.color = ColorObj()
        self.setup_widgets(**kwargs)
        self.color.bind(hsv=self.on_color_obj_changed)
        self.Property = kwargs.get('Property')
        
    def unlink(self):
        super(Color, self).unlink()
        self.Property = None
        
    def attach_Property(self, prop):
        super(Color, self).attach_Property(prop)
        self.set_color_obj(**prop.value)
        self.update_widget_color(**prop.value)
        
    def on_widget_update(self, *args, **kwargs):
        if self.widget_set_by_program:
            return
        hsv = self.get_widget_color()
        #self.color.hsv = dict(zip(self.hsv_keys, hsv))
        d = dict(zip(self.hsv_keys, hsv))
        self.set_Property_value(d)
        self.set_color_obj(**d)
        #if self.Property:
        #    self.Property.set_hsv(**self.color.hsv)
        #self.emit('color_changed', color=self.color, obj=self)
        
        
    def update_widget_color(self, **kwargs):
        #self.color.hsv = kwargs
        #hsv = self.color.hsv_seq
        #print self.color.hsv
        hsv = [kwargs[key] for key in self.hsv_keys]
        if True:#hsv != self.get_widget_color():
            self.widget_set_by_program = True
            self.set_widget_color(hsv)
            self.widget_set_by_program = False
        
    def on_Property_value_changed(self, **kwargs):
        value = kwargs.get('value')
        self.set_color_obj(**value)
        self.update_widget_color(**value)
        
    def set_color_obj(self, **kwargs):
        self.color_obj_set_by_program = True
        self.color.hsv = kwargs
        self.color_obj_set_by_program = False
        
    def on_color_obj_changed(self, **kwargs):
        if self.color_obj_set_by_program:
            return
        self.set_Property_value(self.color.hsv)
    
class LabelMixIn(PropertyConnector):
    def attach_Property(self, prop):
        maxint = 6
        decplaces = 3
        if prop.max is not None:
            max = prop.max
            maxint = len(str(int(max)))
        if prop.type == float:
            fmtstr = str(maxint+decplaces+1)
            fmtstr += '.%df' % (decplaces)
        elif prop.type == int:
            fmtstr = str(maxint) + 'd'
        else:
            fmtstr = 's'
        fmtstr = '%(value)' + fmtstr
        fmtstr += prop.symbol
        self.value_fmt_str = fmtstr
        super(LabelMixIn, self).attach_Property(prop)
        self._update_text_from_Property()
    def detach_Property(self, prop):
        self.value_fmt_str = '%(value)s'
        super(LabelMixIn, self).detach_Property(prop)
        self._update_text_from_Property()
    def on_Property_value_changed(self, **kwargs):
        self._update_text_from_Property(**kwargs)
    def get_Property_text(self, **kwargs):
        value = kwargs.get('value')
        if value is None:
            value = self.get_Property_value()
        if value is None:
            return 'None'
        return self.value_fmt_str % {'value':value}
    def _update_text_from_Property(self, **kwargs):
        s = self.get_Property_text(**kwargs)
        self.update_text_from_Property(s)
        
class EntryBuffer(BaseObject, PropertyConnector):
    def __init__(self, **kwargs):
        super(EntryBuffer, self).__init__(**kwargs)
        self.register_signal('modified')
        self.name = kwargs.get('name', '')
        self.setup_widgets(**kwargs)
        self.Property = kwargs.get('Property')
        self.widget_set_by_program = False
        self.set_widget_text(self.get_object_text())
    def unlink(self):
        self.Property = None
        super(EntryBuffer, self).unlink()
    def get_widget_text(self):
        pass
    def set_widget_text(self, text):
        pass
    def set_object_text(self, text):
        self.set_Property_value(text)
    def get_object_text(self):
        return self.get_Property_value()
    def on_widget_value_changed(self, *args, **kwargs):
        if self.widget_set_by_program:
            return
        self.set_object_text(self.get_widget_text())
    def on_Property_value_changed(self, **kwargs):
        self.widget_set_by_program = True
        self.set_widget_text(self.get_object_text())
        self.widget_set_by_program = False

class Spin(BaseObject, PropertyConnector):
    def __init__(self, **kwargs):
        super(Spin, self).__init__(**kwargs)
        self.scale_factor = kwargs.get('scale_factor', 1)
        self.widget_value_set_by_program = False
        self.setup_widgets(**kwargs)
        self.Property = kwargs.get('Property')
        
    def unlink(self):
        self.Property = None
        super(Spin, self).unlink()
        
    @property
    def value_range(self):
        if self.Property is None or self.Property.min is None:
            return [0, 255]
        return [self.Property.min, self.Property.max]
    @property
    def value_type(self):
        if self.Property is None:
            return int
        return self.Property.type
        
    def attach_Property(self, prop):
        super(Spin, self).attach_Property(prop)
        self.widget_value_set_by_program = True
        self.set_widget_range()
        self.set_widget_value(self.get_object_value())
        self.widget_value_set_by_program = False
        
    def set_widget_range(self):
        pass
        
    def on_Property_value_changed(self, **kwargs):
        self.widget_value_set_by_program = True
        self.set_widget_value(self.get_object_value())
        self.widget_value_set_by_program = False
        
    def on_widget_value_changed(self, *args, **kwargs):
        if not self.widget_value_set_by_program:
            self.set_object_value(self.get_widget_value())
        
    def get_object_value(self):
        if self.Property is None:
            return
        value = self.get_Property_value()
        if value is None:
            value = 0
        return value * self.scale_factor
        
    def set_object_value(self, value):
        if self.Property is None:
            return
        value = self.value_type(value / float(self.scale_factor))
        self.set_Property_value(value)

class Radio(BaseObject, PropertyConnector):
    def __init__(self, **kwargs):
        super(Radio, self).__init__(**kwargs)
        self.widget_signals = []
        self.widgets = {}
        self.widget_signals = {}
        self.Property = kwargs.get('Property')
        self.setup_widgets()
        
    def attach_Property(self, prop):
        super(Radio, self).attach_Property(prop)
        self.on_Property_value_changed()
        
    def unlink_Property(self, prop):
        super(Radio, self).unlink_Property(prop)
        self.remove_widgets()
        self.widgets.clear()
        self.widget_signals.clear()
        
    def setup_widgets(self):
        pass
    def build_widget(self, key):
        pass
    def remove_widgets(self):
        pass
        
    def unlink(self):
        self.Property = None
        super(Radio, self).unlink()
            
    def on_Property_value_changed(self, **kwargs):
        for key, val in self.Property.value.iteritems():
            if key not in self.widgets:
                self.widgets[key] = self.build_widget(key)
            self.widgets[key].set_active(val)
            
    def on_widgets_clicked(self, widget):
        for key, val in self.widgets.iteritems():
            if val.get_active():
                self.set_Property_value({key:True})

class Toggle(BaseObject, PropertyConnector):
    _Properties = {'state':dict(default=False)}
    def __init__(self, **kwargs):
        super(Toggle, self).__init__(**kwargs)
        self.widget_signals = []
        self.toggled_by_program = False
        self.setup_widgets(**kwargs)
        #self.set_widget_state(getattr(self.src_object, self.src_attr))
        self.bind(state=self._on_state_set)
        #if self.Property is not None:
        #    self.on_Property_value_changed()
        self.Property = kwargs.get('Property')
        
    def setup_widgets(self, **kwargs):
        pass
        
    def get_widget_state(self):
        pass
        
    def set_widget_state(self, state):
        pass
        
    def unlink(self):
        self.Property = None
        super(Toggle, self).unlink()
        
    def attach_Property(self, prop):
        super(Toggle, self).attach_Property(prop)
        state = self.get_Property_value()
        if state != self.state:
            self.state = state
        
    def _on_state_set(self, **kwargs):
        state = kwargs.get('value')
        if self.toggled_by_program:
            return
        self.toggled_by_program = True
        self.set_Property_value(state)
        self.set_widget_state(state)
        self.toggled_by_program = False
            
    def on_Property_value_changed(self, **kwargs):
        state = self.get_Property_value()
        if state != self.state:
            #self.toggled_by_program = True
            self.state = state
            #self.set_widget_state(state)
            
    def on_widget_toggled(self, *args):
        if not self.toggled_by_program:
            self.state = not self.state
            #self.set_Property_value(not self.get_Property_value())
        #self.toggled_by_program = False

class Fader(BaseObject, PropertyConnector):
    _Properties = {'name':dict(default='', fformat='_name_format'), 
                   'widget_is_adjusting':dict(default=False, quiet=True)}
    def __init__(self, **kwargs):
        super(Fader, self).__init__(**kwargs)
        name = kwargs.get('name')
        self._name = name
        self.widget_set_by_program = False
        #self.register_signal('obj_value_changed')
        self.offset_value_range = kwargs.get('offset_value_range', False)
        self.value_fmt_string = '%(value)d%(symbol)s'
        self.setup_widgets(**kwargs)
        self.bind(name=self._on_name_set, 
                  widget_is_adjusting=self._on_widget_is_adjusting_set)
        
        if name is not None:
            self.name = name
        self.Property = kwargs.get('Property')
    
    @property
    def value_range(self):
        if self.Property is None or self.Property.min is None:
            return [0, 255]
        if self.offset_value_range:
            return [0, self.Property.max - self.Property.min]
        return [self.Property.min, self.Property.max]
    @property
    def value_symbol(self):
        if self.Property is None:
            return ''
        return self.Property.symbol
        
    def _name_format(self, value):
        if self._name is not None:
            value = self._name
        return value
        
    def attach_Property(self, prop):
        super(Fader, self).attach_Property(prop)
        if prop.type == float:
            self.value_fmt_string = '%(value).3f%(symbol)s'
        else:
            self.value_fmt_string = '%(value)d%(symbol)s'
        self.name = prop.name
        self.set_widget_range()
        self.set_widget_value(self.get_Property_value())
        
    def setup_widgets(self, **kwargs):
        pass
        
    def unlink(self):
        self.Property = None
        super(Fader, self).unlink()
    
    def on_widget_change_value(self, *args):
        if self.widget_set_by_program:
            return
        if not self.widget_is_adjusting:
            return
        self.set_Property_value(self.get_widget_value(), convert_type=True)
    
    def on_Property_value_changed(self, **kwargs):
        value = kwargs.get('value')
        if self.widget_is_adjusting:
            return
        self.widget_set_by_program = True
        self.set_widget_value(value)
        self.widget_set_by_program = False
        #print 'fader %s, attribute %s, value %s' % (self, attrib, value)
        #self.emit('obj_value_changed', attribute=self.attribute, obj=self)
        
    def _on_widget_is_adjusting_set(self, **kwargs):
        state = kwargs.get('value')
        if not state:
            self.on_widget_change_value()
            
    def _on_name_set(self, **kwargs):
        pass
    def set_widget_value(self, value):
        pass
    def get_widget_value(self):
        pass
    def set_widget_range(self):
        pass
    def set_widget_label(self, label):
        pass
        
class ScaledFader(BaseObject):
    def __init__(self, **kwargs):
        super(ScaledFader, self).__init__(**kwargs)
        
        self.register_signal('obj_value_changed')
        self.parameter = kwargs.get('parameter')
        
        uilog = False
        if self.parameter.units == 'dB':
            uilog = True
        self.ui_scale = {'min':self.parameter.scaled_min, 'max':self.parameter.scaled_max, 'LOG':uilog}
        self.param_scale = {'min':self.parameter.value_min, 'max':self.parameter.value_max}
        
        self.scaler = Scaler(scales={'ui':self.ui_scale, 'param':self.param_scale})
        
        self.fader_drag = False
        if self.parameter.value is not None:
            self.scaler.set_value('param', self.parameter.value)
        self.widget_signals = []
        self.setup_widgets(**kwargs)
        self.parameter.connect('value_update', self.on_parameter_value_update)
        self.scaler.connect('value_update', self.on_scaler_value_update)
    
    def setup_widgets(self, **kwargs):
        pass
        
    def unlink(self):
        self.parameter.disconnect(callback=self.on_parameter_value_update)
        for id in self.widget_signals:
            self.widget.disconnect(id)
            
    def on_widget_button_press(self, *args):
        self.fader_drag = True
    def on_widget_button_release(self, *args):
        self.fader_drag = False
    
    def on_widget_change_value(self, range, scroll, value):
        pass
    
    def on_parameter_value_update(self, **kwargs):
        param = kwargs.get('parameter')
        value = kwargs.get('value')
        if param == self.parameter and self.fader_drag is False:
            #print 'fader:', kwargs
            #self.adj.set_value(value)
            self.scaler.set_value('param', value)
        
    def set_widget_value(self, value):
        pass
        
    def on_scaler_value_update(self, **kwargs):
        name = kwargs.get('name')
        value = kwargs.get('value')
        if name == 'ui':
            self.set_widget_value(value)
        elif name == 'param':
            if int(value) != self.parameter.value:
                self.parameter.set_value(int(value))
                self.emit('obj_value_changed', parameter=self.parameter, obj=self)#, adj=self.adj)
                #print 'param: ', value
        #print 'adj: ', self.adj.get_value(), ', param: ', self.parameter.value

class Meter(BaseObject):
    def __init__(self, **kwargs):
        super(Meter, self).__init__(**kwargs)
        
