import threading
from bases.ui_modules import gtk
from Bases import BaseObject, BaseThread
from bases.gtksimple import ThreadToGtk, thread_to_gtk
from bases import widgets, tree

class OSCTree(BaseObject):
    def __init__(self, **kwargs):
        super(OSCTree, self).__init__(**kwargs)
        self.root_node = kwargs.get('root_node')
        self.store = gtk.TreeStore(str, bool, bool, bool, bool)
        keys = ['name']
        for intkey in ['receive', 'send']:
            for attrkey in ['enabled', 'recursive']:
                keys.append('_'.join([intkey, 'interrupt', attrkey]))
        self.prop_keys = keys
        self.item_thread = OSCTreeThread(root_item_kwargs=dict(store=self.store, osc_node=self.root_node, tree_root=self), 
                                         root_item_callback=self.on_root_item_built)
        self.item_thread.start()
        #self.root_item = OSCTreeRootItem(store=self.store, osc_node=self.root_node, tree_root=self)
        self.count_label = widgets.Label()
        #self.selected_item = self.root_item
        self.topwidget = widgets.VBox()
        self.widget = gtk.TreeView()
        self.widget.get_selection().connect('changed', self.on_widget_sel_changed)
        self.scrolled_win = widgets.ScrolledWindow()
        self.scrolled_win.add(self.widget)
        self.topwidget.pack_start(self.scrolled_win, expand=True)
        self.widget.set_model(self.store)
        
        for i, key in enumerate(keys):
            name = ' '.join(key.split('_interrupt_')).title()
            if key == 'name':
                cell = gtk.CellRendererText()
                col = gtk.TreeViewColumn(name, cell, text=i)
            else:
                cell = gtk.CellRendererToggle()
                col = gtk.TreeViewColumn(name, cell, active=i)
            self.widget.append_column(col)
        hbox = widgets.HBox()
        btn = widgets.Button(label='Refresh')
        btn.connect('clicked', self.refresh)
        hbox.pack_start(btn, expand=False)
        
        #self.update_count_label()
        hbox.pack_end(self.count_label, expand=False)
        self.topwidget.pack_start(hbox, expand=False)
        hbox = widgets.HBox()
        for key in self.prop_keys:
            if key == 'name':
                continue
            name = ' '.join(key.split('_interrupt_')).title()
            btn = widgets.Button(label=name)
            btn.connect('clicked', self.on_test_btns_clicked, key)
            hbox.pack_start(btn)
        self.topwidget.pack_start(hbox, expand=False)
        
    def unlink(self):
        self.root_item.unlink_all()
        self.root_item.stop_ParentEmissionThread()
        super(OSCTree, self).unlink()
        
    def on_root_item_built(self, root_item):
        self.root_item = root_item
        self.root_item.bind(child_added=self.on_root_child_added, 
                            child_removed=self.on_root_child_removed)
            
    def on_widget_sel_changed(self, treesel):
        iter = treesel.get_selected()[1]
        if iter is None:
            if not hasattr(getattr(self, 'root_item', None), 'iter'):
                return
            iter = self.root_item.iter
        self.selected_item = self.root_item.find_from_iter(iter)
        #print 'iter=%s, item=%s, row=%s' % (iter, self.selected_item, self.store[iter])
        self.update_count_label()
        
    def on_test_btns_clicked(self, btn, key):
        node = self.selected_item.osc_node
        name, i, propname = key.split('_')
        value = getattr(node.interruptors[name], propname)
        setattr(node.interruptors[name], propname, not value)
        
    def refresh(self, *args):
        return
        self.root_item.unlink_all(remove=True)
        self.root_item = OSCTreeItem(store=self.store, osc_node=self.root_node)
        
    def update_count_label(self):
        item = self.selected_item
        self.count_label.set_text('Node Count: ' + str(item.get_node_count()))
    def on_root_child_added(self, **kwargs):
        self.update_count_label()
        #print 'child_added: ', kwargs
    def on_root_child_removed(self, **kwargs):
        self.update_count_label()
        #print 'child_removed: ', kwargs
        
    def get_node_count(self):
        return self.root_item.get_node_count()
            
class OSCTreeItem(BaseObject):
    _ChildGroups = {'tree_children':dict(ignore_index=True)}
    signals_to_register = ['iter_set']
    def __init__(self, **kwargs):
        super(OSCTreeItem, self).__init__(**kwargs)
        #print self, threading.currentThread()
        self.tree_children.child_class = OSCTreeItem
        self._store = kwargs.get('store')
        self.tree_parent = kwargs.get('tree_parent')
        self.tree_root = kwargs.get('tree_root')
        self.osc_node = kwargs.get('osc_node')
        if self.tree_parent is not None:
            if self.parent_iter is not None:
                self.on_parent_iter_set(item=self.tree_parent)
            else:
                self.tree_parent.bind(iter_set=self.on_parent_iter_set)
        else:
            self.on_parent_iter_set()
        #self.tree_children = {}
        #self.iter = self.store.append(self.parent_iter, self.build_row())
        
        self.add_child()
        #self.osc_node.bind(child_added=self.on_osc_node_child_added, 
        #                   child_removed=self.on_osc_node_child_removed)
        self.osc_node.bind(children=self.on_osc_node_children_update, 
                           property_changed=self.on_osc_node_property_changed)
        
    @property
    def name(self):
        return self.osc_node.name
        
    @property
    def id(self):
        return self.name
        
    @property
    def path(self):
        return self.store.get_path(self.iter)
        
    def unlink(self):
        #self.osc_node.unbind(self)
        super(OSCTreeItem, self).unlink()
        
    def on_parent_iter_set(self, **kwargs):
        if kwargs.get('item') != self.tree_parent:
            return
        if getattr(self, 'iter', None) is not None:
            return
        #if self.tree_parent is not None:
        #    self.tree_parent.unbind(self.on_parent_iter_set)
        thread_to_gtk(self.append_to_store)
        
    def append_to_store(self):
        self.iter = self.store.append(self.parent_iter, self.build_row())
        #self.add_child()
        self.emit('iter_set', item=self, iter=self.iter)
        
    def unlink_all(self, remove=False):
        self.unlink()
        for key in self.tree_children.keys()[:]:
            child = self.tree_children[key]
            child.unlink_all(remove)
            if remove:
                #self.store.remove(child.iter)
                #del self.tree_children[key]
                self.tree_children.del_child(child)
        if remove:
            self.store.remove(self.iter)
        
    @property
    def store(self):
        if self._store is not None:
            return self._store
        return self.tree_parent.store
        
    @property
    def parent_iter(self):
        if self.tree_parent:
            return getattr(self.tree_parent, 'iter', None)
        return None
        
    def build_row(self):
        if self.osc_node.is_root_node:
            address = '/'
            name = '/'
        else:
            address = '/'.join(self.osc_node.get_full_path())
            name = self.osc_node.name
        row = [name]
        row += [getattr(self.osc_node, key) for key in self.tree_root.prop_keys[1:]]
        return row
        
    def add_child(self, name=None):
        t = self.ParentEmissionThread
        call = self._do_add_child
        if t is not None:
            t.insert_threaded_call(call, name)
        else:
            call(name)
            
    def _do_add_child(self, name=None):
        if name is None:
            names = self.osc_node.children.keys()
        else:
            names = [name]
        for name in names:
            node = self.osc_node.children.get(name)
            if node is None:
                continue
            #tree_item = OSCTreeItem(tree_parent=self, tree_root=self.tree_root, osc_node=node)
            #self.tree_children[name] = tree_item
            tree_item = self.tree_children.add_child(tree_parent=self, tree_root=self.tree_root, osc_node=node)
            
    def remove_child(self, name):
        t = self.ParentEmissionThread
        call = self._do_add_child
        if t is not None:
            t.insert_threaded_call(call, name)
        call(name)
        
    def _do_remove_child(self, name):
        child = self.tree_children.get(name)
        if not child:
            return
        #child.unlink()
        if self.store.iter_is_valid(child.iter):
            thread_to_gtk(self.store.remove, child.iter)
        #del self.tree_children[name]
        self.tree_children.del_child(child)
        
    def on_osc_node_children_update(self, **kwargs):
        keys = set(self.osc_node.children.keys()) - set(self.tree_children.keys())
        for key in keys:
            self.add_child(key)
        keys = set(self.tree_children.keys()) - set(self.osc_node.children.keys())
        for key in keys:
            self.remove_child(key)
            
    def on_osc_node_child_added(self, **kwargs):
        name = kwargs.get('name')
        node = kwargs.get('node')
        if node == self.osc_node:
            self.add_child(name)
    
    def on_osc_node_child_removed(self, **kwargs):
        name = kwargs.get('name')
        node = kwargs.get('node')
        if node == self.osc_node:
            self.remove_child(name)
        
    def on_osc_node_property_changed(self, **kwargs):
        prop = kwargs.get('Property')
        if 'interrupt' not in prop.name:
            return
        self.store[self.iter] = self.build_row()
        
    def find_from_iter(self, iter):
        if self.store.get_path(iter) == self.path:
            return self
        if iter == self.iter:
            return self
        for child in self.tree_children.itervalues():
            result = child.find_from_iter(iter)
            if result:
                return result
                
    def get_node_count(self):
        count = 1
        for child in self.tree_children.itervalues():
            count += child.get_node_count()
        return count
    
class OSCTreeThread(BaseThread):
    def __init__(self, **kwargs):
        super(OSCTreeThread, self).__init__(**kwargs)
        self.root_item_kwargs = kwargs.get('root_item_kwargs')
        self.root_item_kwargs['ParentEmissionThread'] = self
        self.root_item_callback = kwargs.get('root_item_callback')
        self.insert_threaded_call(self.build_root_item)
    def build_root_item(self):
        self.root_item = OSCTreeItem(**self.root_item_kwargs)
        self.root_item_callback(self.root_item)
        print 'root_item built', self.root_item.tree_children.keys()
    
