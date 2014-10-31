from ui_modules import gtk

from Bases import BaseObject
from Bases.Properties import PropertyConnector

from gtksimple import ThreadToGtk, TreeModelSort, get_gui_thread


class ListModel(BaseObject, PropertyConnector):
    _Properties = {'current_selection':dict(ignore_type=True, quiet=True)}
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = get_gui_thread()
        super(ListModel, self).__init__(**kwargs)
        self.register_signal('cell_toggled', 'cell_edited', 'selection_changed')
        self.list_types = kwargs.get('list_types', [str, str])
        self.column_names = kwargs.get('column_names', ['id', 'data'])
        self.column_order = kwargs.get('column_order', [x for x in range(len(self.column_names))])
        self.columns_editable = kwargs.get('columns_editable', [])
        self.default_sort_column = kwargs.get('default_sort_column')
        if not self.default_sort_column:
            for i, key in enumerate(self.column_names):
                if 'name' in key.lower():
                    self.default_sort_column = i
                    break
        self.store = gtk.ListStore(*self.list_types)
        self.widget = kwargs.get('widget')
        self._init_widget()
        self.items = kwargs.get('items', {})
        self.iters = {}
        self.update(self.items)
        self.set_sort_column(self.default_sort_column)
        self.bind(current_selection=self._on_current_selection_set)
        self.Property = kwargs.get('Property')
    def unlink(self):
        self.Property = None
        super(ListModel, self).unlink()
    @ThreadToGtk
    def update(self, d):
        for key, val in d.iteritems():
            row = self._build_row(key, val)
            while None in row:
                i = row.index(None)
                row[i] = self.list_types[i]()
            if key in self.items:
                self.store[self.iters[key]] = row
            else:
                iter = self.store.append(row)
                self.iters.update({key:iter})
        self.items.update(d)
    @ThreadToGtk
    def delete_item(self, key):
        iter = self.iters.get(key)
        if iter is None:
            return
        del self.items[key]
        self.store.remove(iter)
        self.iters.clear()
        for row in self.store:
            if row[0] == key:
                continue
            self.iters[row[0]] = row.iter
    @ThreadToGtk
    def clear(self):
        self.store.clear()
        self.iters.clear()
        self.items.clear()
    def attach_Property(self, prop):
        super(ListModel, self).attach_Property(prop)
        if prop.entries is None:
            return
        l = prop.entries[:]
        self.update(dict(zip(l, l)))
        if prop.value is None or prop.value not in prop.entries:
            return
        self.set_current_selection(key=prop.value)
    def detach_Property(self, prop):
        super(ListModel, self).detach_Property(prop)
        self.clear()
    def on_Property_value_changed(self, **kwargs):
        value = kwargs.get('value')
        self.set_current_selection(key=value)
    def _build_row(self, key, val):
        if len(self.list_types) == 1:
            return [val]
        elif len(self.list_types) == 2:
            return [key, val]
        elif isinstance(val, list):
            return [key] + val
        return None
    def _init_widget(self):
        if self.widget is not None:
            self.widget.set_model(self.store)
            if isinstance(self.widget, gtk.TreeView):
                for x in self.column_order:
                    name = self.column_names[x]
                    if self.list_types[x] == bool:
                        col = self._build_toggle_column(name=name, index=x)
                    else:
                        col = self._build_text_column(name=name, index=x)
                    self.widget.append_column(col)
            elif isinstance(self.widget, gtk.ComboBox):
                colNum = len(self.list_types) - 1
                cell = gtk.CellRendererText()
                self.widget.pack_start(cell, True)
                self.widget.add_attribute(cell, 'text', colNum)
    def _build_text_column(self, **kwargs):
        name = kwargs.get('name')
        i = kwargs.get('index')
        cell = gtk.CellRendererText()
        cell.set_property('editable', i in self.columns_editable)
        cell.connect('edited', self.on_cell_edited, i)
        col = gtk.TreeViewColumn(name, cell, text=i)
        col.set_sort_column_id(i)
        return col
    def _build_toggle_column(self, **kwargs):
        name = kwargs.get('name')
        i = kwargs.get('index')
        cell = gtk.CellRendererToggle()
        cell.connect('toggled', self.on_cell_toggled)
        col = gtk.TreeViewColumn(name, cell, active=i, activatable=i+1)
        return col
    def set_sort_column(self, i, order=False):
        if i is None:
            return
        order = int(order)
        self.store.set_sort_column_id(i, order)
    def on_cell_toggled(self, cell, path):
        key = self.store[path][0]
        self.emit('cell_toggled', obj=self, key=key, state=not(cell.get_active()))
    def on_cell_edited(self, cell, path, text, col_index):
        value = self.list_types[col_index](text)
        self.emit('cell_edited', key=self.current_selection, column=col_index, value=value)
    def _on_current_selection_set(self, **kwargs):
        if self.Property is None or self.Property.entries is None:
            return
        value = kwargs.get('value')
        self.set_Property_value(value)

class ListModelTree(ListModel):
    def __init__(self, **kwargs):
        kwargs.setdefault('widget', gtk.TreeView())
        super(ListModelTree, self).__init__(**kwargs)
        self.widget.get_selection().connect('changed', self.on_widget_sel_changed)
    def clear(self):
        super(ListModelTree, self).clear()
        self.current_selection = None
        self.emit('selection_changed', obj=self, key=None)
    def on_widget_sel_changed(self, treesel):
        iter = treesel.get_selected()[1]
        if iter is not None:
            key = self.store[iter][0]
        else:
            key = None
        if key != self.current_selection:
            self.current_selection = key
            self.emit('selection_changed', obj=self, key=key)
    @ThreadToGtk
    def set_current_selection(self, **kwargs):
        key = kwargs.get('key')
        if key is None:
            self.widget.get_selection().unselect_all()
            return
        if key == self.current_selection or key not in self.items:
            return
        self.current_selection = key
        iter = self.iters.get(key)
        self.widget.get_selection().select_iter(iter)

class ListModelCombo(ListModel):
    def __init__(self, **kwargs):
        kwargs.setdefault('list_types', [str])
        kwargs.setdefault('widget', gtk.ComboBox())
        super(ListModelCombo, self).__init__(**kwargs)
        self.widget.connect('changed', self.on_widget_sel_changed)
    def clear(self):
        super(ListModelCombo, self).clear()
        self.current_selection = None
        self.emit('selection_changed', obj=self, key=None)
    def on_widget_sel_changed(self, widget):
        iter = self.widget.get_active_iter()
        if iter is None:
            return
        key = self.store[iter][0]
        if key != self.current_selection:
            self.current_selection = key
            self.emit('selection_changed', obj=self, key=key)
    @ThreadToGtk
    def set_current_selection(self, **kwargs):
        key = kwargs.get('key')
        if key == self.current_selection:
            return
        self.current_selection = key
        if key is None:
            self.widget.set_active(-1)
            return
        iter = self.iters.get(key)
        self.widget.set_active_iter(iter)
