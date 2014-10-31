from Bases import OSCBaseObject
import widgets

class SessionSelect(OSCBaseObject):
    _Properties = {'selection':dict(type=str, quiet=True)}
    def __init__(self, **kwargs):
        self.iOsc = kwargs.get('iOsc')
        self.client = kwargs.get('client')
        kwargs.setdefault('osc_parent_node', self.client.osc_node)
        kwargs.setdefault('osc_address', 'SessionSelect')
        kwargs.setdefault('ParentEmissionThread', self.iOsc.ParentEmissionThread)
        super(SessionSelect, self).__init__(**kwargs)
        x = .25
        y = .1
        w = .25
        h = .1
        bounds = [x, y, w, h]
        self.topwidget = self.iOsc.add_widget('Label', 
                                              name='topwidget', 
                                              bounds=bounds, 
                                              osc_parent_node=self.osc_node, 
                                              client=self.client, 
                                              value='Select Session')
        self.session_btns = {}
        sessions = sorted(self.iOsc.comm.osc_io.discovered_sessions.keys())
        for i, key in enumerate(sessions):
            if key is None:
                continue
            y += h
            bounds = [x, y, w, h]
            btn = self.topwidget.add_widget(SessionButton, name=key, index=i, bounds=bounds)
            self.session_btns[key] = btn
            btn.bind(touch_state=self.on_session_btn_touch)
            
    def unlink(self):
        self.topwidget.remove()
        super(SessionSelect, self).unlink()
        
    def on_session_btn_touch(self, **kwargs):
        state = kwargs.get('value')
        btn = kwargs.get('obj')
        if state and self.selection is None:
            self.selection = btn.name
            self.LOG.info(self.selection)
            
class SessionButton(widgets.Toggle):
    def __init__(self, **kwargs):
        self.index = kwargs.get('index')
        kwargs['label'] = kwargs['name']
        super(SessionButton, self).__init__(**kwargs)
        
