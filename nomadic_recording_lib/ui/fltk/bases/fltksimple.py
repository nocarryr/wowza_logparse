from Bases import BaseObject
from ui_base.bases import simple

gui_thread = BaseObject().GLOBAL_CONFIG.get('GUIThread')

class Toggle(simple.Toggle):
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = gui_thread
        super(Toggle, self).__init__(**kwargs)
