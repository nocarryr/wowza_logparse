from ui_base.gtk import gtkBaseUI
from ui_base.gtk.editorbase import EditorBase
from ui_base.gtk.bases import widgets, tree
from ui_base.gtk.bases.ui_modules import gtk

class Application(gtkBaseUI.Application):
    def __init__(self, **kwargs):
        kwargs['mainwindow_cls'] = MainWindow
        super(Application, self).__init__(**kwargs)
    
class MainWindow(gtkBaseUI.BaseWindow):
    def __init__(self, **kwargs):
        super(MainWindow, self).__init__(**kwargs)
        self.parser = kwargs.get('parser')
        
        topwidget = widgets.VBox()
        self.topwidget = topwidget
        hbox = widgets.HBox()
        self.view_data = {'Raw Log':RawLogView, 'Session View':SessionView}
        self.view = None
        for key in self.view_data.keys():
            btn = widgets.Button(label=key)
            btn.connect('clicked', self.on_view_btn_clicked, key)
            hbox.pack_start(btn)
        topwidget.pack_start(hbox, expand=False)
        self.window.add(topwidget)
        self.window.show_all()
    def on_view_btn_clicked(self, btn, key):
        cls = self.view_data[key]
        if self.view is not None:
            self.view.unlink()
            self.topwidget.remove(self.view.topwidget)
        view = cls(root_obj=self)
        self.topwidget.pack_start(view.topwidget, expand=True)
        
        
class RawLogView(EditorBase):
    def init_editor(self, **kwargs):
        self.parser = self.root_obj.parser
        lvkwargs = dict(column_names=['id'] + self.parser.field_names, 
                        list_types=[str] + [str] * len(self.parser.field_names), 
                        default_sort_column=0)
        self.listview = widgets.TreeList(**lvkwargs)
        self.update_listview()
        self.topwidget.pack_start(self.listview.topwidget, expand=True)
    def unlink(self):
        self.listview.unlink()
        super(RawLogView, self).unlink()
    def update_listview(self):
        d = self.parser.parsed['entries']
        lv = self.listview
        keys = lv.column_names[1:]
        #for i, entry in d.iteritems():
        #    lv.update({i:[entry.fields.get(key, lv.list_types[kI]()) for kI, key in enumerate(keys)]})
        for dt in reversed(sorted(d.keys())):
            entry = d[dt]
            lv.update({str(dt):[entry.fields.get(key, lv.list_types[kI]()) for kI, key in enumerate(keys)]})
class SessionView(EditorBase):
    def init_editor(self, **kwargs):
        self.parser = self.root_obj.parser
        self.list_types = [str] + [str] * len(self.parser.field_names)
        self.column_names = ['id'] + self.parser.field_names
        self.store = gtk.TreeStore(*self.list_types)
        row = ['root'] + [''] * len(self.parser.field_names)
        self.iter = self.store.append(None, row)
        self.session_nodes = []
        self.update_sessions()
        self.topwidget = widgets.ScrolledWindow()
        self.widget = gtk.TreeView()
        self.widget.set_model(self.store)
        for i, key in enumerate(self.column_names):
            cell = gtk.CellRendererText()
            col = gtk.TreeViewColumn(key, cell, text=i)
            self.widget.append_column(col)
        self.topwidget.add(self.widget)
        
    def update_sessions(self):
        for session in self.parser.sessions:
            node = SessionParentNode(session=session, parent=self)
            self.session_nodes.append(node)
class SessionParentNode(object):
    def __init__(self, **kwargs):
        self.session = kwargs.get('session')
        self.parent = kwargs.get('parent')
        self.store = self.parent.store
        row = [self.session.id] + [''] * len(self.parent.parser.field_names)
        self.iter = self.store.append(self.parent.iter, row)
        self.nodes = []
        for e in self.session.entries:
            self.nodes.append(SessionEntryNode(parent=self, entry=e))
class SessionEntryNode(object):
    def __init__(self, **kwargs):
        self.entry = kwargs.get('entry')
        self.parent = kwargs.get('parent')
        self.store = self.parent.store
        root = self.parent.parent
        row = [str(self.entry.dt)]
        row += [self.entry.fields.get(key, root.list_types[i]()) for i, key in enumerate(root.column_names[1:])]
        self.iter = self.store.append(self.parent.iter, row)
        
def run(**kwargs):
    app = Application(mainwindow_kwargs=kwargs)
    app.run()
