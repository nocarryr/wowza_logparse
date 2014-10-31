class Table(object):
    def __init__(self, **kwargs):
        self.obj_sort_attr = kwargs.get('obj_sort_attr')
        for key in ['obj_sort_attr']:
            if key in kwargs:
                del kwargs[key]
        self._child_objects = {}
        self._child_widgets = {}
        self._child_locations = {}
        self._child_kwargs = {}
        
    def update_object_key(self, obj, oldkey):
        d = self._child_objects.get(oldkey)
        if d is None:
            return
        new_kwargs = {}
        kwargmap = {'widget_attr':'attr', 'pack_kwargs':'kwargs'}
        for k, v in kwargmap.iteritems():
            new_kwargs[k] = d[v]
        self.remove_child_object(oldkey)
        self.add_object(obj, **new_kwargs)
        
    def add_object(self, obj, **kwargs):
        attr = kwargs.get('widget_attr', 'topwidget')
        pack_kwargs = kwargs.get('pack_kwargs', {})
        key = getattr(obj, self.obj_sort_attr)
        if key in self._child_objects:
            attr = self._child_objects[key]['attr']
            pack_kwargs = self._child_objects[key]['kwargs']
            self.remove_child_object(key)
        if len(self._child_objects) == 0:
            need_sort = False
        else:
            need_sort = key < max(self._child_objects.keys())
        #print 'need_sort=', need_sort
        self._child_objects.update({key:dict(obj=obj, attr=attr, kwargs=pack_kwargs)})
        widget = getattr(obj, attr)
        if True:#need_sort:
            #self._child_kwargs.update({id(widget):pack_kwargs})
            self.pack_start(widget, **pack_kwargs)
            self.update_child_objects()
        else:
            self.pack_start(widget, **pack_kwargs)
            
    def remove_child_object(self, key):
        obj = self._child_objects.get(key)
        if obj is not None:
            self.remove(getattr(obj['obj'], obj['attr']))
            del self._child_objects[key]
            self.update_child_objects()
        
    def update_child_objects(self):
        l = [getattr(obj['obj'], obj['attr']) for obj in self._child_objects.values()]
        self.resort_children(l)
        
    def pack_start(self, *args, **kwargs):
        self.append_widget(*args, **kwargs)
        
    def pack_end(self, *args, **kwargs):
        self.append_widget(*args, **kwargs)
        
    def append_widget(self, *args, **kwargs):
        if len(args) < 5:
            widget = args[0]
            loc = self.find_next_location(self._child_widgets)
            #self.attach(widget, loc[1], loc[1]+1, loc[0], loc[0]+1, **kwargs) 
            self.do_add_widget(widget, loc, **kwargs)
            w_id = id(widget)
            self._child_widgets.update({loc:widget})
            self._child_locations.update({w_id:loc})
            self._child_kwargs.update({w_id:kwargs})
        
    def find_next_location(self, d):
        n_col = self.get_property('n-columns')
        n_row = self.get_property('n-rows')
        loc = None
        for row in range(n_row):
            for col in range(n_col):
                if (row, col) not in d:
                    loc = (row, col)
                    break
            if loc is not None:
                break
        if loc is None:
            loc = (n_row+1, col)
        return loc
        
    def remove(self, widget):
        w_id = id(widget)
        loc = self._child_locations.get(w_id)
        if loc:
            del self._child_widgets[loc]
            del self._child_locations[w_id]
            del self._child_kwargs[w_id]
        else:
            self.LOG.warning('table base: could not remove %s. id=%s' % (widget, w_id))
        
    def clear(self):
        for w in self._child_widgets.values()[:]:
            self.remove(w)
        self._child_widgets.clear()
        self._child_locations.clear()
        self._child_kwargs.clear()
        
    def resort_children(self, children):
        current = self.get_children()
        current_kwargs = self._child_kwargs.copy()
        d = {}
        for widget in children:
            loc = self.find_next_location(d)
            d.update({loc:widget})
            if widget in self.get_children():
                self.do_child_loc_update(widget, loc)
        
    def do_add_widget(self, widget, loc, **kwargs):
        pass
    def do_child_loc_update(self, widget, loc):
        pass

def get_container_classes():
    return {}
def get_widget_classes():
    return {}
