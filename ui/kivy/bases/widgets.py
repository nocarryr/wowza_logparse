import os.path
import threading
import collections

from Bases import BaseObject, BaseThread
from Bases.Properties import PropertyConnector
from Bases.color import PixelGrid
from ...bases import simple

from widget_classes import Widgets

from kivy.clock import Clock as KivyClock
import kivy.graphics
from kivy.properties import NumericProperty, AliasProperty, DictProperty, BooleanProperty

KV_STATE_MAP = {True:'down', False:'normal'}

class HBox(Widgets.BoxLayout):
    pass
    
class VBox(HBox):
    def __init__(self, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        super(VBox, self).__init__(**kwargs)
    
class Table(Widgets.GridLayout):
    pass

class ScrolledWindow(Widgets.ScrollView):
    pass
    
def build_border_lines(widget, extra=0):
    right = widget.right + extra
    left = right - widget.size[0] - extra
    top = widget.top + extra
    bottom = top - widget.size[1] - extra
    
    lines = [[left, top, right, top], 
             [right, top, right, bottom], 
             [right, bottom, left, bottom], 
             [left, bottom, left, top]]
    return lines
    
class Dummy(object):
    def __init__(self, **kwargs):
        for key, val in kwargs.iteritems():
            setattr(self, key, val)

class Frame(Widgets.Widget):
    def __init__(self, **kwargs):
        self.enable_border = kwargs.get('enable_border', True)
        self.make_label = kwargs.get('make_label', True)
        self.topwidget = kwargs.get('topwidget')
            
        if self.enable_border:
            self.canvas = kivy.graphics.Canvas()
            dummy = Dummy(right=20, top=20, size=[10, 10])
            self.border_lines = []
            with self.canvas:
                #self.bgcolor = kivy.graphics.Color(*kwargs.get('bgcolor', [.1, .1, .1, 1.]))
                #self.bgrect = kivy.graphics.Rectangle(pos=self.pos, size=self.size)
                self.border_color = kivy.graphics.Color(*kwargs.get('border_color', [1, 1, 1]))
                #self.border_rect = kivy.graphics.BorderImage(border=[10, 10, 10, 10], pos=self.pos, size=self.size)
                for line in build_border_lines(dummy):
                    self.border_lines.append(kivy.graphics.Line(points=line))
        super(Frame, self).__init__(**kwargs)
        
        if self.topwidget is None:
            self.topwidget = VBox()
        if self.topwidget:
            self.add_widget(self.topwidget)
            self.topwidget.size = self.size
            self.topwidget.pos = self.pos
            
        if self.make_label:
            lblkwargs = kwargs.get('label_kwargs', {})
            for key in ['label', 'text', 'name']:
                if key in kwargs:
                    lblkwargs.setdefault(key, kwargs[key])
                    break
            lblkwargs.setdefault('size_hint_y', .1)
            self.label = Label(**lblkwargs)
            self.add_widget(self.label)
        if self.enable_border:
            self.bind(**dict(zip(['pos', 'size'], [self._on_pos_or_size_set]*2)))
            
    def _on_pos_or_size_set(self, *args):
        for i, line in enumerate(build_border_lines(self)):
            self.border_lines[i].points = line
        if self.topwidget:
            self.topwidget.size = self.size
            self.topwidget.pos = self.pos
            
    def set_label(self, text):
        if self.make_label:
            self.label.text = text
    
    def add_widget(self, *args, **kwargs):
        if self.topwidget is not False and args[0] != self.topwidget:
            #print 'redirecting add_widget:', self.topwidget, args
            self.topwidget.add_widget(*args, **kwargs)
        else:
            super(Frame, self).add_widget(*args, **kwargs)
            
class FileChooser(BaseObject):
    _view_mode_classes = {'list':Widgets.FileChooserListView, 
                          'icon':Widgets.FileChooserIconView}
    _file_mode_btn_keys = {'open':['Open', 'Cancel'], 
                           'save':['Save', 'Cancel'], 
                           'saveas':['Save As', 'Cancel']}
    _float_size = {'width':.5, 'height':.8}
    _Properties = {'current_file':dict(default=''), 
                   'current_path':dict(default='')}
    def __init__(self, **kwargs):
        super(FileChooser, self).__init__(**kwargs)
        self.register_signal('selection_made', 'popup_closed')
        self._selection_by_chooser = False
        self.bind(current_file=self._on_current_file_set)
        self.view_mode = kwargs.get('view_mode', 'list')
        self.file_mode = kwargs.get('file_mode', 'open')
        vbox = VBox()
        self.chooser = self._view_mode_classes[self.view_mode](**kwargs)
        self.current_path = self.chooser.path
        self.chooser.bind(path=self.on_chooser_path_changed, 
                          on_submit=self.on_chooser_submit)
        vbox.add_widget(self.chooser)
        self.txtFilename = Entry(name='Filename', Property=(self, 'current_file'), no_frame=True)
        self.txtFilename.topwidget.size_hint_y = .1
        vbox.add_widget(self.txtFilename.topwidget)
        hbox = HBox(size_hint_y=.1)
        self.btns = {}
        for key in self._file_mode_btn_keys[self.file_mode]:
            btn = Button(label=key)
            self.btns[key] = btn
            btn.bind(on_release=self.on_btn_release)
            hbox.add_widget(btn)
        vbox.add_widget(hbox)
        self.topwidget = Widgets.Popup(title='Select File', content=vbox, size_hint=[.5, .8])
        
        self.topwidget.open()
    
    def _on_current_file_set(self, **kwargs):
        self.LOG.info('current file: ',  kwargs.get('value'), self.current_file)
        #if not self._selection_by_chooser:
        #    pass
        #    self.chooser.selection = []
        self._selection_by_chooser = False
        
    def on_chooser_submit(self, chooser, selection, touch):
        self.LOG.info('chooser submit: ', selection)
        self._selection_by_chooser = True
        if len(selection):
            self.current_file = str(os.path.basename(selection[0]))
        else:
            self.current_file = ''
        
    def on_chooser_path_changed(self, chooser, path):
        self.current_path = str(path)
        self.current_file = ''
    
    def on_btn_release(self, btn):
        for key, val in self.btns.iteritems():
            if btn == val:
                mode = key
        if mode != 'Cancel':
            if self.current_file != '':
                path = os.path.join(self.current_path, self.current_file)
                self.emit('selection_made', chooser=self, selection=path)
        self.topwidget.dismiss()
        self.emit('popup_closed', chooser=self)
        

class Label(Widgets.Label):
    def __init__(self, **kwargs):
        lbl = kwargs.get('label')
        if lbl:
            kwargs.setdefault('text', lbl)
        super(Label, self).__init__(**kwargs)
    def unlink(self):
        pass
#        with self.canvas:
#            self.bgcolor = kivy.graphics.Color(*kwargs.get('bgcolor', [.1, .1, .1, 1.]))
#            self.bgrect = kivy.graphics.Rectangle(texture=self.texture, pos=self.pos, size=self.size)
#        self.bind(pos=self._on_pos_set, size=self._on_size_set)
#    def _on_pos_set(self, widget, pos):
#        self.bgrect.pos = pos
#        self.texture_update()
#        self.bgrect.texture = self.texture
#    def _on_size_set(self, widget, size):
#        self.bgrect.size = size
#        self.texture_update()
#        self.bgrect.texture = self.texture

class Button(Widgets.Button):
    bool_state = BooleanProperty(False)
    def __init__(self, **kwargs):
        label = kwargs.get('label')
        if label:
            kwargs.setdefault('text', label)
        super(Button, self).__init__(**kwargs)
        self.bind(bool_state=self._on_bool_state, 
                  state=self._on_state)
    def _on_bool_state(self, *args):
        state = KV_STATE_MAP[self.bool_state]
        if state != self.state:
            self.state = state
    def _on_state(self, *args):
        bstate = self.state == KV_STATE_MAP[True]
        if bstate != self.bool_state:
            self.bool_state = bstate
        
class ToggleBtn(simple.Toggle):
    def setup_widgets(self, **kwargs):
        lbl = kwargs.get('label')
        if lbl:
            kwargs.setdefault('text', lbl)
        self.widget = Widgets.ToggleButton(**kwargs)
        self.widget.bind(state=self.on_widget_toggled)
    def get_widget_state(self):
        return self.widget.state == KV_STATE_MAP[True]
    def set_widget_state(self, value):
        self.widget.state = KV_STATE_MAP[value]
        
#class Entry(simple.EntryBuffer):
#    def setup_widgets(self, **kwargs):
#        self.widget = Widgets.TextInput(text='', multiline=False)
#        if kwargs.get('no_frame', False):
#            self.topwidget = self.widget
#        else:
#            self.topwidget = Frame(label=self.name)
#            self.topwidget.add_widget(self.widget)
#        self.widget.bind(focus=self.on_widget_focus)
#    def on_widget_focus(self, widget, value):
#        if not value:
#            self.on_widget_value_changed()
#    def get_widget_text(self):
#        return self.widget.text
#    def set_widget_text(self, text):
#        self.widget.text = text
        
class Entry(simple.EntryBuffer):
    def __init__(self, **kwargs):
        super(Entry, self).__init__(**kwargs)
        if kwargs.get('no_frame', False):
            self.topwidget = self.widget
        else:
            self.widget.size_hint_y = .2
            self.topwidget = Frame(label=kwargs.get('label', self.name))#, enable_border=False)
            self.topwidget.add_widget(self.widget)
    def setup_widgets(self, **kwargs):
        self.widget = Widgets.TextInput(multiline=False)
        self.widget.bind(focus=self.on_widget_focus)
    def on_widget_focus(self, widget, value):
        if not value:
            self.on_widget_value_changed()
    def get_widget_text(self):
        return str(self.widget.text)
    def set_widget_text(self, text):
        #print 'entry setwidget text: ', text
        if text is None:
            text = ''
        #print 'widget text: ', text
        self.widget.text = text
        self.widget_set_by_program = False
        
class SpinBtn(simple.Spin):
    def __init__(self, **kwargs):
        self.value_increment = 1
        super(SpinBtn, self).__init__(**kwargs)
        if kwargs.get('no_frame', False):
            self.topwidget = self.widget
        else:
            self.topwidget = Frame(label=kwargs.get('label', ''))
            self.topwidget.add_widget(self.widget)
    def setup_widgets(self, **kwargs):
        self.widget = HBox()
        self.value_entry = Entry(no_frame=True)
        self.widget.add_widget(self.value_entry.topwidget)
        btnbox = VBox(size_hint_x=.2)
        self.updown_btns = {}
        for key in ['up', 'dn']:
            btn = Button(label=key, size_hint_y=.5)
            btn.key = key
            btn.bind(state=self.on_updown_btns_state)
            btnbox.add_widget(btn)
            self.updown_btns[key] = btn
        self.widget.add_widget(btnbox)
    def set_widget_value(self, value):
        #print self, value
        self.value_entry.set_widget_text('%.3f' % (value))
    def on_updown_btns_state(self, btn, state):
        if state:
            self.start_ramp(direction=btn.key)
        else:
            self.stop_ramp(direction=btn.key)
    def start_ramp(self, **kwargs):
        self.do_increment(**kwargs)
    def stop_ramp(self, **kwargs):
        pass
    def do_increment(self, **kwargs):
        direction = kwargs.get('direction')
        current = self.get_Property_value()
        if current is None:
            return
        value = current
        min, max = self.value_range
        if direction == 'up':
            value = current + self.value_increment
            if value > max:
                value = max
        elif direction == 'dn':
            value = current - self.value_increment
            if value < min:
                value = min
        self.set_Property_value(value)
        
class Slider(simple.Fader):
    def setup_widgets(self, **kwargs):
        self.name = kwargs.get('name', kwargs.get('label', ''))
        self.no_frame = kwargs.get('no_frame', False)
        kwargs.setdefault('max', 255)
        d = dict(value_min='min', value_max='max', lower='min', upper='max')
        w_kwargs = {}
        for key, val in kwargs.get('adj_kwargs', {}).iteritems():
            if key in d:
                w_kwargs.update({d[key]:val})
        for key, val in kwargs.iteritems():
            if key in d:
                w_kwargs.update({d[key]:val})
            if self.no_frame and 'size_hint' in key:
                w_kwargs[key] = val
        w_kwargs.setdefault('orientation', self.orientation)
        self.widget = Widgets.Slider(**w_kwargs)
        self.widget.bind(value=self.on_widget_change_value, 
                         on_touch_down=self.on_widget_button_press, 
                         on_touch_up=self.on_widget_button_release)
        if kwargs.get('no_frame', False):
            self.topwidget = self.widget
        else:
            self.topwidget = Frame(label=self.name)
            self.topwidget.add_widget(self.widget)
            self.value_label = Label(text='', size_hint_y=.1)
            self.topwidget.add_widget(self.value_label)
            self.widget.bind(value=self._on_widget_value_changed)
        
    def on_widget_button_press(self, *args, **kwargs):
        self.widget_is_adjusting = True
    def on_widget_button_release(self, *args, **kwargs):
        self.widget_is_adjusting = False
        
    def attach_Property(self, prop):
        super(Slider, self).attach_Property(prop)
        if self.name == '' and not self.no_frame:
            self.topwidget.set_label(prop.name)
    def set_widget_range(self):
        if self.Property:
            for key in ['min', 'max']:
                val = getattr(self.Property, key)
                if val is not None:
                    setattr(self.widget, key, val)
    def get_widget_value(self):
        return self.widget.value
    def set_widget_value(self, value):
        if value is None:
            value = 0
        self.widget.value = value
    def _on_widget_value_changed(self, *args):
        self.value_label.text=str(self.get_Property_value())
    
class HSlider(Slider):
    orientation = 'horizontal'
    
class VSlider(Slider):
    orientation = 'vertical'
    
class XYPad(BaseObject, PropertyConnector):
    xy_keys = ['x', 'y']
    pos_keys = ['pan', 'tilt']
    num_grid_lines = 6
    _Properties = {'x':dict(default=0., min=0., max=1., quiet=True), 
                   'y':dict(default=0., min=0., max=1., quiet=True), 
                   'pos':dict(fset='_pos_setter', fget='_pos_getter', 
                              default={'x':0., 'y':0.}, 
                              min={'x':0., 'y':0.}, 
                              max={'x':1., 'y':1.}, 
                              quiet=True), 
                   'value':dict(default={'x':0., 'y':0.}, 
                                min={'x':0., 'y':0.}, 
                                max={'x':1., 'y':1.}, 
                                quiet=True)}
    def __init__(self, **kwargs):
        super(XYPad, self).__init__(**kwargs)
        self.prop_keys = self.xy_keys
        self.Property_changed_by_value = False
        #self._xypos = [0., 0.]
        self.cursor_size = (10, 10)
        #self.topwidget = VBox()
        #self.widget = Widgets.Widget()
        
        #self.widget = Frame(make_label=False, topwidget=False)
        self.widget = XYTouchWidget()
        
        self.build_xy_spins = kwargs.get('build_xy_spins', True)
        if self.build_xy_spins:
            self.topwidget = Frame(label=kwargs.get('label', 'XYPad'))
            self.topwidget.add_widget(self.widget)
            hbox = HBox(size_hint_y=.2)
            self.xySpins = {}
            for key in self.xy_keys:
                w = SpinBtn(no_frame=True, Property=(self, key))
                hbox.add_widget(w.topwidget)
                self.xySpins[key] = w
            self.value_label = Label()
            hbox.add_widget(self.value_label)
            self.topwidget.add_widget(hbox)
        else:
            self.topwidget = self.widget
            
        self.draw_grid = kwargs.get('draw_grid', True)
        if self.draw_grid:
            self.grid_lines = {'x':[], 'y':[]}
            xylines = self.build_grid_line_points()
            with self.widget.canvas:
                self.grid_color = kivy.graphics.Color(.8, .8, .8)
                for key, lines in xylines.iteritems():
                    for line in lines:
                        self.grid_lines[key].append(kivy.graphics.Line(points=line))
        self.cursor = XYCursor(size=self.cursor_size)
        self.widget.add_widget(self.cursor)
        self.update_cursor_pos()
        self.widget.bind(**dict(zip(['pos', 'size'], [self.on_widget_size_or_pos_changed]*2)))
        self.widget.bind(value_dict=self.on_widget_pos_value_changed)
        #for key in self.xy_keys:
        #    self.Properties[key].link(self.Properties['value'], key)
        self.bind(value=self._on_value_set)
        
    def _pos_getter(self):
        return dict(zip(self.xy_keys, [self.x, self.y]))
    def _pos_setter(self, value):
        old = [self.x, self.y]
        for key, val in value.iteritems():
            if key in self.xy_keys and getattr(self, key) != val:
                setattr(self, key, val)
        pos = self.Properties['pos']
        pos.value = value
        pos.emit(old)
        self.update_cursor_pos()
        #calc_value = pos.normalized_and_offset
        d = dict(zip(self.prop_keys, [value[key] for key in self.xy_keys]))
        #print 'pos_setter: calc=%s, d=%s' % (calc_value, d)
        self.Properties['value'].normalized_and_offset = d
        #print 'pos value=%s \n d=%s \n propvalue=%s' % (value, d, self.value)
    
    def on_widget_pos_value_changed(self, *args):
        value = self.widget.value_dict
        for key, val in value.iteritems():
            self.Properties[key].normalized_and_offset = val
        self.pos = dict(zip(self.xy_keys, [self.x, self.y]))
        
    def update_cursor_pos(self, *args):
        size = self.widget.size
        pos = self.widget.pos
        value = self.widget.value_dict
        #props = [self.Properties[key] for key in self.xy_keys]
        #value = [prop.normalized_and_offset * size[i] + pos[i] for i, prop in enumerate(props)]
        calc_value = [value[key] * size[i] + pos[i] for i, key in enumerate(['x', 'y'])]
        #print 'cursor_pos=%s, widget_pos=%s, widget_size=%s, xy=%s' % (value, pos, size, [self.x, self.y])
        self.cursor.center = calc_value
        
    def on_widget_size_or_pos_changed(self, *args):
        self.update_cursor_pos()
        if not self.draw_grid:
            return
        xylines = self.build_grid_line_points()
        with self.widget.canvas:
            for key, lines in xylines.iteritems():
                for i, line in enumerate(lines):
                    self.grid_lines[key][i].points = line
                
    def build_grid_line_points(self):
        size = dict(zip(['x', 'y'], self.widget.size))
        right = self.widget.right
        left = right - size['x']
        top = self.widget.top
        bottom = top - size['y']
        scale = dict(zip(['x', 'y'], [size[key] / float(self.num_grid_lines) for key in ['x', 'y']]))
        xylines = {'x':[], 'y':[]}
        for i in range(self.num_grid_lines):
            x = left + (scale['x'] * i)
            y = bottom + (scale['y'] * i)
            xylines['x'].append([left, y, right, y])
            xylines['y'].append([x, bottom, x, top])
        return xylines
        
    def attach_Property(self, prop):
        super(XYPad, self).attach_Property(prop)
        keys = prop.value.keys()
        if keys[0] in self.xy_keys:
            self.prop_keys = self.xy_keys
        elif keys[0] in self.pos_keys:
            self.prop_keys = self.pos_keys
        #print 'Property value=%s, min=%s, max=%s' % (prop.value, prop.min, prop.max)
        myprop = self.Properties['value']
        #print 'prop_keys=%s, Propval=%s, valueval=%s' % (self.prop_keys, prop.value, self.value)
        myprop.value.clear()
        #print 'cleared'
        myprop.min = prop.min
        myprop.max = prop.max
        myprop.set_value(prop.value)
        #print 'after: value=%s, min=%s, max=%s' % (myprop.value, myprop.min, myprop.max)
        
        
    def on_Property_value_changed(self, **kwargs):
        if self.Property_changed_by_value:
            return
        self.Property_changed_by_value = False
        prop = kwargs.get('Property')
        value = prop.normalized_and_offset
        #print ' Prop value=%s \n normalized_and_offset=%s \n min=%s, max=%s\n\n' % (prop.value, prop.normalized_and_offset, prop.min, prop.max)
#        d = {}
#        for i, key in enumerate(self.prop_keys):
#            xykey = self.xy_keys[i]
#            d[xykey] = value[key]
#        self.value.normalized_and_offset = d
        self.value = self.get_Property_value()
            
    def _on_value_set(self, **kwargs):
        prop = kwargs.get('Property')
        value = kwargs.get('value')
        if len(value) < 2:
            return
        #value = prop.normalized_and_offset
        #print ' Value value=%s \n normalized_and_offset=%s \n min=%s, max=%s\n\n' % (prop.value, prop.normalized_and_offset, prop.min, prop.max)
        #if self.Property is None:
        #    return
        self.Property_changed_by_value = True
        self.set_Property_value(value)
        calc_value = prop.normalized_and_offset
        for i, key in enumerate(self.xy_keys):
            propkey = self.prop_keys[i]
            self.Properties[key].normalized_and_offset = calc_value[propkey]
        if hasattr(self, 'value_label'):
            s = ', '.join(['%.3f' % (self.value[key]) for key in self.prop_keys])
            #print 'value_label text = ', s
            self.value_label.text = s
        self.update_cursor_pos()
        
class XYTouchWidget(Widgets.Widget):
    value_x = NumericProperty(0.)
    value_y = NumericProperty(0.)
    value_dict = DictProperty({'x':0., 'y':0.})
    def __init__(self, **kwargs):
        #self.touch_callback = kwargs.get('touch_callback')
        super(XYTouchWidget, self).__init__(**kwargs)
        
    def _get_value(self):
        return dict(zip(['x', 'y'], [self.value_x, self.value_y]))
    def _set_value(self, value):
        d = {}
        for key in ['x', 'y']:
            if key in value:
                setattr(self, '_'.join(['value', key]), value[key])
                d[key] = value[key]
            else:
                d[key] = self.value_dict[key]
        self.value_dict = d
                
    value = AliasProperty(_get_value, _set_value)#, bind=('value_x', 'value_y'))
    
    def calc_touch_pos(self, pos):
        #x = min(self.right, max(pos[0], self.x))
        #y = min(self.top, max(pos[1], self.y))
        value = {}
        #value['x'] = (x - self.x) / float(self.width)
        #value['y'] = (y - self.y) / float(self.height)
        
        for i, keys in enumerate(zip(['x', 'y'], [['width', 'right'], ['height', 'top']])):
            m = min(getattr(self, keys[1][1]), max(pos[i], getattr(self, keys[0])))
            value[keys[0]] = (m - getattr(self, keys[0])) / float(getattr(self, keys[1][0]))
        return value
        
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        #if self in touch.ud:
        #    return False
        touch.grab(self)
        touch.ud[self] = True
        self.value = self.calc_touch_pos(touch.pos)        
        return True
    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return
        self.value = self.calc_touch_pos(touch.pos)
        return True
    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return
        assert(self in touch.ud)
        touch.ungrab(self)
        self.value = self.calc_touch_pos(touch.pos)
        return True
    
    
class XYCursor(Button):
    def __init__(self, **kwargs):
        super(XYCursor, self).__init__(**kwargs)
        #self.touch_callback = kwargs.get('touch_callback')
        self.canvas.clear()
        with self.canvas:
            self.cursor_color = kivy.graphics.Color(.8, .8, .8)
            self.cursor_rect = kivy.graphics.Rectangle(size=self.size, pos=self.pos)
        self.bind(pos=self._on_widget_pos_set, size=self._on_widget_size_set)
    def _on_widget_pos_set(self, widget, value):
        self.cursor_rect.pos = value
    def _on_widget_size_set(self, widget, value):
        self.cursor_rect.size = value
    def _do_press(self):
        pass
    def _do_release(self):
        pass
#    def on_touch_down(self, touch):
#        if not super(XYCursor, self).on_touch_down(touch):
#            return False
#        self.touch_callback(touch)
#        return True
#    def on_touch_move(self, touch):
#        if not super(XYCursor, self).on_touch_move(touch):
#            return False
#        self.touch_callback(touch)
#        return True
#    def on_touch_up(self, touch):
#        if not super(XYCursor, self).on_touch_up(touch):
#            return False
#        self.touch_callback(touch)
#        return True
        
class ColorPicker(simple.Color):
    #_Properties = dict(zip(['hue', 'sat', 'val'], [{'default':0.}]*3))
    _Properties = {'hue':dict(default=0., min=0., max=1.), 
                   'sat':dict(default=0., min=0., max=1.), 
                   'val':dict(default=0., min=0., max=1.), 
                   'slider_value':dict(default=0., min=0., max=1.)}
    def __init__(self, **kwargs):
        super(ColorPicker, self).__init__(**kwargs)
        self.register_signal('color_changed')
        self.color_mode = kwargs.get('color_mode', 'hsv')
        self.slider_value_set_by_program = False
        self.topwidget = VBox()
        hbox = HBox()
        self.slider = HueSlider(size_hint_x=.2)
        self.slider.Property = (self, 'slider_value')
        hbox.add_widget(self.slider.topwidget)
        self.picker = ColorXY(color_mode=self.color_mode)
        hbox.add_widget(self.picker.topwidget)
        
        self.topwidget.add_widget(hbox)
        self.color_display = ColorDisplay()
        self.topwidget.add_widget(self.color_display)
        self.picker.bind(hsv=self.on_picker_hsv_changed)
        hbox = HBox(size_hint_y=.2)
        self.hsv_spins = {}
        for key in ['hue', 'sat', 'val']:
            w = SpinBtn(label=key, Property=(self, key))
            hbox.add_widget(w.topwidget)
            self.hsv_spins[key] = w
        self.topwidget.add_widget(hbox)
        self.bind(slider_value=self._on_slider_value_set)
        
    def setup_widgets(self, **kwargs):
        pass
        
    def unlink(self):
        self.picker.unlink()
        self.slider.unlink()
        super(ColorPicker, self).unlink()
    def on_picker_hsv_changed(self, **kwargs):
        value = kwargs.get('value')
        for key, val in value.iteritems():
            setattr(self, key, val)
        self.color_display.set_color(value)
        self.on_widget_update()
        self.emit('color_changed', widget=self, color=value)
        
    def get_widget_color(self):
        return [getattr(self, key) for key in ['hue', 'sat', 'val']]
    def set_widget_color(self, hsv):
        if self.color_mode == 'hsv':
            self.slider_value_set_by_program = True
            self.slider_value = hsv[0]
        self.picker.hsv = dict(zip(['hue', 'sat', 'val'], hsv))
        self.color_display.set_color(hsv)
        
    def _on_slider_value_set(self, **kwargs):
        value = kwargs.get('value')
        if self.slider_value_set_by_program:
            self.slider_value_set_by_program = False
            return
        if self.color_mode == 'hsv':
            self.picker.hsv['hue'] = value
        elif self.color_mode == 'rgb':
            self.val = value
        
class ColorXY(XYPad):
    hsv_keys = ['hue', 'sat', 'val']
    _Properties = {'hsv':dict(default=dict(zip(hsv_keys, [0.]*3)), quiet=True)}
    def __init__(self, **kwargs):
        kwargs.setdefault('draw_grid', False)
        kwargs.setdefault('build_xy_spins', False)
        self.hsv_set_by_widget = False
        super(ColorXY, self).__init__(**kwargs)
        self.color_mode = kwargs.get('color_mode')
        self.bgwidget = Widgets.Label(size=self.widget.size, pos=self.widget.pos)
        #self.bgwidget.prepare_remove = self.prepare_remove
        self.widget.add_widget(self.bgwidget, index=1)
        self._current_pixel = None
        self.register_signal('color_changed')
        self.texture_obj = TextureObj(pattern=self.color_mode)
        with self.bgwidget.canvas:
            self.texture_rect = kivy.graphics.Rectangle(texture=self.texture_obj._texture, 
                                                        size=self.widget.size, pos=self.widget.pos)
        self.widget.bind(pos=self._on_widget_pos_set, size=self._on_widget_size_set)
        #self.bind(pos=self._on_pos_set)
        self.bind(hsv=self._on_hsv_set)
        
    def unlink(self):
        super(ColorXY, self).unlink()
        self.texture_obj.unlink()
        
    def prepare_remove(self):
        self.texture_obj.unlink()
        
    def _on_widget_pos_set(self, widget, value):
        self.bgwidget.pos = value
        self.texture_rect.pos = value
    def _on_widget_size_set(self, widget, value):
        #self.texture_obj.resize(size=value)
        self.bgwidget.size = value
        self.texture_rect.size = value
    def _on_value_set(self, **kwargs):
        super(ColorXY, self)._on_value_set(**kwargs)
        #prop = self.Properties['value']
        #normval = prop.normalized_and_offset
        value = self.pos
        tex_xy = [int(value[key] * self.texture_obj.size[i] - 1) for i, key in enumerate(self.xy_keys)]
        for i in range(2):
            if tex_xy[i] < 0 or tex_xy[i] >= self.texture_obj.size[i]:
                return
        pixel = self.texture_obj.grid.pixels[tex_xy[1]][tex_xy[0]]
        if pixel != self._current_pixel:
            self._current_pixel = pixel
            self.hsv_set_by_widget = True
            self.hsv = self._current_pixel.hsv
            self.emit('color_changed', widget=self, color=pixel)
    def _on_hsv_set(self, **kwargs):
        if self.hsv_set_by_widget:
            self.hsv_set_by_widget = False
            return
        #value = kwargs.get('value')
        old = kwargs.get('old')
        value = self.hsv
        if self.color_mode == 'hsv':
            if old['hue'] != value['hue']:
                self.texture_obj.setattr_all_pixels(hue=value['hue'])
                #print 'pos=%s, hue=%s, hsv_dictkeys=%s' % ([self.pos['x'], self.pos['y']], value['hue'], self.texture_obj.grid.pixels_by_hsv.keys())
            if True in [old[key] != value[key] for key in ['sat', 'val']]:
                pixel = self.texture_obj.find_pixel_from_hsv(value)
                tex_xy = [pixel.grid_location[key] / (self.texture_obj.size[i] + 1.) for i, key in enumerate(['col', 'row'])]
                xy = dict(zip(self.xy_keys, tex_xy))
                self.pos = xy
        
#    def _on_pos_set(self, **kwargs):
#        props = [self.Properties[key] for key in self.xy_keys]
#        #tex_xy = [int((prop.value / (prop.max - prop.min) + prop.min) * self.texture_obj.size[i]) for i, prop in enumerate(props)]
#        tex_xy = [int(prop.normalized_and_offset * self.texture_obj.size[i] - 1) for i, prop in enumerate(props)]
#        #print tex_xy
#        for i in range(2):
#            if tex_xy[i] < 0 or tex_xy[i] >= self.texture_obj.size[i]:
#                return
#        pixel = self.texture_obj.grid.pixels[tex_xy[1]][tex_xy[0]]
#        if pixel != self._current_color:
#            self._current_color = pixel
#            self.emit('color_changed', widget=self, color=pixel)
    def on_color_changed(self, color):
        pass
        
class HueSlider(VSlider):
    def __init__(self, **kwargs):
        kwargs['no_frame'] = True
        super(HueSlider, self).__init__(**kwargs)
        self.bgwidget = Widgets.Label(size_hint_x=kwargs.get('size_hint_x', .2))
        self.bgwidget.prepare_remove = self.prepare_remove
        #self.widget.add_widget(self.bgwidget, index=1)
        self.topwidget = self.bgwidget
        texture_obj = TextureObj(size=(1, 128), pattern='none')
        with self.bgwidget.canvas:
            self.texture_rect = kivy.graphics.Rectangle(texture=texture_obj._texture, 
                                                        size=self.topwidget.size, pos=self.topwidget.pos)
        self.bgwidget.add_widget(self.widget)
        self.topwidget.bind(pos=self._on_widget_pos_set, size=self._on_widget_size_set)
        #scale = float(self.texture_obj.size[0])
        scale = 128.
        for y, row in enumerate(texture_obj.grid.pixels):
            for x, pixel in enumerate(row):
                pixel.hue = x / scale
                pixel.sat = 1.
                pixel.val = 1.
        texture_obj.blit_texture()
        self.texture_obj = texture_obj
                
    def unlink(self):
        super(HueSlider, self).unlink()
        self.texture_obj.unlink()
        
    def prepare_remove(self):
        self.texture_obj.unlink()
        
    def _on_widget_pos_set(self, widget, value):
        self.widget.pos = value
        self.texture_rect.pos = value
    def _on_widget_size_set(self, widget, value):
        self.widget.size = value
        self.texture_rect.size = value
        
class ColorDisplay(Button):
    def __init__(self, **kwargs):
        kwargs.setdefault('size_hint_y', .2)
        super(ColorDisplay, self).__init__(**kwargs)
        with self.canvas:
            self.canvas_color = kivy.graphics.Color(0., 0., 0)
            self.canvas_rect = kivy.graphics.Rectangle(size=self.size, pos=self.pos)
        self.bind(pos=self._on_widget_pos_set, size=self._on_widget_size_set)
        
    def _on_widget_pos_set(self, widget, value):
        self.canvas_rect.pos = value
        
    def _on_widget_size_set(self, widget, value):
        self.canvas_rect.size = value
        
    def set_color(self, hsv):
        if isinstance(hsv, dict):
            hsv = [hsv[key] for key in ['hue', 'sat', 'val']]
        self.canvas_color.hsv = hsv
        

datatype_map = {chr:{'array':'c', 'ogl':'ubyte'}}
class TextureObj(object):
    hsv_keys = ['hue', 'sat', 'val']
    def __init__(self, **kwargs):
        self.size = kwargs.get('size', (32, 32))
        self.pattern = kwargs.get('pattern', 'hsv')
        self.datatype = kwargs.get('datatype', chr)
        self.arraytype = datatype_map[self.datatype]['array']
        self.oglbuffertype = datatype_map[self.datatype]['ogl']
        self.color_format = kwargs.get('color_format', 'rgb')
        self.update_threads = collections.deque()
        self.threaded_updater = ThreadedUpdater(job_complete_cb=self.on_threaded_job_complete)
        self.threaded_updater.start()
        self.grid = PixelGrid(size=self.size)
        self.build_texture()
        self.build_pattern()
        self.blit_texture()
        
    def unlink(self):
        self.threaded_updater.stop(blocking=True)
        
    def add_update_job(self, cb, **kwargs):
        self.threaded_updater.add_job(cb, **kwargs)
        
    def on_threaded_job_complete(self, *args, **kwargs):
        KivyClock.schedule_once(self.blit_texture, 0)
        
    def build_pattern(self, cb=None):
        if cb is not None:
            pass
        elif self.pattern == 'hsv':
            cb = self.build_hsv_pattern
        elif self.pattern == 'rgb':
            cb = self.build_rgb_pattern
        else:
            return
        self.add_update_job(cb)
    
    def build_texture(self):
        self._texture = kivy.graphics.texture.Texture.create(size=self.size, colorfmt=self.color_format)
    
    def find_pixel_from_hsv(self, hsv):
        l = self.grid.find_pixels_from_hsv(hsv)
        if not len(l):
            return False
        return l[0]
        
    def setattr_all_pixels(self, **kwargs):
        self.add_update_job(self.grid.setattr_all_pixels, **kwargs)
        #self.grid.setattr_all_pixels(**kwargs)
        #self.blit_texture()
    
    def build_hsv_pattern(self, hue=0.):
        for y, row in enumerate(self.grid.pixels):
            for x, pixel in enumerate(row):
                pixel.hue = hue
                pixel.sat = y / float(self.grid.num_rows)
                pixel.val = x / float(self.grid.num_cols)
                #pixel.set_hsv(hue=hue, sat=y / float(self.grid.num_rows), val=x / float(self.grid.num_cols))
                
    def build_rgb_pattern(self):
        for y, row in enumerate(self.grid.pixels):
            for x, pixel in enumerate(row):
                pixel.red = y * 255. / self.grid.num_rows
                pixel.green = (y * -255. / self.grid.num_rows) + 255
                pixel.blue = x * 255. / self.grid.num_cols
    
    def resize(self, **kwargs):
        size = kwargs.get('size')
        size = [int(f) for f in size]
        if size == self.size:
            return
        self.grid.resize(size=size)
        self.size = size
        self.build_texture()
        self.build_test_pattern()
        
    def blit_texture(self, *args, **kwargs):
        a = self.grid.get_ogl_pixel_data(color_format=self.color_format, arraytype=self.arraytype)
        bfr = a.tostring()
        self._texture.blit_buffer(bfr, colorfmt=self.color_format, bufferfmt=self.oglbuffertype)

class ThreadedUpdater(BaseThread):
    def __init__(self, **kwargs):
        kwargs['thread_id'] = 'ThreadedUpdater-%s' % (id(self))
        super(ThreadedUpdater, self).__init__(**kwargs)
        self.job_complete_cb = kwargs.get('job_complete_cb')
        #self.running = threading.Event()
        #self.updating = threading.Event()
        #self.queue = collections.deque()
        
    def add_job(self, cb, **kwargs):
        self.LOG.info('adding: ', cb, kwargs)
        self.insert_threaded_call(cb, **kwargs)
        
    
    def old_add_job(self, cb, **kwargs):
        self.queue.append((cb, kwargs))
        self.updating.set()
        
    def run(self):
        print self._thread_id, ' run'
        super(ThreadedUpdater, self).run()
    def stop(self, **kwargs):
        print self._thread_id, 'stopping'
        super(ThreadedUpdater, self).stop(**kwargs)
        print self._thread_id, 'stopped'
    def old_run(self):
        self.running.set()
        while self.running.isSet():
            self.updating.wait()
            if self.running.isSet():
                self.do_next_job()
                
    def old_stop(self):
        self.running.clear()
        self.updating.set()
        
    def _do_threaded_calls(self):
        results = super(ThreadedUpdater, self)._do_threaded_calls()
        if results is None:
            return
        result, cb, args, kwargs = results
        self.LOG.info('complete: ', cb, args)
        self.job_complete_cb(self, cb, **kwargs)
        
#    def do_next_job(self):
#        if not len(self.queue):
#            self.updating.clear()
#            return
#        cb, kwargs = self.queue.popleft()
#        cb(**kwargs)
#        self.job_complete_cb(self, cb, **kwargs)
