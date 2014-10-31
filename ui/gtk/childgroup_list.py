from bases import widgets
import editorbase

class ChildGroupList(editorbase.EditorBase):
    topwidget_label = ''
    _Properties = {'current_child':dict(ignore_type=True)}
    def init_editor(self, **kwargs):
        self.name = kwargs.get('name')
        self.child_group = kwargs.get('child_group')
        
        self.col_names = kwargs.get('col_names')
        self.col_attrs = kwargs.get('col_attrs')
        self.list_types = kwargs.get('list_types')
        self.col_order = kwargs.get('col_order')
        if not self.col_order:
            self.col_order = range(len(self.col_names))[1:]
        self.default_sort_column = kwargs.get('default_sort_column', 1)
        
        self.list = widgets.TreeList(name=self.name, 
                                     column_names=self.col_names, 
                                     list_types=self.list_types, 
                                     column_order=self.col_order, 
                                     default_sort_column=self.default_sort_column)
        self.update_list()
        self.list.connect('selection_changed', self.on_list_selection_changed)
        self.bind(current_child=self._on_current_child_set)
        
        self.child_group.bind(child_added=self.on_child_added, 
                              child_removed=self.on_child_removed)
        
        self.topwidget = self.list.topwidget
        
    def unlink(self):
        #self.child_group.unbind(self.on_child_added, self.on_child_removed)
        self.child_group.unbind(self)
        for child in self.child_group.itervalues():
            child.unbind(self)#.on_child_property_changed)
        super(ChildGroupList, self).unlink()
        
    def _on_current_child_set(self, **kwargs):
        child = kwargs.get('value')
        if child is None:
            cid = None
        else:
            cid = child.id
        if self.list.current_selection != cid:
            self.list.set_current_selection(key=cid)
        
    def update_list(self, key=None):
        if key is not None:
            children = {key:self.child_group[key]}
        else:
            children = self.child_group
        for key, val in children.iteritems():
            values = [getattr(val, attr) for attr in self.col_attrs][1:]
            if len(values) == 1:
                values = values[0]
            self.list.update({key:values})
            val.bind(property_changed=self.on_child_property_changed)
        
    def on_list_selection_changed(self, **kwargs):
        key = kwargs.get('key')
        child = self.child_group.get(key)
        if child:
            self.current_child = child
                
    def on_child_property_changed(self, **kwargs):
        child = kwargs.get('obj')
        self.update_list(child.id)
        
    def on_child_added(self, **kwargs):
        child = kwargs.get('obj')
        self.update_list(child.id)
        
        
    def on_child_removed(self, **kwargs):
        child = kwargs.get('obj')
        if child == self.current_child:
            self.current_child = None
        self.list.clear()
        self.update_list()
