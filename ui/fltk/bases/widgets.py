from ui_modules import fltk

from Bases import BaseObject
from Bases.SignalDispatcher import dispatcher

import fltksimple

gui_thread = BaseObject().GLOBAL_CONFIG.get('GUIThread')

def check_init_size(*args, **kwargs):
    if len(args) >= 4 and False not in [type(arg) == int for arg in args[:4]]:
        position = args[:2]
        size = args[2:]
    else:
        position = [0, 0]
        size = [0, 0]
    kwargs.setdefault('position', position)
    kwargs.setdefault('size', size)
    return position + size
    
def format_size_args(**kwargs):
    position = list(kwargs.get('position', [0, 0]))
    size = list(kwargs.get('size', [0, 0]))
    return position + size
    
class DimensionMixin(object):
    @property
    def widget_position(self):
        w = self._get_widget_obj()
        return [w.x(), w.y()]
    @widget_position.setter
    def widget_position(self, value):
        w = self._get_widget_obj()
        w.position(*value)
    @property
    def widget_size(self):
        w = self._get_widget_obj()
        return [w.w(), w.h()]
    @widget_size.setter
    def widget_size(self, value):
        w = self._get_widget_obj()
        w.size(*value)
    def _get_widget_obj(self):
        if isinstance(self, fltk.Fl_Widget):
            w = self
        elif hasattr(self, 'topwidget'):
            w = self.topwidget
        elif hasattr(self, 'widget'):
            w = self.widget
        return w
    
class Window(fltk.Fl_Window):#, dispatcher):
    def __init__(self, *args):
        self.ParentEmissionThread = gui_thread
        #self.register_signal('resize')
        super(Window, self).__init__(*args)
        self.end()
        
#    def resize(self, *args):
#        print 'window resize: ', args
#        super(Window, self).resize(*args)
#        self.emit('resize', position=args[:2], size=args[2:])
    
class Box(fltk.Fl_Pack, DimensionMixin):
    def __init__(self, *args, **kwargs):
        check_init_size(*args, **kwargs)
        wargs = format_size_args(**kwargs)
        super(Box, self).__init__(*wargs)
        self.end()
        self.type(getattr(self.__class__, self._orientation.upper()))
        #print 'box init: ', [self.x(), self.y()], [self.w(), self.h()], self.type()
    def pack_start(self, widget, **kwargs):
        self.insert(widget, self.children() + 1)
        p = self.parent()
        if p is not None:
            p.redraw()
        #widget.show()
        self.redraw()
        widget.redraw()
    
    
class VBox(Box):
    _orientation = 'vertical'
#    def add(self, widget, **kwargs):
#        size = widget.widget_size
#        position = [0, 0]
#        count = self.children()
#        size[0] = self.widget_size[0]
#        if count == 0:
#            size[1] = self.widget_size[1]
#        else:
#            last_child = self.child(count-1)
#            position[1] = last_child.y() + last_child.h()
#            size[1] = self.widget_size[1] - position[1]
#        widget.position(*position)
#        widget.size(*size)
#        return super(VBox, self).add(widget)
class HBox(Box):
    _orientation = 'horizontal'
    
class Button(fltk.Fl_Button, dispatcher, DimensionMixin):
    def __init__(self, *args, **kwargs):
        print 'button init start: ', args, kwargs
        check_init_size(*args, **kwargs)
        wargs = format_size_args(**kwargs)
        label = None
        if len(args) == 5:
            label = args[4]
        if type(label) != str:
            label = kwargs.get('label', '')
        wargs.append(label)
        print 'button about to init superclass: ', wargs
        super(Button, self).__init__(*wargs)
        print 'button superclass init: ', wargs
        self.register_signal('clicked')
        self.callback(self._on_callback)
    def _on_callback(self, *args):
        self.emit('clicked', widget=self)
    
    
class ToggleBtn(fltksimple.Toggle, DimensionMixin):
    def __init__(self, *args, **kwargs):
        check_init_size(*args, **kwargs)
        super(ToggleBtn, self).__init__(**kwargs)
    def setup_widgets(self, **kwargs):
        wargs = format_size_args(**kwargs)
        wargs.append(kwargs.get('label', ''))
        self.widget = fltk.Fl_Toggle_Button(*wargs)
        self.widget.callback(self.on_widget_toggled)
    def get_widget_state(self):
        return self.widget.value() == 1
    def set_widget_state(self, state):
        if state:
            self.widget.set()
        else:
            self.widget.clear()
            
