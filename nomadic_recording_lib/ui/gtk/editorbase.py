from Bases import BaseObject
from bases import widgets

class EditorBase(BaseObject):
    def __init__(self, **kwargs):
        super(EditorBase, self).__init__(**kwargs)
        self.parent_editor = kwargs.get('parent_editor')
        self.root_obj = kwargs.get('root_obj', getattr(self.parent_editor, 'root_obj', None))
        self.child_editors = {}
        lbl = getattr(self.__class__, 'topwidget_label', None)
        if lbl is None:
            lbl = getattr(self, 'topwidget_label', kwargs.get('topwidget_label', ''))
        frame = widgets.Frame(label=lbl)
        self.topwidget = kwargs.get('topwidget', frame)
        self.init_editor(**kwargs)
        self.topwidget.show_all()
    def make_child_editor(self, cls, name, **kwargs):
        kwargs.setdefault('parent_editor', self)
        obj = cls(**kwargs)
        self.child_editors.update({name:obj})
        return obj
    def remove_child_editor(self, name):
        child = self.child_editors.get(name)
        if child is None:
            return
        child.unlink()
        p = child.topwidget.get_parent()
        p.remove(child.topwidget)
        del self.child_editors[name]
    def unlink(self):
        for child in self.child_editors.itervalues():
            child.unlink()
    def __repr__(self):
        s = '<Editor Object'
        twname = getattr(self, 'topwidget_label', None)
        if type(twname) == str:
            s = ' '.join([s, twname])
        else:
            s = ' '.join([s,  self.__class__.__name__])
        return '%s at (%s)>' % (s, id(self))
        
EDITORS = {}

def add_editor(cls, name=None):
    if name is None:
        name = getattr(cls, 'saved_class_name', cls.__name__)
    EDITORS[name] = cls
    
