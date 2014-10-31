from ..gtkBaseUI import BaseContainer
from ..bases import widgets


class BaseView(BaseContainer):
    def __init__(self, **kwargs):
        super(BaseView, self).__init__(**kwargs)
        self.MainController = kwargs.get('MainController')
        self.editors = {}
        
    def add_editor(self, cls, name, **kwargs):
        kwargs.setdefault('MainController', self.MainController)
        obj = cls(**kwargs)
        self.editors[id(obj)] = (name, obj)
        setattr(self, name, obj)
        return obj
        
    def remove_editor(self, obj):
        if type(obj) == str:
            obj = getattr(self, obj, None)
        if obj is None:
            return
        obj.unlink()
        topw = getattr(obj, 'topwidget', None)
        if topw and topw.get_parent():
            topw.get_parent().remove(topw)
        name = self.editors[id(obj)][0]
        del self.editors[id(obj)]
        if getattr(self, name, None) is not None:
            setattr(self, name, None)
        
    def unlink(self):
        for eid, e in self.editors.itervalues():
            e.unlink()
        super(BaseView, self).unlink()

class BlankView(BaseView):
    topwidget_name = 'Blank'
    topwidget_cls = widgets.VBox
    def __init__(self, **kwargs):
        self.topwidget = widgets.VBox()
        super(BlankView, self).__init__(**kwargs)
        self.drawingarea = widgets.DrawingArea()
        self.topwidget.pack_start(self.drawingarea, expand=True)
        
UI_VIEW = BlankView
