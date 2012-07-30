from ui_base.gtk import gtkBaseUI
from ui_base.gtk.bases import widgets

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
        lvkwargs = dict(column_names=['id'] + self.parser.field_names, 
                        list_types=[str] + [str] * len(self.parser.field_names), 
                        default_sort_column=0)
        self.listview = widgets.TreeList(**lvkwargs)
        self.update_listview()
        topwidget.pack_start(self.listview.topwidget, expand=True)
        self.window.add(topwidget)
        self.window.show_all()
    def update_listview(self):
        d = self.parser.parsed['entries']
        lv = self.listview
        keys = lv.column_names[1:]
        #for i, entry in d.iteritems():
        #    lv.update({i:[entry.fields.get(key, lv.list_types[kI]()) for kI, key in enumerate(keys)]})
        for dt in reversed(sorted(d.keys())):
            entry = d[dt]
            lv.update({str(dt):[entry.fields.get(key, lv.list_types[kI]()) for kI, key in enumerate(keys)]})
            
def run(**kwargs):
    app = Application(mainwindow_kwargs=kwargs)
    app.run()
