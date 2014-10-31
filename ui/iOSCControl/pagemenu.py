from Bases import OSCBaseObject, ChildGroup
import widgets

#from pages.groups import GroupMasters
#from pages.cuestacks import CueStacks
#from pages.groupcontrol import GroupControl
#from pages.devicecontrol import DeviceControl
#from pages.palettes import Palettes
#from pages.setup import Setup
#
#PAGES = (GroupMasters, CueStacks, GroupControl, DeviceControl, Palettes, Setup)
PAGES = []

class PageMenu(OSCBaseObject):
    #button_size = dict(w=.2, h=.05)
    def __init__(self, **kwargs):
        self.iOsc = kwargs.get('iOsc')
        self.client = kwargs.get('client')
        self.current_page = None
        kwargs.setdefault('osc_parent_node', self.client.osc_node)
        kwargs.setdefault('osc_address', 'PageMenu')
        kwargs.setdefault('ParentEmissionThread', self.iOsc.ParentEmissionThread)
        super(PageMenu, self).__init__(**kwargs)
        self.x_offset = kwargs.get('x_offset', 0.)
        self.y_offset = kwargs.get('y_offset', 0.)
        #w = self.button_size['w'] * len(PAGES)
        self.button_size = dict(h=.05, w=1./len(PAGES))
        h = self.button_size['h']
        bounds = [self.x_offset, self.y_offset, 1, h]
        self.topwidget = self.iOsc.add_widget('Label', 
                                              name='PageMenu', 
                                              bounds=bounds, 
                                              osc_parent_node=self.osc_parent_node, 
                                              client=self.client)
        self.btn_topwidget = self.topwidget.add_widget(widgets.Label, name='select_buttons', bounds=bounds)
        self.menu_buttons = ChildGroup(name='select_buttons', osc_parent_node=self.osc_node)
        for i, cls in enumerate(PAGES):
            btn = self.btn_topwidget.add_widget(MenuButton, Index=i, page_cls=cls, parent=self)
            self.menu_buttons.add_child(existing_object=btn)
            btn.bind(touch_state=self.on_menu_button_touch_state)
            
    def unlink(self):
        self.set_current_page(None)
        self.topwidget.remove()
        super(PageMenu, self).unlink()
        
    def set_current_page(self, cls):
        if self.current_page is not None:
            self.current_page.remove()
            self.current_page = None
        if cls is not None:
            self.current_page = cls(iOsc=self.iOsc, client=self.client, y_offset=self.y_offset + self.button_size['h'] + .01)
            
    def on_menu_button_touch_state(self, **kwargs):
        btn = kwargs.get('obj')
        state = kwargs.get('value')
        if state:
            self.set_current_page(btn.cls)
            for w in self.menu_buttons.itervalues():
                if w != btn:
                    w.touch_state = False
            
class MenuButton(widgets.Toggle):
    def __init__(self, **kwargs):
        self.parent = kwargs.get('parent')
        self.cls = kwargs.get('page_cls')
        i = kwargs.get('Index')
        w = self.parent.button_size['w']
        h = self.parent.button_size['h']
        x = (i * w) + self.parent.x_offset
        y = self.parent.y_offset
        kwargs.setdefault('bounds', [x, y, w, h])
        kwargs.setdefault('label', self.cls.page_name)
        kwargs.setdefault('name', self.cls.page_name)
        super(MenuButton, self).__init__(**kwargs)
