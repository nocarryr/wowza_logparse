import traceback

from ui_modules import gtk

from Bases import BaseObject
from Bases.Properties import PropertyConnector

from gtksimple import ThreadToGtk, TreeModelSort, GTK_VERSION, get_gui_thread

key_attrs = ['id', 'Index']#, 'name']

class PropertyListModel(BaseObject):
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = get_gui_thread()
        super(PropertyListModel, self).__init__(**kwargs)
        self.register_signal('new_cell', 'obj_added', 'obj_removed')
        self.child_group = kwargs.get('child_group')
        self.used_classes = kwargs.get('used_classes')
        model_obj = None
        if self.child_group is not None:
            if len(self.child_group):
                if self.used_classes is not None:
                    for obj in self.child_group.itervalues():
                        if obj.__class__ in self.used_classes:
                            model_obj = obj
                            break
                else:
                    model_obj = self.child_group.values()[0]
            elif self.child_group.child_class:
                try:
                    model_obj = self.child_group.child_class()
                except:
                    s = traceback.format_exc()
                    self.LOG.warning(s + '\nPropertyListModel could not build model_obj:\n')
                    model_obj = None
        if not model_obj:
            model_obj = kwargs.get('model_obj')
        self.prop_names = kwargs.get('property_names')
        if not self.prop_names:
            self.prop_names = list(model_obj.SettingsPropKeys)
        self.column_names = kwargs.get('column_names', self.prop_names[:])
        self.column_types = kwargs.get('column_types')
        self.columns_editable = kwargs.get('columns_editable')
        self.default_sort_prop = kwargs.get('default_sort_prop')
        self.key_attr = kwargs.get('key_attr')
        for i, prop in enumerate(self.prop_names):
            name = self.column_names[i]
            if prop == name:
                name = ' '.join(name.split('_')).title()
                self.column_names[i] = name
        if not self.columns_editable:
            self.columns_editable = getattr(model_obj, 'SettingsPropKeys', [])
        if not self.column_types:
            props = [model_obj.Properties[key] for key in self.prop_names]
            self.column_types = [prop.type for prop in props]
        #print 'propnames: ', self.prop_names
        if self.key_attr is None and self.prop_names[0] not in key_attrs:
            for attr in key_attrs:
                if model_obj and hasattr(model_obj, attr):
                    self.prop_names.insert(0, attr)
                    self.column_names.insert(0, attr)
                    prop = model_obj.Properties.get(attr)
                    if prop is not None:
                        col_type = prop.type
                    else:
                        col_type = type(getattr(model_obj, attr))
                    self.column_types.insert(0, col_type)
                    self.key_attr = attr
                    #print 'break?'
                    break
        #print 'propnames=%s, types=%s' % (self.prop_names, self.column_types)
        self.store = gtk.ListStore(*self.column_types)
        self.sorted_store = TreeModelSort(model=self.store)
        self.child_obj = {}
        self.child_iters = {}
        self.views = {}
        self.cells = {}
        
        if self.default_sort_prop is None:
            if 'Index' in self.prop_names:
                self.default_sort_prop = 'Index'
        self.set_sort_prop(self.default_sort_prop)
        
        if self.child_group:
            self.add_obj(*self.child_group.values())
            self.child_group.bind(child_update=self.on_child_group_update)
        
    def unlink(self):
        if self.child_group:
            self.child_group.unbind(self)
        for view_id in self.views.keys()[:]:
            self.unlink_view(view_id=view_id)
        for key in self.child_obj.keys()[:]:
            #self.del_obj(id=key)
            obj = self.child_obj[key]
            del self.child_iters[obj.iter]
            obj.unlink()
            del self.child_obj[key]
        super(PropertyListModel, self).unlink()
        
    @ThreadToGtk
    def add_obj(self, *args):
        for arg in args:
            objid = getattr(arg, self.prop_names[0], None)
            if objid is None:
                continue
            if self.used_classes is not None and arg.__class__ not in self.used_classes:
                continue
            if objid in self.child_obj:
                continue
            pl_obj = PropertyListObj(parent=self, obj=arg)
            self.child_obj[objid] = pl_obj
            self.child_iters[pl_obj.iter] = pl_obj
            self.emit('obj_added', id=objid)
            
    @ThreadToGtk
    def del_obj(self, **kwargs):
        objid = kwargs.get('id')
        obj = kwargs.get('obj')
        if objid is None:
            objid = getattr(obj, self.prop_names[0])
        pl_obj = self.child_obj.get(objid)
        if not pl_obj:
            return
        pl_obj.unlink()
        #del self.child_iters[pl_obj.iter]
        self.child_iters.clear()
        for row in self.store:
            c = self.child_obj[row[0]]
            c.iter = row.iter
            self.child_iters[row.iter] = c
        del self.child_obj[objid]
        self.emit('obj_removed', id=objid)
        
    def add_treeview(self, **kwargs):
        treeview = kwargs.get('treeview')
        widget = kwargs.get('widget')
        if treeview:
            treeview.model = self
            if not widget:
                widget = treeview.widget
            parent_id = treeview.id
            self.views[parent_id] = treeview
        else:
            if not widget:
                widget = gtk.TreeView()
            parent_id = id(widget)
            self.views[parent_id] = widget
        hidden_props = kwargs.get('hidden_props', [])
        prop_order = kwargs.get('prop_order', [])
        for prop_name in self.prop_names:
            if prop_name not in prop_order and prop_name not in hidden_props:
                prop_order.append(prop_name)
        
        widget.set_model(self.sorted_store)
        for prop_name in prop_order:
            i = self.prop_names.index(prop_name)
            col_name = self.column_names[i]
            col_type = self.column_types[i]
            if col_type == bool:
                cell = gtk.CellRendererToggle()
                cell.set_property('activatable', prop_name in self.columns_editable)
                col = gtk.TreeViewColumn(col_name, cell, active=i)
            else:
                cell = gtk.CellRendererText()
                cell.set_property('editable', prop_name in self.columns_editable)
                col = gtk.TreeViewColumn(col_name, cell, text=i)
            self._on_new_cell(type=col_type, cell=cell, column=i, parent_id=parent_id)
            col.set_sort_column_id(i)
            widget.append_column(col)
        return widget
        
    def unlink_view(self, **kwargs):
        view_id = kwargs.get('view_id')
        treeview = kwargs.get('treeview')
        widget = kwargs.get('widget')
        if view_id is not None:
            obj = self.views.get(view_id)
            if isinstance(obj, gtk.TreeView):
                widget = obj
            elif isinstance(obj, BaseObject):
                treeview = obj
                widget = treeview.widget
        elif treeview is not None:
            view_id = treeview.id
            widget = treeview.widget
        elif widget is not None:
            view_id = id(widget)
        else:
            return False
        for child in self.child_obj.itervalues():
            child.unlink_view(view_id=view_id, widget=widget)
        del self.views[view_id]
        del self.cells[view_id]
            
    def set_sort_prop(self, prop_name, order=True):
        if prop_name not in self.prop_names:
            return
        i = self.prop_names.index(prop_name)
        #g_ord = {True:gtk.SortType.ASCENDING, False:gtk.SortType.DESCENDING}
        self.sorted_store.set_sort_column_id(i, order)
    
    def _on_new_cell(self, **kwargs):
        parent_id = kwargs.get('parent_id')
        column = kwargs.get('column')
        if parent_id not in self.cells:
            self.cells[parent_id] = {}
        if column not in self.cells[parent_id]:
            self.cells[parent_id][column] = kwargs.copy()
        for child in self.child_obj.itervalues():
            child._on_new_cell(**kwargs)
            
    def on_child_group_update(self, **kwargs):
        mode = kwargs.get('mode')
        obj = kwargs.get('obj')
        if mode == 'add':
            self.add_obj(obj)
        elif mode == 'remove':
            self.del_obj(obj=obj)
        
class PropertyListObj(BaseObject):
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = get_gui_thread()
        super(PropertyListObj, self).__init__(**kwargs)
        self.parent = kwargs.get('parent')
        self.store = self.parent.store
        self.sorted_store = self.parent.sorted_store
        self.obj = kwargs.get('obj')
        self.items = {}
        for i, prop_name in enumerate(self.parent.prop_names):
            item = PropertyListItem(parent=self, prop_name=prop_name, column=i)
            self.items[prop_name] = item
        self.iter = self.store.append(self.build_row())
        #print self.store.get_path(self.iter)
        self.s_iter = self.sorted_store.convert_child_iter_to_iter(self.iter)
        for cells in self.parent.cells.itervalues():
            for column, cell in cells.iteritems():
                self._on_new_cell(**cell)
                
    def unlink(self):
        for item in self.items.itervalues():
            item.unlink()
        self.store.remove(self.iter)
        self.iter = None
        super(PropertyListObj, self).unlink()
    def unlink_view(self, **kwargs):
        for item in self.items.itervalues():
            item.unlink_view(**kwargs)
    def build_row(self):
        return [self.items[key].value for key in self.parent.prop_names]
    def _on_new_cell(self, **kwargs):
        for item in self.items.itervalues():
            item._on_new_cell(**kwargs)
            
class PropertyListItem(BaseObject, PropertyConnector):
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = get_gui_thread()
        super(PropertyListItem, self).__init__(**kwargs)
        self.parent = kwargs.get('parent')
        self.obj = self.parent.obj
        self.prop_name = kwargs.get('prop_name')
        self.column = kwargs.get('column')
        self.store = self.parent.store
        self.sorted_store = self.parent.sorted_store
        self.widget_signals = {}
        self.src_attr = None
        if self.prop_name in self.obj.Properties:
            self.Property = (self.obj, self.prop_name)
        else:
            self.src_attr = self.prop_name
        
    def unlink(self):
        self.Property = None
        for view_id in self.widget_signals.keys()[:]:
            self.unlink_view(view_id=view_id)
        super(PropertyListItem, self).unlink()
        
    def unlink_view(self, **kwargs):
        view_id = kwargs.get('view_id')
        signals = self.widget_signals.get(view_id)
        if signals is None:
            return
        for s_id, cell in signals:
            if cell.handler_is_connected(s_id):
                cell.disconnect(s_id)
            else:
                print 'could not remove cell handler: ', self, s_id, cell
        del self.widget_signals[view_id]
        
    @property
    def value(self):
        value = self.get_Property_value()
        if value is None:
            mytype = self.parent.parent.column_types[self.column]
            if mytype in [int, float]:
                value = mytype(0)
            elif mytype == bool:
                value = False
            elif mytype == str:
                value = ''
        return value
        
    def get_Property_value(self):
        if self.src_attr is not None:
            return getattr(self.parent.obj, self.src_attr)
        return super(PropertyListItem, self).get_Property_value()
        
    def attach_Property(self, prop):
        super(PropertyListItem, self).attach_Property(prop)            
            
    def unlink_Property(self, prop):
        super(PropertyListItem, self).unlink_Property(prop)
        
    def on_Property_value_changed(self, **kwargs):
        self.update_from_property()
        
    @ThreadToGtk
    def update_from_property(self):
        iter = self.parent.iter
        if iter is None:
            self.LOG.warning('ALREADY UNLINKED: ', str(self, self.parent, self.obj, self.Property))
            return
        self.store.set_value(self.parent.iter, self.column, self.value)
        
    def on_cell_edited(self, cell, pathstr, text, col_index):
        if col_index != self.column:
            return
        if GTK_VERSION < 3:
            path = pathstr
        else:
            path = gtk.TreePath(pathstr)
        iter = self.sorted_store.get_iter(path)
        objid = self.sorted_store[iter][0]
        if objid != self.parent.build_row()[0]:
            return
        #print 'cell edit: ', col_index, path, text
        self.set_Property_value(text, convert_type=True)
        self.on_Property_value_changed()
        
    def on_cell_toggled(self, cell, path, column):
        if column != self.column:
            return
        iter = self.sorted_store.get_iter(path)
        objid = self.sorted_store[iter][0]
        if objid != self.parent.build_row()[0]:
            return
        propval = self.get_Property_value()
        self.set_Property_value(not propval)
        
    def _on_new_cell(self, **kwargs):
        cell = kwargs.get('cell')
        column = kwargs.get('column')
        value_type = kwargs.get('type')
        parent_id = kwargs.get('parent_id')
        #print self.prop_name, self.column, kwargs
        if column != self.column:
            return
        if value_type == bool:
            s_id = cell.connect('toggled', self.on_cell_toggled, column)
        else:
            s_id = cell.connect('edited', self.on_cell_edited, column)
        if parent_id not in self.widget_signals:
            self.widget_signals[parent_id] = set()
        self.widget_signals[parent_id].add((s_id, cell))
