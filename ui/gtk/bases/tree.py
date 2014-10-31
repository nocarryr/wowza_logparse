from ui_modules import gtk

from Bases import BaseObject

GLOBAL_CONFIG = BaseObject().GLOBAL_CONFIG
def get_gui_thread():
    return GLOBAL_CONFIG['GUIApplication'].ParentEmissionThread

class TreeViewConnector(BaseObject):
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = get_gui_thread()
        super(TreeViewConnector, self).__init__(**kwargs)
        self.register_signal('selection_changed', 'cell_edited')
        self.model = kwargs.get('model')
        self.columns = kwargs.get('columns')
        self.columns_editable = kwargs.get('columns_editable', [])
        if kwargs.get('widget') is not None:
            self.widget = kwargs.get('widget')
            self.widget.set_model(self.model.tree)
        else:
            self.widget = gtk.TreeView(model=self.model.tree)
            
        for key in sorted(self.columns.keys()):
            val = self.columns[key]
            cell = gtk.CellRendererText()
            cell.set_property('editable', key in self.columns_editable)
            cell.connect('edited', self.on_cell_edited)
            col = gtk.TreeViewColumn(val, cell, text=key)
            col.set_sort_column_id(key)
            self.widget.append_column(col)
        self.selection_set_by_program = False
        self.widget.get_selection().connect('changed', self.on_tree_selection_changed)
        self.model.connect('selection_changed', self.on_model_selection_changed)
    def on_tree_selection_changed(self, treeSel):
        if self.selection_set_by_program is False:
            iter = treeSel.get_selected()[1]
            if iter is not None:
                key = treeSel.get_selected()[0][iter][0]
                self.model.set_selection(key)
                #self.emit('selection_changed', key=key, tree=self.tree, model=self.model)
        self.selection_set_by_program = False
    def on_model_selection_changed(self, **kwargs):
        state = kwargs.get('state')
        obj = kwargs.get('obj')
        item = kwargs.get('item')
        if state and not item.selected_by_path:
            self.selected_obj = obj
            self.selected_item = item
            self.selection_set_by_program = True
            self.widget.get_selection().select_iter(item.iter)
        self.emit('selection_changed', **kwargs)
    def on_cell_edited(self, cell, path, text):
        self.emit('cell_edited', item=self.selected_item, obj=self.selected_obj, text=text)
        self.selected_item.refresh_all()

class GenericTreeStore(BaseObject):
    '''
    column_attr_map = {'id':{'PixelMappedDevice':'id', 'Pixel':'id', 'NormalAttribute':'id'}, 
                           'Name':{'PixelMappedDevice':'name', 'Pixel':'location', 'NormalAttribute':'name'}, 
                           'Location':{'Pixel':'name'}, 
                           'Color':{'NormalAttribute':'name'}, 
                           'Channel':{'NormalAttribute':'chan_index'}}
    kwargs = {'base_dict':self.PixelDevices, 'obj_name_attr':'xml_root_name', 
                  'column_names':('id', 'Name', 'Location', 'Color', 'Channel'), 
                  'column_types':(str, str, str, str, str), 
                  'column_attr_map':column_attr_map}
    '''
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = get_gui_thread()
        super(GenericTreeStore, self).__init__(**kwargs)
        kwargs.setdefault('show_dicts', True)
        self.register_signal('selection_changed')
        self.base_dict = kwargs.get('base_dict')
        self.column_names = kwargs.get('column_names')
        self.column_attr_map = kwargs.get('column_attr_map')
        self.column_types = kwargs.get('column_types')
        self.tree = gtk.TreeStore(*self.column_types)
        self.iter = None
        self.items = {}
        self.root_kwargs = kwargs.copy()
        self.root_kwargs.update({'tree':self.tree, 'tree_parent':self, 'root_item':self})
        del self.root_kwargs['base_dict']
        if 'obj_name_attr' not in self.root_kwargs:
            bob
        for key, val in self.base_dict.iteritems():
            self.add_item(key, val)
    def add_item(self, id, obj):
        kwargs = self.root_kwargs.copy()
        if type(obj) == dict:
            kwargs.update({'base_dict':obj, 'name':id})
            item = TreeItemDict(**kwargs)
        else:
            kwargs.update({'base_obj':obj})
            item = TreeItemObj(**kwargs)
        self.items.update({id:item})
        item.connect('child_added', self.on_child_added)
        item.connect('selection_changed', self.on_item_selection_changed)
    def on_child_added(self, **kwargs):
        item = kwargs.get('item')
        item.connect('selection_changed', self.on_selection_changed)
    def on_selection_changed(self, **kwargs):
        #print kwargs
        self.emit('selection_changed', **kwargs)
    def refresh_all(self):
        for key, val in self.base_dict.iteritems():
            if key in self.items:
                item = self.items[key]
                if isinstance(item, TreeItemObj) and item.base_obj != val:
                    item.prepare_delete()
                    del self.items[key]
                    self.add_item(key, val)
                else:
                    item.refresh_all()
            else:
                self.add_item(key, val)
        keys = set()
        for key in self.items.iterkeys():
            if key not in self.base_dict:
                keys.add(key)
        for key in keys:
            self.items[key].prepare_delete()
            del self.items[key]
            
    def set_selection(self, id):
        selected = None
        for item in self.items.itervalues():
            result = item.set_selection(id)
            if result:
                selected = item
        return selected
    def on_item_selection_changed(self, **kwargs):
        item = kwargs.get('item')
        state = kwargs.get('state')
        #print item
        if state:
            if hasattr(item, 'base_obj'):
                obj = item.base_obj
            elif hasattr(item, 'base_dict'):
                obj = item.base_dict
            self.emit('selection_changed', item=item, obj=obj, state=state)

class TreeItemBase(BaseObject):
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = get_gui_thread()
        super(TreeItemBase, self).__init__(**kwargs)
        self.register_signal('selection_changed')
        self.register_signal('child_added')
        self.selected = False
        self.selected_by_path = False
        self.tree = kwargs.get('tree')
        self.tree_parent = kwargs.get('tree_parent', None)
        self.root_item = kwargs.get('root_item')
        if hasattr(self, 'base_obj') is False:
            self.base_obj = kwargs.get('base_obj')
        self.child_signal_id = None
        self.children = {}
        self.child_signals = {}
        self.row = []
        self.kwargs = kwargs
        
        self.column_names = kwargs.get('column_names')
        self.column_attr_map = kwargs.get('column_attr_map')
        self.column_types = kwargs.get('column_types')
        for coltype in self.column_types:
            self.row.append(coltype())
        self.build()
        if kwargs.get('show_dicts') is False and isinstance(self, TreeItemDict) and self.tree_parent.iter is not None:
            self.LOG.warning('not appending row', self.row, kwargs.get('show_dicts'))
            self.iter = self.tree_parent.iter
        else:
            self.iter = self.tree.append(self.tree_parent.iter, self.row)
        self.look_for_children()
        self.search_for_child_signals()
    def build(self):
        pass
    def look_for_children(self):
        pass
    def add_item(self, id, obj):
        if obj is None:
            return
        if id in self.children:
            self.children[id].refresh_all()
        else:
            kwargs = self.kwargs.copy()
            kwargs.update({'tree_parent':self})
            if type(obj) == dict:
                kwargs.update({'base_dict':obj, 'name':id})
                item = TreeItemDict(**kwargs)
            else:
                kwargs.update({'base_obj':obj})
                item = TreeItemObj(**kwargs)
            item.connect('selection_changed', self.root_item.on_item_selection_changed)
            #item.connect('child_added', self.on_child_added)
            self.children.update({id:item})
            self.emit('child_added', id=id, item=self.children[id], parent_item=self)
            
    def refresh_all(self):
        self.build()
        self.tree[self.iter] = self.row
        self.look_for_children()
        for child in self.children.itervalues():
            child.refresh_all()
            
    def prepare_delete(self):
        if self.child_signal_id is not None:
            self.base_obj.disconnect(id=self.child_signal_id)
        for child in self.children.itervalues():
            child.prepare_delete()
        if not isinstance(self, TreeItemDict) or self.kwargs.get('show_dicts'):
            if self.tree.iter_is_valid(self.iter) is False:
                bob
            self.tree.remove(self.iter)
        else:
            self.LOG.warning('not deleting row')
        self.LOG.info(self.row, 'delete')
        
    def search_for_child_signals(self):
        if self.base_obj is not None:
            sig = self.base_obj.search_for_signal_name('child_added')
            if len(sig) > 0:
                self.child_signal_id = self.base_obj.connect('child_added', self.on_child_signal)
                
    def on_child_signal(self, **kwargs):
        self.look_for_children()

    def set_selection(self, id):
        selected = False
        selected_by_path = False
        if id == self.row[0]:
            selected = True
            selected_by_path = False
        else:
            for child in self.children.itervalues():
                result = child.set_selection(id)
                if result:
                    selected = True
                    selected_by_path = True
        if selected != self.selected or selected_by_path != self.selected_by_path:
            self.selected = selected
            self.selected_by_path = selected_by_path
            self.emit('selection_changed', item=self, state=selected)
            self.LOG.info(self, 'selected = ', selected)
            
        #if selected_by_path != self.selected_by_path:
        #    self.selected_by_path = selected_by_path
        return selected
        
class TreeItemDict(TreeItemBase):
    def __init__(self, **kwargs):
        self.name = kwargs.get('name')
        self.base_dict = kwargs.get('base_dict')
        for key in ['name', 'base_dict']:
            del kwargs[key]
        super(TreeItemDict, self).__init__(**kwargs)
        
    def build(self):
        for y, col in enumerate(self.column_names):
            if 'name' in col.lower():
                self.row[y] = self.name
                
    def refresh_all(self):
        keys = set()
        for key in self.children.iterkeys():
            if key not in self.base_dict:
                keys.add(key)
        for key in keys:
            self.children[key].prepare_delete()
            del self.children[key]
        super(TreeItemDict, self).refresh_all()
        
    def prepare_delete(self):
        super(TreeItemDict, self).prepare_delete()
        
        
    def look_for_children(self):
        for key, val in self.base_dict.iteritems():
            if key not in self.children:
                self.add_item(key, val)
    
    
class TreeItemObj(TreeItemBase):
    def __init__(self, **kwargs):
        self.base_obj = kwargs.get('base_obj')
        name_attr = kwargs.get('obj_name_attr')
        if name_attr is None:
            bob
        if name_attr is not None and hasattr(self.base_obj, name_attr):
            self.base_obj_name = getattr(self.base_obj, name_attr)
        else:
            self.base_obj_name = None
        super(TreeItemObj, self).__init__(**kwargs)
        self.attr_signal_id = None
        self.attr_signals = {}
        self.bound_properties = set()
        self.search_for_attr_signals()
    def build(self):
        for y, col in enumerate(self.column_names):
            if self.base_obj_name in self.column_attr_map[col]:
                key = self.column_attr_map[col][self.base_obj_name]
                if hasattr(self.base_obj, key):
                    attr = getattr(self.base_obj, key)
                    if type(attr) == self.column_types[y]:
                        self.row[y] = attr
                    elif attr is None:
                        self.row[y] = self.column_types[y]()
                    else:
                        self.row[y] = self.column_types[y](attr)
                        
    def look_for_children(self):
        child_attr = self.kwargs.get('child_name_attr')
        if hasattr(self.base_obj, child_attr):
            for key in getattr(self.base_obj, child_attr):
                if key not in self.children:
                    self.add_item(key, getattr(self.base_obj, key))
                    
    def prepare_delete(self):
        if self.attr_signal_id is not None:
            self.base_obj.disconnect(id=self.attr_signal_id)
        self.base_obj.unbind(self.on_Property)
        super(TreeItemObj, self).prepare_delete()

    def search_for_attr_signals(self):
        for col in self.column_names:
            key = self.column_attr_map[col].get(self.base_obj_name)
            if key is not None and hasattr(self.base_obj, key):
                prop = self.base_obj.Properties.get(key)
                if prop:
                    self.base_obj.bind(**{key:self.on_Property})
                    self.bound_properties.add(key)
                else:
                    signal_name = self.base_obj.search_for_signal_name(key)
                    if len(signal_name) > 0:
                        if len(signal_name) > 1:
                            max_len = 0
                            real_sig = None
                            for sig in signal_name:
                                if len(sig) > max_len:
                                    max_len = len(sig)
                                    real_sig = sig
                        else:
                            real_sig = signal_name[0]
                        if real_sig is not None:
                            self.attr_signals.update({real_sig:key})
                            self.attr_signal_id = self.base_obj.connect(real_sig, self.on_attr_signal)
                            #print 'signal_id = ', self.attr_signal_id
                        
    def on_attr_signal(self, **kwargs):
        signal_name = kwargs.get('signal_name')
        if signal_name in self.attr_signals:
            self.build()
            self.tree[self.iter] = self.row
            
    def on_Property(self, **kwargs):
        prop = kwargs.get('Property')
        if prop.name in self.bound_properties:
            self.build()
            self.tree[self.iter] = self.row
