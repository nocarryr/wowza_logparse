from gi.repository import Gtk
import parser
import network_objects

class TreeStore(object):
    def __init__(self, **kwargs):
        self.column_types = kwargs.get('column_types')
        self.column_attr_map = kwargs.get('column_attr_map')
        self.column_names = kwargs.get('column_names')
        self.root_obj = kwargs.get('root_obj')
        self.child_attrs = kwargs.get('child_attrs')
        self.children = {}
        self.store = Gtk.TreeStore(*self.column_types)
        if type(self.root_obj) in [list, tuple, set]:
            self.root_child = []
            for robj in self.root_obj:
                self.root_child.append(TreeItem(tree_root=self, object=robj))
        else:
            self.root_child = TreeItem(tree_root=self, object=self.root_obj)
        
class TreeItem(object):
    def __init__(self, **kwargs):
        self.obj = kwargs.get('object')
        self.tree_root = kwargs.get('tree_root')
        self.tree_parent = kwargs.get('tree_parent')
        self.attr_map = self.tree_root.column_attr_map[self.obj.__class__.__name__]
        self.child_attr = self.tree_root.child_attrs.get(self.obj.__class__.__name__)
        self.iter = self.add_to_tree()
        self.children = {}
        if self.child_attr is not None:
            self.add_children()
    def add_to_tree(self):
        vals = []
        column_types = self.tree_root.column_types
        for i, attr in enumerate(self.attr_map):
            t = column_types[i]
            vals.append(t(getattr(self.obj, attr)))
        if self.tree_parent is None:
            parent = None
        else:
            parent = self.tree_parent.iter
        iter = self.tree_root.store.append(parent)
        self.tree_root.store[iter] = vals
        return iter
    def add_children(self):
        child_vals = getattr(self.obj, self.child_attr)
        ckwargs = {'tree_root':self.tree_root, 'tree_parent':self}
        if isinstance(child_vals, dict):
            for k, v in child_vals.iteritems():
                ckwargs['object'] = v
                child = TreeItem(**ckwargs)
                self.children[k] = child
        else:
            for i, v in enumerate(child_vals):
                ckwargs['object'] = v
                child = TreeItem(**ckwargs)
                self.children[i] = child
        
class TreeWidget(object):
    def __init__(self, **kwargs):
        self.tree_store = kwargs.get('tree_store')
        self.id = kwargs.get('id')
        self.title = kwargs.get('title')
        self.widget = Gtk.ScrolledWindow()
        self.tree = Gtk.TreeView(self.tree_store.store)
        self.build_columns()
        self.widget.add(self.tree)
    def build_columns(self):
        store = self.tree_store
        col_names = store.column_names
        col_types = store.column_types
        widget = self.tree
        for i, name in enumerate(col_names):
            cell = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(col_names[i], cell, text=i)
            widget.append_column(col)
            
class Window(Gtk.Window):
    def __init__(self, **kwargs):
        super(Window, self).__init__()
        self.tree_stores = kwargs.get('tree_stores')
        self.tree_widgets = {}
        main_vbox = Gtk.VBox()
        self.add(main_vbox)
        self.notebook = Gtk.Notebook()
        for store_data in self.tree_stores:
            title = store_data.get('title')
            if title is None:
                title = ' '.join(store_data['id'].split('_')).title()
                store_data.setdefault('title', title)
            tw = TreeWidget(**store_data)
            self.tree_widgets[store_data['id']] = tw
            lbl = Gtk.Label(title)
            self.notebook.append_page(tw.widget, lbl)
        main_vbox.pack_start(self.notebook, True, True, 0)
        
def build_treeviews(**kwargs):
    data = kwargs.get('data')
    if data is None:
        data = test(**kwargs)
    tree_stores = []
    tsdata = {'id':'PARSED_BRACKETS'}
    ts = TreeStore(column_names=['start_line', 'end_line', 'text'], 
                   column_types=[int, int, str], 
                   column_attr_map={'NestedBracket':['start_line_num', 'end_line_num', 'contents']}, 
                   child_attrs={'NestedBracket':'children'}, 
                   root_obj=data['PARSED_BRACKETS'])
    tsdata['tree_store'] = ts
    tree_stores.append(tsdata)
    win = Window(tree_stores=tree_stores)
    win.connect("delete-event", Gtk.main_quit)
    win.show_all()
    Gtk.main()
    
def test(**kwargs):
    net_conf, net_parse = parser.parse_conf(filename='dhcpd.conf', return_parsed=True)
    lease_conf = parser.parse_leases(filename='dhcpd.leases')
    nets = network_objects.build_networks(net_conf)
    leases = network_objects.build_leases(lease_conf)
    return {'PARSED_NETWORKS':net_conf, 
            'PARSED_BRACKETS':net_parse, 
            'PARSED_LEASES':lease_conf, 
            'NETWORKS':nets, 
            'LEASES':leases}
