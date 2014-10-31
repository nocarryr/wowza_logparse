import threading

from ui_modules import gtk, gobject, gdk, pango

from Bases import BaseObject
from Bases.Properties import PropertyConnector
from ...bases import widgets as basewidgets
#from gtksimple import *
import gtksimple

get_gtk2_enum = gtksimple.get_gtk2_enum
get_gtk3_enum = gtksimple.get_gtk3_enum
get_gui_thread = gtksimple.get_gui_thread

import tree
import listmodel

#class Box(gtk.Box):
#    pass

GTK_VERSION = BaseObject().GLOBAL_CONFIG['gtk_version']


class BoxMixin(object):
    def pack_start(self, widget, **kwargs):
        new_kwargs = kwargs.copy()
        new_kwargs.setdefault('expand', False)
        new_kwargs.setdefault('fill', True)
        new_kwargs.setdefault('padding', 1)
        for key in ['xoptions', 'yoptions']:
            if key in new_kwargs:
                del new_kwargs[key]
        args = [new_kwargs.get(key) for key in ['expand', 'fill', 'padding']]
        super(BoxMixin, self).pack_start(widget, *args)
    def pack_end(self, widget, **kwargs):
        new_kwargs = kwargs.copy()
        new_kwargs.setdefault('expand', False)
        new_kwargs.setdefault('fill', True)
        new_kwargs.setdefault('padding', 1)
        for key in ['xoptions', 'yoptions']:
            if key in new_kwargs:
                del new_kwargs[key]
        args = [new_kwargs.get(key) for key in ['expand', 'fill', 'padding']]
        super(BoxMixin, self).pack_end(widget, *args)
        
if GTK_VERSION < 3:
    class VBox(BoxMixin, gtk.VBox):
        pass
    class HBox(BoxMixin, gtk.HBox):
        pass
else:
    class Box(BoxMixin, gtk.Box):
        def __init__(self, *args, **kwargs):
            orientation = getattr(gtk.Orientation, self._orientation.upper())
            #super(Box, self).__init__(orientation)
            gtk.Box.__init__(self, orientation=orientation)
    class VBox(Box):
        _orientation = 'vertical'
    class HBox(Box):
        _orientation = 'horizontal'

attach_keys = ['EXPAND', 'FILL']
if GTK_VERSION < 3:
    attach_vals = [gtk.EXPAND, gtk.FILL]
else:
    attach_vals = [gtk.AttachOptions.EXPAND, gtk.AttachOptions.FILL]
AttachOptions = dict(zip(attach_keys, attach_vals))

class Table(gtk.Table, basewidgets.Table):
    def __init__(self, **kwargs):
        kwargs.setdefault('columns', 2)
        basewidgets.Table.__init__(self, **kwargs)
        if self.obj_sort_attr:
            del kwargs['obj_sort_attr']
        gtk.Table.__init__(self, **kwargs)
        
    def attach(self, *args, **kwargs):
        expand = kwargs.get('expand')
        if expand is not None:
            if expand:
                kwargs.setdefault('xoptions', AttachOptions['EXPAND'] | AttachOptions['FILL'])
                kwargs.setdefault('yoptions', AttachOptions['EXPAND'] | AttachOptions['FILL'])
            del kwargs['expand']
        else:
            kwargs.setdefault('xoptions', AttachOptions['FILL'])
            kwargs.setdefault('yoptions', AttachOptions['FILL'])
        super(Table, self).attach(*args, **kwargs)
    
    def do_add_widget(self, widget, loc, **kwargs):
        for x, prop in enumerate(['n-columns', 'n-rows']):
            if loc[x] > self.get_property(prop):
                self.set_property(prop, loc[x])
        self.attach(widget, loc[1], loc[1]+1, loc[0], loc[0]+1, **kwargs)
        widget.show()
        
    def remove(self, widget):
        gtk.Table.remove(self, widget)
        basewidgets.Table.remove(self, widget)
    
    def do_child_loc_update(self, widget, loc):
        args = [loc[1], loc[1]+1, loc[0], loc[0]+1]
        for x, prop in enumerate(['-'.join([key, 'attach']) for key in ['left', 'right', 'top', 'bottom']]):
            self.child_set_property(widget, prop, args[x])
            
def _set_font_scale(widget, scale):
        attrs = widget.get_attributes()
        if attrs is None:
            attrs = pango.AttrList()
        ## TODO: figure out how pango works now
        #attrs.change(pango.SCALE(scale, 0, 9999))
        #widget.set_attributes(attrs)
        
if GTK_VERSION < 3:
    JustifyOptions = get_gtk2_enum('JUSTIFY')
else:
    JustifyOptions = get_gtk3_enum('Justification')
    
class Label(gtk.Label, gtksimple.LabelMixIn):
    def __init__(self, label=None, **kwargs):
        gtk.Label.__init__(self, label)
        justify = kwargs.get('justification', 'center')
        self.set_justify(justify)
        fscale = kwargs.get('font_scale')
        if fscale:
            self.set_font_scale(fscale)
        self._use_thread_control = kwargs.get('threaded', True)
        self.Property = kwargs.get('Property')
    @gtksimple.ThreadToGtk
    def update_text_from_Property(self, text):
        self._unthreaded_set_text(text)
    def set_text(self, text):
        if self._use_thread_control:
            self._threaded_set_text(text)
        else:
            self._unthreaded_set_text(text)
    @gtksimple.ThreadToGtk
    def _threaded_set_text(self, text):
        gtk.Label.set_text(self, text)
    def _unthreaded_set_text(self, text):
        gtk.Label.set_text(self, text)
    def set_font_scale(self, scale):
        return
        _set_font_scale(self, scale)
    def unlink(self):
        self.Property = None
    def set_justify(self, justify):
        if type(justify) == str:
            justify = JustifyOptions.get(justify.upper())
        if justify == JustifyOptions['LEFT']:
            self.set_alignment(0., .5)
        super(Label, self).set_justify(justify)
    
class Frame(gtk.Frame, gtksimple.LabelMixIn):
    def __init__(self, **kwargs):
        wid_kwargs = {'label':kwargs.get('label', '')}
        super(Frame, self).__init__(**wid_kwargs)
        fscale = kwargs.get('font_scale')
        if fscale:
            self.set_font_scale(fscale)
        if not hasattr(self, 'topwidget'):
            self.topwidget = kwargs.get('topwidget', VBox)()
            self.add(self.topwidget)
        self.Property = kwargs.get('Property')
    def unlink(self):
        self.Property = None
    @gtksimple.ThreadToGtk
    def update_text_from_Property(self, text):
        self.set_label(text)        
    def set_font_scale(self, scale):
        return
        _set_font_scale(self.get_label_widget(), scale)
    def add(self, *args, **kwargs):
        if args[0] != self.topwidget:
            self.topwidget.add(*args, **kwargs)
        else:
            super(Frame, self).add(*args, **kwargs)
    def pack_start(self, *args, **kwargs):
        self.topwidget.pack_start(*args, **kwargs)
    def pack_end(self, *args, **kwargs):
        self.topwidget.pack_end(*args, **kwargs)
    def attach(self, *args, **kwargs):
        self.topwidget.pack_start(*args, **kwargs)
class Expander(gtk.Expander):
    def __init__(self, **kwargs):
        expanded = kwargs.get('expanded', True)
        wid_kwargs = {'label':kwargs.get('label', '')}
        super(Expander, self).__init__(**wid_kwargs)
        fscale = kwargs.get('font_scale')
        if fscale:
            self.set_font_scale(fscale)
        self.topwidget = kwargs.get('topwidget', VBox())
        self.add(self.topwidget)
        self.set_expanded(expanded)
    def set_font_scale(self, scale):
        _set_font_scale(self.get_label_widget(), scale)
    def pack_start(self, *args, **kwargs):
        self.topwidget.pack_start(*args, **kwargs)
    def attach(self, *args, **kwargs):
        self.topwidget.attach(*args, **kwargs)
class ScrolledWindow(gtk.ScrolledWindow):
    def __init__(self, *args, **kwargs):
        super(ScrolledWindow, self).__init__(*args, **kwargs)
        self.add_viewport = kwargs.get('add_viewport', True)
        if self.add_viewport:
            self.viewport = gtk.Viewport()
            self.add(self.viewport)
    def add(self, *args, **kwargs):
        if self.add_viewport and not isinstance(args[0], gtk.Viewport):
            self.viewport.add(*args, **kwargs)
        else:
            super(ScrolledWindow, self).add(*args, **kwargs)
    def pack_start(self, *args, **kwargs):
        if not self.add_viewport:
            return
        self.viewport.add(args[0])
    def remove(self, *args, **kwargs):
        if self.add_viewport:
            self.viewport.remove(args[0])
        else:
            super(ScrolledWindow, self).remove(*args, **kwargs)

class DrawingArea(gtk.DrawingArea):
    pass

class PaneMixin(object):
    def pack_start(self, widget, **kwargs):
        if self.get_child1() is None:
            self.pack1(widget, True, False)
        elif self.get_child2() is None:
            self.pack2(widget, True, False)
    @property
    def normalized_pos(self):
        size = getattr(self.allocation, self.size_attribute)
        if size < 0:
            return 0
        return self.get_position() / float(size)
    @normalized_pos.setter
    def normalized_pos(self, value):
        if value < 0 or value > 1:
            return
        size = getattr(self.get_allocation(), self.size_attribute)
        if size < 0:
            return
        self.set_position(int(value * size))
        
if GTK_VERSION < 3:
    class HPane(PaneMixin, gtk.HPaned):
        size_attribute = 'width'
    class VPane(PaneMixin, gtk.VPaned):
        size_attribute = 'height'
else:
    class Pane(PaneMixin, gtk.Paned):
        def __init__(self, **kwargs):
            orientation = getattr(gtk.Orientation, self._orientation.upper())
            gtk.Paned.__init__(self, orientation=orientation)
    class HPane(Pane):
        size_attribute = 'width'
        _orientation = 'horizontal'
    class VPane(Pane):
        size_attribute = 'height'
        _orientation = 'vertical'

class Notebook(gtk.Notebook):
    def add_page(self, **kwargs):
        widget = kwargs.get('widget')
        label = gtk.Label(kwargs.get('label', ''))
        self.append_page(widget, label)
        
class MenuBar(gtk.MenuBar):
    def __init__(self, **kwargs):
        super(MenuBar, self).__init__()
        self.menu_order = kwargs.get('menu_order')
        self.menu_info = kwargs.get('menu_info')
        for key in self.menu_info.iterkeys():
            val = self.menu_info[key]
            if type(val) == list or type(val) == tuple:
                d = {}
                for s in val:
                    d.update({s:{'name':s}})
                self.menu_info[key] = d
        self.menus = {}
        for key in self.menu_order:
            val = self.menu_info[key]
            self.add_menu(key, **val)
        self.show()
    def add_menu(self, id, **kwargs):
        menu = Menu(menubar=self, name=id, item_info=kwargs)
        self.menus.update({id:menu})
        self.append(menu.menuitem._item)
        
class Menu(object):
    def __init__(self, **kwargs):
        #super(Menu, self).__init__()
        self._menu = gtk.Menu()
        self.menuitem = MenuItem(name=kwargs.get('name'))
        self.menuitem._item.set_submenu(self._menu)
        self.menubar = kwargs.get('menubar')
        self.item_info = kwargs.get('item_info')
        self.items = {}
        for key, val in self.item_info.iteritems():
            self.add_item(key, **val)
    def add_item(self, id, **kwargs):
        item = MenuItem(**kwargs)
        self.items.update({id:item})
        self._menu.append(item._item)

class MenuItem(object):
    def __init__(self, **kwargs):
        self.item_name = kwargs.get('name')
        self._item = gtk.MenuItem(label=self.item_name)
        #super(MenuItem, self).__init__(label=self.item_name)
        self._item.show()


if GTK_VERSION < 3:
    responses = get_gtk2_enum('RESPONSE')
    fc_actions = get_gtk2_enum('FILE_CHOOSER_ACTION')
    filter_flags = get_gtk2_enum('FILE_FILTER')
else:
    responses = get_gtk3_enum('ResponseType')
    fc_actions = get_gtk3_enum('FileChooserAction')
    filter_flags = get_gtk3_enum('FileFilterFlags')

btn_info = {'cancel':(gtk.STOCK_CANCEL, responses['CANCEL']), 
            'open':(gtk.STOCK_OPEN, responses['OK']), 
            'save':(gtk.STOCK_SAVE, responses['OK']), 
            'ok':(gtk.STOCK_OK, responses['ACCEPT'])}
class FileDialog(BaseObject):
    modes = {'open':fc_actions['OPEN'], 
             'save':fc_actions['SAVE'], 
             'select_folder':fc_actions['SELECT_FOLDER'], 
             'create_folder':fc_actions['CREATE_FOLDER']}
    default_buttons = {'open':(btn_info['cancel'] + btn_info['open']), 
                       'save':(btn_info['cancel'] + btn_info['save'])}
    filter_types = ['pattern', 'mime']
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = get_gui_thread()
        super(FileDialog, self).__init__(**kwargs)
        self.register_signal('response')
        self.mode = kwargs.get('mode')
        self.overwrite_confirmation = kwargs.get('overwrite_confirmation', True)
        self.current_folder = kwargs.get('current_folder')
        filters = kwargs.get('filters', {})
        ##{FilterName:[[filter_type, filter_data],...]}
        self.filters = {}
        for key, val in filters.iteritems():
            self.add_filter(key, val)
        dlg_kwargs = {}
        if 'label' in kwargs:
            dlg_kwargs.update({'title':kwargs.get('label')})
        dlg_kwargs.update({'buttons':kwargs.get('buttons', self.default_buttons[self.mode])})
        dlg_kwargs.update({'action':self.modes[self.mode]})
        self.dialog = gtk.FileChooserDialog(**dlg_kwargs)
        for filter in self.filters.itervalues():
            self.dialog.add_filter(filter)
        default_filter = kwargs.get('default_filter')
        if default_filter is not None:
            f = self.filters.get(default_filter)
            self.dialog.set_filter(f)
        if self.current_folder is not None:
            self.dialog.set_current_folder_uri(self.current_folder)
        if 'filename' in kwargs:
            self.dialog.set_filename(kwargs['filename'])
        elif 'current_name' in kwargs:
            self.dialog.set_current_name(kwargs['current_name'])
        self.dialog.set_do_overwrite_confirmation(self.overwrite_confirmation)
        #self.dialog.connect('response', self.on_dialog_response)
        
    def show(self):
        response = self.dialog.run()
        resp_dict = {'dialog':self, 'response':False}
        if response == responses['OK']:
            resp_dict.update({'response':True, 'filename':self.dialog.get_filename(), 'uri':self.dialog.get_uri()})
        #print resp_dict
        self.emit('response', **resp_dict)
        self.dialog.destroy()
        return resp_dict
    
    def add_filter(self, name, filter_data):
        f = gtk.FileFilter()
        f.set_name(name)
        for filter in filter_data:
            if filter[0] == 'pattern':
                f.add_pattern(filter[1])
            elif filter[0] == 'mime':
                f.add_mime_type(filter[1])
            elif filter[0] == 'custom':
                f.add_custom(filter_flags['FILENAME'] | filter_flags['URI'], 
                             *filter[1:])
        self.filters.update({name:f})
        
    def on_dialog_response(self, *args):
        pass
        #print args
        
if GTK_VERSION < 3:
    dlg_flags = get_gtk2_enum('DIALOG')
else:
    dlg_flags = get_gtk3_enum('DialogFlags')
    
class EntryDialog(BaseObject):
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = get_gui_thread()
        super(EntryDialog, self).__init__(**kwargs)
        self.register_signal('response')
        self.title = kwargs.get('title')
        self.message = kwargs.get('message')
        self.entry_text = kwargs.get('entry_text', '')
        if GTK_VERSION < 3:
            dlg_flags = get_gtk2_enum('DIALOG')
        else:
            dlg_flags = get_gtk3_enum('DialogFlags')
        #self.dialog = gtk.Dialog(self.title, None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, 
        #                         (btn_info['ok'] + btn_info['cancel']))
        self.dialog = gtk.Dialog(self.title, None, dlg_flags['MODAL'] | dlg_flags['DESTROY_WITH_PARENT'], 
                                 (btn_info['ok'] + btn_info['cancel']))
        self.dialog.vbox.pack_start(Label(self.message))
        self.entry = Entry(no_frame=True)
        self.entry.set_widget_text(self.entry_text)
        self.dialog.action_area.pack_start(self.entry.topwidget)
        self.dialog.show_all()
    def run(self):
        response = self.dialog.run()
        if response == btn_info['ok'][1]:
            value = self.entry.get_widget_text()
        else:
            value = None
        self.emit('response', dialog=self, value=value)
        self.dialog.destroy()
        
class ColorSelection(gtksimple.Color):
    def __init__(self, **kwargs):
        super(ColorSelection, self).__init__(**kwargs)
        kwargs.setdefault('label', 'Color')
        self.topwidget = Frame(**kwargs)
        self.topwidget.pack_start(self.widget)
    
    def unlink(self):
        super(ColorSelection, self).unlink()
        for w in self.spinbtns.itervalues():
            w.unlink()
    
    def hide_extra_widgets(self, widget=None):
        if widget is None:
            widget = self._widget
        flag = False
        if widget in self.widgets_to_show.values():
            flag = True
        #if widget in [w.get_parent() for w in self.widgets_to_show.values()]:
        #    flag = True
        for w in self.widgets_to_show.itervalues():
            if widget.is_ancestor(w) or w.is_ancestor(widget):
                flag = True
        if not flag:
            widget.hide()
            return
        if not hasattr(widget, 'get_children'):
            return
        children = widget.get_children()
        for child in children:
            self.hide_extra_widgets(child)
        
    def setup_widgets(self, **kwargs):
        widget = gtk.ColorSelection()
        d = {}
        d['hsv'] = widget.get_children()[0].get_children()[0].get_children()[0]
        d['display'] = widget.get_children()[0].get_children()[0].get_children()[1].get_children()[0].get_children()[0]
        d['picker'] = widget.get_children()[0].get_children()[0].get_children()[1].get_children()[1]
        
        #for w in d.itervalues():
        #    w.get_parent().remove(w)
        #d['display'].remove(d['display'].get_children()[0])
        self.widgets_to_show = d

        vbox = VBox()
        vbox.pack_start(widget, expand=True)
        #vbox.pack_start(d['hsv'], expand=True)
        #hbox = HBox()
        #for key in ['display', 'picker']:
        #    hbox.pack_start(d[key], expand=True)
        #vbox.pack_start(hbox, expand=True)
        self.spinbtns = {}
        vbox2 = VBox()
        spinhbox = [HBox(), HBox()]
        for i, keys in enumerate([['red', 'green', 'blue'], ['hue', 'sat', 'val']]):
            for key in keys:
                w = SpinBtn(label=key, Property=(self.color, key))
                if key == 'hue':
                    w.widget.set_wrap(True)
                spinhbox[i].pack_start(w.topwidget)
                self.spinbtns[key] = w
            vbox2.pack_start(spinhbox[i])
        vbox.pack_start(vbox2, expand=False)

        self.widget = vbox
        self._widget = widget
        self.hsv_widget = d['hsv']
        self._widget.connect('color-changed', self.on_widget_update)
        self._widget.connect('show', self.on_widget_show)
        
    def get_widget_color(self):
        return self.hsv_widget.get_color()
        #return self.widget.get_current_color()
    
    @gtksimple.ThreadToGtk
    def set_widget_color(self, hsv):
        self.hsv_widget.set_color(*hsv)
        
    def on_widget_show(self, *args):
        self.hide_extra_widgets()
        
    @property
    def is_adjusting(self):
        if hasattr(self, '_widget'):
            return self._widget.is_adjusting()
        return False
    
class ColorBtn(gtksimple.Color):
    def __init__(self, **kwargs):
        self.gcolor = gtk.gdk.Color(0, 0, 0)
        super(ColorBtn, self).__init__(**kwargs)
        self.topwidget = self.widget
        
    def setup_widgets(self, **kwargs):
        self.widget = ColorBtnButton()
        
    def get_widget_color(self):
        gcolor = self.widget.get_color()
        return list((getattr(gcolor, key) for key in ['hue', 'saturation', 'value']))
    
    @gtksimple.ThreadToGtk
    def set_widget_color(self, hsv):
        rgb = self.color.rgb_seq
        gcolor = self.gcolor
        for i, key in enumerate(['red', 'green', 'blue']):
            setattr(gcolor, key, rgb[i] * 65535)
        #gtksimple.thread_to_gtk(self._do_set_color, self.gcolor)
        self.widget.set_color(gcolor)
        
    def _do_set_color(self, *args, **kwargs):
        self.widget.set_color(*args, **kwargs)
        
    @property
    def is_adjusting(self):
        # TODO: make it find the colorselection.is_adjusting value
        return False
        
class ColorBtnButton(gtk.ColorButton):
    def __init__(self, **kwargs):
        super(ColorBtnButton, self).__init__()
        
class oldColorBtnButton(gtk.Button):
    #bg_states = [getattr(gtk.StateType, key) for key in ['NORMAL', 'PRELIGHT']]
    #bg_states = gtk.StateFlags.NORMAL | gtk.StateFlags.PRELIGHT
    def __init__(self, **kwargs):
        super(ColorBtnButton, self).__init__()
        state_keys = [key for key in dir(gtk.StateFlags) if key.isupper()]
        f = gtk.StateFlags(0)
        for key in state_keys:
            f |= getattr(gtk.StateFlags, key)
        self.bg_states = f
        #print self.bg_states
        self.set_property('height-request', 24)
        self.gc = None
        self.align = gtk.Alignment(xscale=1., yscale=1.)
        self.align.set_property('height-request', 24)
        self.drawing = gtk.DrawingArea()
        #self.drawing.connect('expose-event', self._on_expose)
        #gcolor = gtk.gdk.Color(0, 0, 0)
        self.set_color([0., 0., 0.])
        self.align.add(self.drawing)
        self.add(self.align)
        
        
    def _on_expose(self, *args):
#        h = self.get_allocation().height
#        self.remove(self.get_children()[0])
#        self.add(self.align)
#        self.align.show_all()
#        rect = self.get_allocation()
#        rect.height = h
#        self.allocation = rect
#        self.align.allocation = rect
        
        
        self.gc = self.drawing.window.new_gc()#function=gtk.gdk.CLEAR)
        gcolor = gtk.gdk.color_from_hsv(0., 1., 1.)
        self.gc.set_foreground(gcolor)
        #self.gc.set_background(gtk.gdk.Color())
        self.draw_rect()
        
        
    def draw_rect(self):
        #rect = self.drawing.allocation
        rect = self.drawing.window.get_size()
        #l = [getattr(rect, key) for key in ['x', 'y', 'width', 'height']]
        self.drawing.window.draw_rectangle(self.gc, True, 0, 0, *[int(v / 2.) for v in rect])#0, 0, rect.width, rect.height)
        
    def set_color(self, rgb):
        #if self.gc is None:
        #    return
        #gcolor = gtk.gdk.color_from_hsv(*hsv)
        #l = [getattr(gcolor, key) / 65536. for key in ['red', 'green', 'blue']]
        #l.append(1.)
        rgb = rgb[:]
        rgb.append(1.)
        grgba = gdk.RGBA(*rgb)
        #print 'colorbtn set: ', rgb, grgba
        self.drawing.override_color(self.bg_states, grgba)
        #self.gc.set_background(gcolor)
        #self.gc.set_foreground(gcolor)
        #self.draw_rect()
        #print 'w alloc=%s, align alloc=%s, dwg alloc=%s, dwg size=%s, color=%s' % (self.allocation, self.align.allocation, self.drawing.allocation, self.drawing.window.get_size(), gcolor)

class Entry(gtksimple.EntryBuffer):
    def setup_widgets(self, **kwargs):
        self.widget = gtk.Entry()
        self.widget.connect('activate', self.on_widget_value_changed)
        if kwargs.get('no_frame', False):
            self.topwidget = self.widget
        else:
            self.topwidget = Frame(label=self.name)
            self.topwidget.pack_start(self.widget)
    def get_widget_text(self):
        return self.widget.get_text()
    def set_widget_text(self, text):
        if text is None:
            text = ''
        self.widget.set_text(text)
        
class Text(gtksimple.TextBuffer):
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', '')
        self.topwidget = Frame(label=self.name, topwidget=gtk.ScrolledWindow)
        kwargs.setdefault('widget', gtk.TextView())
        super(Text, self).__init__(**kwargs)
        #expand = kwargs.get('expand', True)
        self.topwidget.add(self.widget)

class Tree(tree.TreeViewConnector):
    def __init__(self, **kwargs):
        super(Tree, self).__init__(**kwargs)
        self.name = kwargs.get('name', '')
        self.topwidget = Frame(label=self.name, topwidget=ScrolledWindow)
        #self.scrolled_win = ScrolledWindow()
        #self.scrolled_win.add(self.widget)
        self.topwidget.topwidget.add(self.widget)

class SpinBtn(gtksimple.Spin):
    def __init__(self, **kwargs):
        super(SpinBtn, self).__init__(**kwargs)
        if kwargs.get('no_frame', False):
            self.topwidget = self.widget
        else:
            self.topwidget = Frame(label=kwargs.get('label', ''))
            self.topwidget.pack_start(self.widget)
    def setup_widgets(self, **kwargs):
        if not hasattr(self, 'widget'):
            self.widget = kwargs.get('widget', gtk.SpinButton())
        self.adj = gtk.Adjustment()
        self.adj.set_property('step-increment', 1)
        self.widget.set_adjustment(self.adj)
        self.adj.connect('value-changed', self.on_widget_value_changed)
    def set_widget_range(self):
        if self.value_type == int:
            self.widget.set_digits(0)
            step = 1
        else:
            self.widget.set_digits(3)
            min, max = self.value_range
            step = (max - min) / 100.
            if step > 1:
                step = 1
        #self.adj.lower, self.adj.upper = self.value_range
        keys = ['lower', 'upper', 'step-increment']
        vals = self.value_range[:]
        vals.append(step)
        for key, val in zip(keys, vals):
            self.adj.set_property(key, val)
        
    @gtksimple.ThreadToGtk
    def set_widget_value(self, value):
        #gtksimple.thread_to_gtk(self._do_set_widget_value, value)
        if value is not None:
            self.widget_value_set_by_program = True
            self.adj.set_value(value)
            self.widget_value_set_by_program = False
            
    def get_widget_value(self):
        return self.adj.get_value()

class RadioBtn(gtksimple.Radio):
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', kwargs.get('label', ''))
        self.topwidget = Frame(label=self.name)
        super(RadioBtn, self).__init__(**kwargs)
    def build_widget(self, key):
        w = super(RadioBtn, self).build_widget(key)
        self.topwidget.pack_start(w)
        return w
    def attach_Property(self, prop):
        super(RadioBtn, self).attach_Property(prop)
        if self.name == '':
            self.topwidget.set_label(prop.name)
            
class TreeList(listmodel.ListModelTree):
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', '')
        self.topwidget = Frame(label=self.name)
        super(TreeList, self).__init__(**kwargs)
        self.scrolled_win = ScrolledWindow()
        self.scrolled_win.add(self.widget)
        self.topwidget.pack_start(self.scrolled_win, expand=True)
    
class TreeView(BaseObject):
    _Properties = {'selected':dict(ignore_type=True)}
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = get_gui_thread()
        super(TreeView, self).__init__(**kwargs)
        self._model = None
        self.selection_set_by_property = False
        self.selection_set_by_widget = False
        self.name = kwargs.get('name', '')
        self.id = kwargs.get('id', id(self))
        self.model = kwargs.get('model')
        self.topwidget = Frame(label=self.name)
        self.widget = gtk.TreeView()
        self.widget.get_selection().connect('changed', self.on_widget_sel_changed)
        self.scrolled_win = ScrolledWindow()
        self.scrolled_win.add(self.widget)
        self.topwidget.pack_start(self.scrolled_win, expand=True)
        self.bind(selected=self._on_selected_set)
    def unlink(self):
        super(TreeView, self).unlink()
        if self.model is not None:
            self.model.unbind(self)
    @property
    def model(self):
        return self._model
    @model.setter
    def model(self, value):
        self._model = value
        if self.model is not None:
            self.model.bind(obj_added=self.on_model_obj_added, 
                            obj_removed=self.on_model_obj_removed)
    def on_widget_sel_changed(self, treesel):
        if not self.model:
            return
        if self.selection_set_by_property:
            return
        iter = treesel.get_selected()[1]
        if iter is not None:
            key = self.model.sorted_store[iter][0]
        else:
            key = None
        self.selection_set_by_widget = True
        self.selected = key
        self.selection_set_by_widget = False
    def _on_selected_set(self, **kwargs):
        if not self.model:
            return
        if self.selection_set_by_widget:
            return
        key = kwargs.get('value')
        treesel = self.widget.get_selection()
        self.selection_set_by_property = True
        if key is None:
            treesel.unselect_all()
        else:
            modelobj = self.model.child_obj.get(key)
            if modelobj is None:
                #self.selected = None
                return
            path = self.model.store.get_path(modelobj.iter)
            s_path = self.model.sorted_store.convert_child_path_to_path(path)
            s_iter = self.model.sorted_store.get_iter(path)
            treesel.select_iter(s_iter)
        self.selection_set_by_property = False
    def on_model_obj_added(self, **kwargs):
        key = kwargs.get('id')
        if key == self.selected:
            self._on_selected_set(value=self.selected)
    def on_model_obj_removed(self, **kwargs):
        key = kwargs.get('id')
        if key == self.selected:
            self.selected = None

class Combo(listmodel.ListModelCombo):
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', '')
        #kwargs.setdefault('list_types', [str])
        #kwargs.setdefault('widget', gtk.ComboBox())
        super(Combo, self).__init__(**kwargs)
        if kwargs.get('no_frame', False):
            self.topwidget = self.widget
        else:
            self.topwidget = Frame(label=self.name)
            self.topwidget.pack_start(self.widget)
            
class Button(gtk.Button):
    pass
    
class ToggleBtn(gtksimple.Toggle):
    def __init__(self, **kwargs):
        super(ToggleBtn, self).__init__(**kwargs)
        #self.topwidget = VBox()
        #self.topwidget.pack_start(self.widget)
    def setup_widgets(self, **kwargs):
        self.widget = gtk.ToggleButton(label=kwargs.get('label', ''))
        self.widget_packing = {'expand':False}
        id = self.widget.connect('toggled', self.on_widget_toggled)
        self.widget_signals.append(id)
    def get_widget_state(self):
        return self.widget.get_active()
    def set_widget_state(self, state):
        self.widget.set_active(state)
        
class CheckBox(gtk.CheckButton):
    @property
    def state(self):
        return self.get_active()
    @state.setter
    def state(self, value):
        self.set_active(value)

class Slider(gtksimple.Fader):
    def __init__(self, **kwargs):
        #self.name = kwargs.get('name', kwargs.get('label', ''))
        label = kwargs.get('label')
        if label is not None:
            kwargs.setdefault('name', label)
        self.topwidget = Frame(label='')
        super(Slider, self).__init__(**kwargs)
        self.topwidget.pack_start(self.widget, expand=True)
        self.widget.set_digits(2)
    def _on_name_set(self, **kwargs):
        self.topwidget.set_label(kwargs.get('value'))
        super(Slider, self)._on_name_set(**kwargs)
        
class VSlider(Slider):
    def __init__(self, **kwargs):
        kwargs.setdefault('fader_type', 'VSlider')
        super(VSlider, self).__init__(**kwargs)
        self.widget_packing.update({'xoptions':AttachOptions['FILL'], 
                                    'yoptions':AttachOptions['EXPAND'] | AttachOptions['FILL']})
        self.widget.set_property('inverted', True)
        #self.widget.set_property('width-request', 40)
        #self.widget.set_property('height-request', 128)
        
class HSlider(Slider):
    def __init__(self, **kwargs):
        kwargs.setdefault('fader_type', 'HSlider')
        super(HSlider, self).__init__(**kwargs)
        self.widget_packing.update({'xoptions':AttachOptions['EXPAND'] | AttachOptions['FILL'], 
                                    'yoptions':AttachOptions['FILL']})
        #self.widget.set_property('width-request', 128)
        #self.widget.set_property('height-request', 40)

class ProgressBar(BaseObject, PropertyConnector):
    _Properties = {'value':dict(default=0., min=0., max=1., quiet=True)}
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = get_gui_thread()
        super(ProgressBar, self).__init__(**kwargs)
        self.widget = gtk.ProgressBar()
        self.topwidget = self.widget
        self.bind(value=self._on_value_set)
    def attach_Property(self, prop):
        super(ProgressBar, self).attach_Property(prop)
        self.update_Property_value()
    def unlink_Property(self, prop):
        super(ProgressBar, self).unlink_Property(prop)
        self.value = 0.
    def on_Property_value_changed(self, **kwargs):
        self.update_Property_value()
    def update_Property_value(self):
        prop = self.Property
        if prop is None or prop.value is None:
            value = 0.
        else:
            value = prop.normalized_and_offset
        self.Properties['value'].normalized_and_offset = value
    def _on_value_set(self, **kwargs):
        value = kwargs.get('value')
        self.widget.set_fraction(value)
        if self.Property is not None:
            self.widget.set_text('%s' % (self.Property.value))
        else:
            self.widget.set_text('')
            
class HProgressBar(ProgressBar):
    def __init__(self, **kwargs):
        super(HProgressBar, self).__init__(**kwargs)
        self.widget.set_orientation(gtk.Orientation.HORIZONTAL)
        
class VProgressBar(ProgressBar):
    def __init__(self, **kwargs):
        super(VProgressBar, self).__init__(**kwargs)
        self.widget.set_orientation(gtk.Orientation.VERTICAL)

class XYSlider(BaseObject, PropertyConnector):
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = get_gui_thread()
        self._attribute = None
        super(XYSlider, self).__init__(**kwargs)
        self.value_obj = {}
        self.sliders = {}
        self.spins = {}
        for key, cls in zip(['pan', 'tilt'], [HSlider, VSlider]):
            obj = ValueObject(Property=self.Property, prop_key=key)
            w = cls()#Property=(obj, 'value'))
            self.sliders[key] = w
            self.value_obj[key] = obj
            w.widget.get_parent().remove(w.widget)
            spin = SpinBtn(label=key)
            self.spins[key] = spin
        self.Property = kwargs.get('Property')
        self.topwidget = Frame(label=kwargs.get('label', 'XY'))
        self.table = Table(rows=3, columns=3, homogeneous=True)
        self.table.attach(self.spins['pan'].topwidget, 0, 1, 0, 1, expand=True)
        self.table.attach(self.sliders['pan'].widget, 0, 2, 2, 3, expand=True)
        self.table.attach(self.spins['tilt'].topwidget, 1, 2, 0, 1, expand=True)
        self.table.attach(self.sliders['tilt'].widget, 2, 3, 0, 2, expand=True)
        self.topwidget.pack_start(self.table, expand=True)
        self.topwidget.show_all()
        
    def unlink(self):
        super(XYSlider, self).unlink()
        self.Property = None
        
    def attach_Property(self, prop):
        super(XYSlider, self).attach_Property(prop)
        for obj in self.value_obj.itervalues():
            obj.Property = prop
        for key, w in self.sliders.iteritems():
            prop = (self.value_obj[key], 'value')
            w.Property = prop
            s = self.spins[key]
            s.Property = prop
            
    def unlink_Property(self, prop):
        super(XYSlider, self).unlink_Property(prop)
        for w in self.sliders.itervalues():
            w.Property = None
        for w in self.spins.itervalues():
            w.Property = None
        for obj in self.value_obj.itervalues():
            obj.Property = None

class ValueObject(BaseObject, PropertyConnector):
    _Properties = {'value':dict(ignore_type=True, ignore_range=True)}
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = get_gui_thread()
        self._update = False
        super(ValueObject, self).__init__(**kwargs)
        self.prop_key = kwargs.get('prop_key')
        self.Property = kwargs.get('Property')
        self.bind(value=self.on_own_value_set)
        
    def attach_Property(self, prop):
        super(ValueObject, self).attach_Property(prop)
        myprop = self.Properties['value']
        myprop.type = type(self.get_Property_value()[self.prop_key])
        myprop.min = prop.min[self.prop_key]
        myprop.max = prop.max[self.prop_key]
        myprop.value = self.get_Property_value()[self.prop_key]
            
#    def get_Property_value(self):
#        return super(ValueObject, self).get_Property_value()[self.prop_key]
#    def set_Property_value(self, value):
#        value = {self.prop_key:value}
#        super(ValueObject, self).set_Property_value(value)
        
    def on_Property_value_changed(self, **kwargs):
        old = kwargs.get('old')[self.prop_key]
        value = kwargs.get('value')[self.prop_key]
        if self._update or old == value:
            return
        self.value = value
        
    def on_own_value_set(self, **kwargs):
        if self.value is None:
            return
        self._update = True
        propval = self.get_Property_value()
        propval[self.prop_key] = self.value
        #self.set_Property_value(self.value)
        self._update = False
    
class CenteringSlider(gtksimple.Fader):
    def __init__(self, **kwargs):
        self.release_timer = None
        kwargs.setdefault('adj_kwargs', {'lower':-100., 'upper':100.})
        super(CenteringSlider, self).__init__(**kwargs)
        self.topwidget = Frame(label=self.attribute.name)
        self.topwidget.pack_start(self.widget, expand=True)
        self.widget.set_digits(0)
    def on_widget_button_press(self, *args):
        if self.release_timer:
            self.release_timer.cancel()
            self.release_timer = None
        super(CenteringSlider, self).on_widget_button_press(*args)
        
    def on_widget_button_release(self, *args):
        self.release_timer = threading.Timer(.1, self.on_release_timer)
        self.release_timer.start()
        super(CenteringSlider, self).on_widget_button_release(*args)
        
    def on_release_timer(self):
        self.release_timer = None
        self.attribute.value = 0.
        
class CenteringVSlider(CenteringSlider):
    def __init__(self, **kwargs):
        kwargs.setdefault('fader_type', 'VSlider')
        super(CenteringVSlider, self).__init__(**kwargs)
        self.widget_packing.update({'xoptions':gtk.AttachOptions.FILL, 
                                    'yoptions':gtk.AttachOptions.EXPAND | gtk.AttachOptions.FILL})
        self.widget.set_property('inverted', True)
class CenteringHSlider(CenteringSlider):
    def __init__(self, **kwargs):
        kwargs.setdefault('fader_type', 'HSlider')
        super(CenteringHSlider, self).__init__(**kwargs)
        self.widget_packing.update({'xoptions':gtk.AttachOptions.EXPAND | gtk.AttachOptions.FILL, 
                                    'yoptions':gtk.AttachOptions.FILL})
    

def XYWidget(**kwargs):
    import clutter_bases
    return clutter_bases.XYWidget(**kwargs)
    
class XYShuttle(BaseObject):
    pos_keys = ['x', 'y']
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = get_gui_thread()
        self._widget_pos = dict(zip([key for key in self.pos_keys], [50., 50.]))
        super(XYShuttle, self).__init__(**kwargs)
        self.MainController = kwargs.get('MainController')
        self.src_object = kwargs.get('src_object')
        self.src_attr = kwargs.get('src_attr')
        self.src_signal = kwargs.get('src_signal')
        self.value_objects = {}
        group = self.src_object.name
        self.shuttle = self.MainController.EffectsSystem.add_shuttle(group_names=[self.src_object.name])
        self.shuttle.add_obj(self.src_object)
        self.xywidget = XYWidget(src_object=self, src_attr='widget_pos', 
                                 label=kwargs.get('label', ''), value_range=[[-100, 100], [-100, 100]])
        self.topwidget = self.xywidget.topwidget
        self.xywidget.connect('position_changed', self.on_widget_pos_changed)
        self.xywidget.scene.connect('clicked', self.on_widget_clicked)
        self.xywidget.scene.connect('released', self.on_widget_released)
        
    @property
    def widget_pos(self):
        return self._widget_pos
    @widget_pos.setter
    def widget_pos(self, value):
        for key, val in value.iteritems():
            if val != self._widget_pos[key]:
                self._widget_pos.update({key:val})
                
    def set_expression(self, **kwargs):
        d = {}
        for key in self.pos_keys:
            pos = self.widget_pos[key]
            inc = (pos - 50) / 10
            comp = ''
            zero = False
            if inc == 0:
                zero = True
            elif inc > 0:
                comp = '<'
            else:
                comp = '>'
                
            s = '%(getv)s + %(inc)s if %(getv)s + %(inc)s %(comp)s %(getv)s' % {'getv':'self.get_object_value()', 'inc':inc, 'comp':comp}
            if zero:
                s = 'self.get_object_value()'
            #print key, s
            d[key] = s
        objkey = self.src_object.id
        self.shuttle.effects['Functional'].set_expression(objkey=objkey, expression=d)
        
    def on_widget_clicked(self, **kwargs):
        self.set_expression()
        s = self.shuttle.sequencer
        if not s.state:
            s.start()
        
    def on_widget_released(self, **kwargs):
        s = self.shuttle.sequencer
        if s.state:
            s.stop()
        
    def on_widget_pos_changed(self, **kwargs):
        self.set_expression()
        
class XYValueObject(BaseObject):
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = get_gui_thread()
        self._value = None
        super(XYValueObject, self).__init__(**kwargs)
        self.id = id(self)
        self.value_min = kwargs.get('value_min')
        self.value_max = kwargs.get('value_max')
        self.src_object = kwargs.get('src_object')
        self.src_attr = kwargs.get('src_attr')
        self.src_attr_key = kwargs.get('src_attr_key')
        self._value = self.get_object_value()
        self.src_object.connect(self.src_signal, self.on_object_update)
    def unlink(self):
        self.src_object.disconnect(callback=self.on_object_update)
        super(XYValueObject, self).unlink()
    @property
    def value(self):
        return self._value
    @value.setter
    def value(self, value):
        if value != self._value:
            #self._value = value
            self.set_object_value(value)
    def get_object_value(self):
        return getattr(self.src_object, self.src_attr)[self.src_attr_key]
    def set_object_value(self, value):
        setattr(self.src_object, self.src_attr, {self.src_attr_key:value})
    def on_object_update(self, **kwargs):
        self._value = self.get_object_value()

def get_widget_classes():
    return {'ToggleBtn':ToggleBtn, 'Radio':RadioBtn, 'VSlider':VSlider, 
            'HSlider':HSlider, 'Dial':HSlider, 'MenuBar':MenuBar}
def get_container_classes():
    return {'VBox':VBox, 'HBox':HBox, 'Table':Table, 'Frame':Frame, 
            'Expander':Expander, 'ScrolledWindow':ScrolledWindow, 'Notebook':Notebook}
