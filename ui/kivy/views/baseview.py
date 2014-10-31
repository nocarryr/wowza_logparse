from Bases import BaseObject

class BaseView(BaseObject):
    def __init__(self, **kwargs):
        super(BaseView, self).__init__(**kwargs)
        self.MainController = kwargs.get('MainController')
        self.editors = set()
        self.init_view(**kwargs)
        self.topwidget.size_hint_y = 1.
        
    def init_view(self, **kwargs):
        pass
        
    def add_editor(self, cls, name, **kwargs):
        kwargs.setdefault('MainController', self.MainController)
        obj = cls(**kwargs)
        self.editors.add(obj)
        setattr(self, name, obj)
        return obj
        
    def remove_editor(self, obj):
        obj.unlink()
        topw = getattr(obj, 'topwidget', None)
        if topw and topw.parent:
            topw.parent.remove_widget(topw)
        self.editors.discard(obj)
        
    def unlink(self):
        for e in self.editors:
            e.unlink()
