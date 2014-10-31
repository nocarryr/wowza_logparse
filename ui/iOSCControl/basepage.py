from Bases import OSCBaseObject

class BasePage(OSCBaseObject):
    def __init__(self, **kwargs):
        self.iOsc = kwargs.get('iOsc')
        self.client = kwargs.get('client')
        self.MainController = self.iOsc.MainController
        kwargs.setdefault('osc_parent_node', self.client.osc_node)
        kwargs.setdefault('osc_address', self.__class__.__name__)
        kwargs.setdefault('ParentEmissionThread', self.iOsc.ParentEmissionThread)
        super(BasePage, self).__init__(**kwargs)
        self.x_offset = kwargs.get('x_offset', 0)
        self.y_offset = kwargs.get('y_offset', 0)
    
    def build_topwidget(self, cls, **kwargs):
        kwargs.setdefault('client', self.client)
        kwargs.setdefault('osc_parent_node', self.osc_node)
        kwargs.setdefault('ParentEmissionThread', self.ParentEmissionThread)
        self.topwidget = self.iOsc.add_widget(cls, **kwargs)
        
    def remove(self):
        self.topwidget.remove()
        self.unlink()
