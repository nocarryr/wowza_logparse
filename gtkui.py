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
        d = self.parser.sorted
        lvkwargs = dict(column_names=['dt'] + d.values()[0].keys(), 
                        list_types=[str] * (len(d.values()[0].keys()) + 1), 
                        default_sort_column=0)
        self.listview = widgets.TreeList(**lvkwargs)
        self.update_listview()
        topwidget.pack_start(self.listview.topwidget, expand=True)
        self.window.add(topwidget)
        self.window.show_all()
    def update_listview(self):
        d = self.parser.sorted
        lv = self.listview
        keys = lv.column_names[1:]
        for dt, fields in d.iteritems():
            lv.update({str(dt):[fields[key] for key in keys]})
            
def run(**kwargs):
    app = Application(mainwindow_kwargs=kwargs)
    app.run()
