#import cluttergtk
#import clutter
#import gtk
#import pango
from ui_modules import gtk, pango, clutter, cluttergtk

from Bases import BaseObject
import widgets

alignment_map = {'left':pango.ALIGN_LEFT, 'center':pango.ALIGN_CENTER, 'right':pango.ALIGN_RIGHT}

class Scene(BaseObject):
    def __init__(self, **kwargs):
        super(Scene, self).__init__(**kwargs)
        self.register_signal('clicked', 'released')
        self.stage = None
        self.embed = cluttergtk.Embed()
        self.embed.set_size_request(128, 128)
        self.motion_event_id = None  
        
    def on_button_press(self, obj, event):
        self.motion_event_id = self.stage.connect('motion-event', self.on_motion_event)
        self.emit('clicked', scene=self)
        
    def on_button_release(self, obj, event):
        if self.motion_event_id is not None:
            self.stage.disconnect(self.motion_event_id)
            self.motion_event_id = None
        self.emit('released', scene=self)
            
    def on_motion_event(self, obj, event):
        pass
        #print event.x, event.y
    
    def on_stage_resize(self, widget, alloc):
        #print 'alloc:', alloc
        size = [min([alloc.width, alloc.height])] * 2
        stage = self.stage
        self.stage = self.embed.get_stage()
        if self.stage and self.stage != stage:
            self.stage.connect('button-press-event', self.on_button_press)
            self.stage.connect('button-release-event', self.on_button_release)
            self.stage.set_size(128, 128)
            #print 'stagesize:', self.stage.get_size()
            self.stage.show()

class Draggable(clutter.Group):
    def __init__(self, **kwargs):
        super(Draggable, self).__init__()
        if not hasattr(self, 'motion_scale'):
            self.motion_scale = 1.
        self.motion_event_id = None
        self.dragging = False
        self.drag_start = None
        self.set_reactive(True)
        self.limits = None
        self.real_pos = [0, 0]
        self.connect('button-press-event', self.on_button_pressed)
        self.connect('realize', self.on_realize)
        
    def on_realize(self, *args):
        self.get_stage().connect('button-release-event', self.on_button_released)
        stage_size = self.get_stage().get_size()
        size = self.get_size()
        self.size = size
        self.limits = [[-(size[x] / 2), stage_size[x] - (size[x] / 2)] for x in [0, 1]]
        #print 'limits:', self.limits
        self.update_real_pos(self.get_position())
        
    def add(self, actor):
        super(Draggable, self).add(actor)
        actor.connect('button-press-event', self.on_button_pressed)
        
    def on_button_pressed(self, obj, event):
        self.dragging = True
        pos = self.get_position()
        #epos = [coord * self.motion_scale for coord in (event.x, event.y)]
        epos = (event.x, event.y)
        self.drag_offset = [(coord - pos[i]) * self.motion_scale for i, coord in enumerate(epos)]
        #print 'drag_offset = ', self.drag_offset
        id = self.get_stage().connect('motion-event', self.on_motion_event)
        self.motion_event_id = id
        
    def on_button_released(self, obj, event):
        #print 'release'
        if self.dragging:
            self.dragging = False
            self.drag_offset = None
            self.get_stage().disconnect(self.motion_event_id)
            
    def on_motion_event(self, obj, event):
        if self.dragging:
            #epos = [coord * self.motion_scale for coord in (event.x, event.y)]
            epos = (event.x, event.y)
            pos = [(coord - self.drag_offset[i]) * self.motion_scale for i, coord in enumerate(epos)]
            for x, p in enumerate(pos):
                if p < self.limits[x][0]:
                    pos[x] = self.limits[x][0]
                elif p > self.limits[x][1]:
                    pos[x] = self.limits[x][1]
            self.set_position(*pos)
            self.update_real_pos(pos)
            
    def update_real_pos(self, pos):
        self.real_pos = [pos[x] + (self.size[x] / 2) for x in [0, 1]]
        #print 'real: ', self.real_pos
        
    def set_real_pos(self, pos):
        offset = [pos[x] - (self.size[x] / 2) for x in [0, 1]]
        self.set_position(*offset)
        
        
class GraphRect(clutter.Rectangle):
    def __init__(self, **kwargs):
        super(GraphRect, self).__init__()
        self.set_size(*kwargs.get('size', (120, 120)))
        
        props = {'color':clutter.Color(255, 255, 255, 0), 
                 'border-color':clutter.Color(0, 0, 0, 255), 
                 'border-width':1, 
                 'has-border':True}
        
        for key, val in props.iteritems():
            kwargs.setdefault(key, val)
            self.set_property(key, kwargs.get(key))
        

class XYWidget(BaseObject):
    pos_keys = ['x', 'y']
    def __init__(self, **kwargs):
        self._pos = [0.0] * 2
        super(XYWidget, self).__init__(**kwargs)
        self.register_signal('position_changed')
        self.src_object = kwargs.get('src_object')
        self.src_attr = kwargs.get('src_attr')
        self.src_attr_keys = kwargs.get('src_attr_keys', self.pos_keys)
        self.src_signal = kwargs.get('src_signal')
        self.invert_flags = kwargs.get('inverted', [False, True])
        
        self.topwidget = gtk.AspectFrame(label=kwargs.get('label', 'XY'))
        vbox = gtk.VBox()
        self.scene = XYWidgetScene(**kwargs)
        vbox.pack_start(self.scene.embed)
        hbox = gtk.HBox()
        
        self.pos_spins = {}
        for key in ['pos_x', 'pos_y']:
            spin = widgets.SpinBtn(no_frame=True, src_object=self, src_attr=key)
            hbox.pack_start(spin.topwidget)
            self.pos_spins.update({key:spin})
        vbox.pack_start(hbox)
        self.topwidget.add(vbox)
        self.topwidget.connect('size-allocate', self.scene.on_stage_resize)
        self.scene.connect('position_changed', self.on_position_changed)
        if self.src_signal:
            self.src_object.connect(self.src_signal, self.on_src_object_update)
            
    @property
    def pos(self):
        return dict(zip(self.pos_keys, self._pos))
    @pos.setter
    def pos(self, value):
        self._set_pos(**value)
    @property
    def pos_x(self):
        return self._pos[0]
    @pos_x.setter
    def pos_x(self, value):
        self._set_pos(x=value)
    @property
    def pos_y(self):
        return self._pos[1]
    @pos_y.setter
    def pos_y(self, value):
        self._set_pos(y=value)
        
    def _set_pos(self, **kwargs):
        for key, val in kwargs.iteritems():
            i = self.pos_keys.index(key)
            if self.invert_flags[i]:
                val = (val * -1.0) + self.scene.value_range[i][1]
            self._pos[i] = val
        self.scene.set_scaled_position(self._pos)
        self.emit('position_changed', position=self._pos)
        
    def on_position_changed(self, **kwargs):
        pos = kwargs.get('scaled_position')
        for x in [0, 1]:
            if self.invert_flags[x]:
                pos[x] = (pos[x] * -1.0) + self.scene.value_range[x][1]
        for x, key in enumerate(['pos_x', 'pos_y']):
            if int(self.pos_spins[key].adj.get_value()) != int(pos[x]):
                self._pos[x] = pos[x]
                self.pos_spins[key].on_object_value_changed()
        if self.src_object:
            d = {}
            for key, attrkey in zip(self.pos_keys, self.src_attr_keys):
                d[attrkey] = self.pos[key]
            setattr(self.src_object, self.src_attr, d)
        self.emit('position_changed', position=self._pos, widget=self)
        
    def on_src_object_update(self, **kwargs):
        if not self.scene.cursor.dragging:
            pos = getattr(self.src_object, self.src_attr)
            d = {}
            for key, attrkey in zip(self.pos_keys, self.src_attr_keys):
                if attrkey in pos:
                    d[key] = pos[attrkey]
            self._set_pos(**d)

class XYWidgetScene(Scene):
    def __init__(self, **kwargs):
        super(XYWidgetScene, self).__init__(**kwargs)
        self.register_signal('position_changed')
        self.value_range = kwargs.get('value_range', [[0, 100], [0, 100]])
        self.value_max = [x[1] - x[0] for x in self.value_range]
        self.cursor = None
        self.text = None
        
    def on_stage_resize(self, widget, alloc):
        super(XYWidgetScene, self).on_stage_resize(widget, alloc)
        if not self.cursor:
            size = self.stage.get_size()
            self.stage_size = size
            self.add_grid_lines()
            self.cursor = XYCursor(size=(20, 20), motion_cb=self.on_cursor_motion)
            self.stage.add(self.cursor)
            self.cursor.set_real_pos([s / 2 for s in size])
            self.stage.set_color(clutter.Color(0, 0, 0, 255))
            
    def add_grid_lines(self):
        boxsize = [self.stage_size[0] / 4] * 2
        boxes = []
        bgcol = clutter.Color(0, 0, 0, 0)
        fgcol = clutter.Color(128, 128, 128, 255)
        boxkwargs = {'color':bgcol, 'border-color':fgcol, 'size':boxsize}
        group = clutter.Group()
        for x in range(4):
            boxes.append([])
            for y in range(4):
                box = GraphRect(**boxkwargs)
                group.add(box)
                box.set_position(boxsize[0] * x, boxsize[1] * y)
                boxes[x].append(box)
        self.stage.add(group)
        self.grid_group = group
        self.grid_boxes = boxes
        
    def set_scaled_position(self, pos):
        scaled = [pos[x] / self.value_max[x] * self.stage_size[x] for x in [0, 1]]
        #print 'set scaled: ', scaled
        self.cursor.set_real_pos(scaled)
        
    def on_cursor_motion(self, **kwargs):
        pos = kwargs.get('pos')
        scaled = [pos[x] / self.stage_size[x] * self.value_max[x] for x in [0, 1]]
        self.emit('position_changed', position=pos, widget=self, scaled_position=scaled)
    
class XYCursor(Draggable):
    def __init__(self, **kwargs):
        super(XYCursor, self).__init__()
        #self.motion_scale = .5
        self.motion_cb = kwargs.get('motion_cb')
        shape_dict = {'rect':GraphRect}
        kwargs.setdefault('color', clutter.Color(128, 128, 128, 255))
        kwargs.setdefault('border-color', clutter.Color(255, 255, 255, 255))
        self.shape = shape_dict.get(kwargs.get('shape', 'rect'))(**kwargs)
        self.add(self.shape)
        
    def on_motion_event(self, *args):
        super(XYCursor, self).on_motion_event(*args)
        if self.motion_cb is not None:
            self.motion_cb(pos=self.real_pos)

class GraphText(clutter.Group):
    default_size = (60, 24)
    def __init__(self, **kwargs):
        super(GraphText, self).__init__()
        self.box = GraphRect()
        self.add(self.box)
        self.alignment = kwargs.get('alignment', 'left')
        self.text_obj = clutter.Text()
        self.text_obj.set_size(*kwargs.get('size', self.default_size))
        if 'font_size' in kwargs:
            font = self.text_obj.get_font_name()
            size = kwargs.get('font_size')
            self.text_obj.set_font_name(' '.join([font.split(' ')[0], str(size)]))
        self.box.set_size(*kwargs.get('size', self.default_size))
        props = {'color':clutter.Color(0, 0, 0, 255), 
                 'line-alignment':alignment_map.get(self.alignment)}
        for key, val in props.iteritems():
            self.text_obj.set_property(key, val)
        self.set_text(kwargs.get('text', ''))
        self.add(self.text_obj)
        #self.set_size(*kwargs.get('size', (120, 24)))
    def set_text(self, text):
        self.text_obj.set_text(text)
