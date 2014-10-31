from Bases import BaseObject

class Application(BaseObject):
    def __init__(self, **kwargs):
        super(Application, self).__init__(**kwargs)
        self.register_signal('start', 'exit')
        self.name = kwargs.get('name', self.GLOBAL_CONFIG.get('app_name'))
        self.app_id = kwargs.get('app_id', self.GLOBAL_CONFIG.get('app_id'))
        self.mainwindow_cls = kwargs.get('mainwindow_cls')
        self.mainwindow_kwargs = kwargs.get('mainwindow_kwargs', {})
        self.GLOBAL_CONFIG['GUIApplication'] = self
        if not hasattr(self, '_application'):
            self._application = None
    
    def _build_mainwindow(self, **kwargs):
        kwargs.setdefault('Application', self)
        mw = self.mainwindow_cls(**kwargs)
        return mw
        
    def start_GUI_loop(self, join=False):
        pass
        
    def stop_GUI_loop(self):
        pass
        
    def run(self, join=False):
        mwkwargs = self.mainwindow_kwargs.copy()
        self.mainwindow = self._build_mainwindow(**mwkwargs)
        self.emit('start')
        self.start_GUI_loop(join)
        
    def on_mainwindow_close(self, *args, **kwargs):
        self.stop_ParentEmissionThread()
        self.stop_GUI_loop()
        self.emit('exit')

from bases.widgets import get_widget_classes, get_container_classes

widget_classes = get_widget_classes()
container_classes = get_container_classes()

class BaseWindow(BaseObject):
    _Properties = {'title':dict(default=''), 
                   'size':dict(default=[1150, 800]), 
                   'position':dict(default=[40, 40]), 
                   'fullscreen':dict(default=False)}
    def __init__(self, **kwargs):
        kwargs['ParentEmissionThread'] = kwargs['Application'].ParentEmissionThread
        super(BaseWindow, self).__init__(**kwargs)
        self.window = self._build_window(**kwargs)
        self.bind(property_changed=self._on_own_property_changed)
        self._Application = None
        self.Application = kwargs.get('Application')
        #for key in ['size', 'window_size']:
        #    if hasattr(self, key):
        #        kwargs.setdefault('size', getattr(self, key))
        size = kwargs.get('size')
        if type(size) in [list, tuple]:
            self.size = list(kwargs.get('size'))
        self.title = kwargs.get('title')
        
    @property
    def Application(self):
        return self._Application
    @Application.setter
    def Application(self, value):
        old = self.Application
        self._Application = value
        self._Application_set(old, value)
        self.title = self.Application.name
        
    def _Application_set(self, old, new):
        pass
        
    def _build_window(self, **kwargs):
        pass
        
    def _on_own_property_changed(self, **kwargs):
        pass

class BaseContainer(BaseObject):
    def __init__(self, **kwargs):
        super(BaseContainer, self).__init__(**kwargs)
        self._topwidget_name = kwargs.get('topwidget_name', self.__class__.__dict__.get('topwidget_name'))
        self._topwidget_cls = kwargs.get('topwidget_cls', self.__class__.__dict__.get('topwidget_cls'))
        topwidget_kwargs = kwargs.get('topwidget_kwargs', self.__class__.__dict__.get('topwidget_kwargs', {}))
        
        if not hasattr(self, 'container_classes'):
            self.container_classes = container_classes
        #self.topwidget = self.container_classes['Frame'](label=self._topwidget_name)
        if kwargs.get('Expander', True):
            clsname = 'Expander'
        else:
            clsname = 'Frame'
            
        if not hasattr(self, 'topwidget'):
            self.topwidget = self.container_classes[clsname](label=self._topwidget_name)
        
        self.topcontainer = self._topwidget_cls(**topwidget_kwargs)
        #print self._topwidget_name, self._topwidget_cls, topwidget_kwargs
        self.topwidget.pack_start(self.topcontainer, expand=True)
        self._child_widgets = {}
        self._child_widgets_locations = {}
        #self.topwidget.show_all()
    
    def add_child(self, widget, **kwargs):
        kwargs.setdefault('expand', False)
        self.topcontainer.pack_start(widget, **kwargs)
            
    def make_child_widget(self, cls, widget_name, **kwargs):
        widget = cls(**kwargs)
        self._child_widgets.update({widget_name:widget})
        return widget
        
    def remove_child_widget(self, widget_name):
        widget = self._child_widgets.get(widget_name)
        if widget is not None:
            widget.get_parent().remove(widget)
            del self._child_widgets[widget_name]
            return True
        return False
    

class ControlContainer(BaseContainer):
    def __init__(self, **kwargs):
        if not hasattr(self, 'container_classes'):
            self.container_classes = kwargs.get('container_classes', get_container_classes())
        if not hasattr(self, 'widget_classes'):
            self.widget_classes = kwargs.get('widget_classes', get_widget_classes())
        self.section = kwargs.get('section')
        size = self.section.container_size
        if size is not None:
            twkwargs = kwargs.get('topwidget_kwargs', {})
            twkwargs.update({'rows':size[0], 'columns':size[1]})
            kwargs.setdefault('topwidget_kwargs', twkwargs)
        kwargs.setdefault('topwidget_name', self.section.name)
        kwargs.setdefault('topwidget_cls', self.container_classes.get(self.section.container_widget, 'VBox'))
        
        
        
        
        #new_kwargs = kwargs.copy()
        #new_kwargs.update({'topwidget_cls':self.container_classes['VBox']})
        
        #if hasattr(self.section, 'container_widget'):
        #    cls = self.container_classes.get(self.section.container_widget)
        #    if cls is not None:
        #        new_kwargs.update({'topwidget_cls':cls})
        super(ControlContainer, self).__init__(**kwargs)
        self.topwidget.set_label(self.section.name)
        self.controls = {}
        self.containers = {}
        self.children = {}
        if self.section.params_by_group is not None:
            for group in self.section.params_by_group.iterkeys():
                self.controls.update({group:{}})
        self.build_controls()
        if len(self.section.children) > 0:
            self.build_children()
        self.topwidget.show_all()
    def build_controls(self):
        for key, val in self.section.param_info.iteritems():
            widget = val.get('widget')
            if widget is not None and widget in self.widget_classes:
                cls = self.widget_classes[widget]
                if key in self.section.parameters:
                    param = self.section.parameters[key]
                
                obj = cls(parameter=param)
                if self.section.params_by_group is not None:
                    group = val['param_group_name']
                    index = val['param_group_index']
                    self.controls[group].update({index:obj})
                else:
                    self.controls.update({key:obj})
        self.add_controls()
    def add_controls(self):
        boxsize = self.section.container_size
        boxcls = self.container_classes.get(self.section.container_widget, self.container_classes['VBox'])
        boxkwargs = {}
        if boxsize is not None:
            boxkwargs.update({'columns':boxsize[0], 'rows':boxsize[1]})
        box = boxcls(**boxkwargs)
        if self.section.params_by_group is not None:
            #for grKey, grVal in self.controls.iteritems():
            for x, grKey in enumerate(self.section.param_group_order):
                grVal = self.controls[grKey]
                grinfo = self.section.param_group_containers.get(grKey, {})
                cls = self.container_classes.get(grinfo.get('cls', 'VBox'))
                size = grinfo.get('size')
                d = {}
                if size is not None:
                    d.update({'rows':size[1], 'columns':size[0]})
                grBox = cls(**d)
                for cKey, cVal in grVal.iteritems():
                    #if 'widget_packing' in cVal.__dict__:
                    #    print cVal.parameter.name, cVal.widget_packing
                    pack_kwargs = cVal.__dict__.get('widget_packing', {})
                    
                    grBox.pack_start(cVal.topwidget, **pack_kwargs)
                    #print 'group %s,  child %s, index %s, name %s' % (grKey, cKey, x, cVal.parameter.name)
                #frame = self.container_classes['Frame']()
                #frame.pack_start(box, expand=True)
                boxkwargs = grinfo.get('kwargs', {})
                box.pack_start(grBox, **boxkwargs)
            self.add_child(box, expand=True)
            box.show_all()
            self.containers.update({grKey:box})
        else:
            for val in self.controls.itervalues():
                pack_kwargs = val.__dict__.get('widget_packing', {})
                self.add_child(val.topwidget, **pack_kwargs)
                
    def build_children(self):
        cinfo = self.section.child_container
        size = cinfo.get('size')
        cboxkwargs = {}
        if size is not None:
            cboxkwargs.update({'rows':size[1], 'columns':size[0]})
        cbox = self.container_classes.get(cinfo.get('cls', 'VBox'))(**cboxkwargs)
        #print 'name %s,cboxclass %s, kwargs %s' % (self.section.name, cinfo.get('cls'), cboxkwargs)
        #for key, val in self.section.children.iteritems():
        keys = self.section.child_order
        if keys is None:
            keys = self.section.children.keys()
        for key in keys:
            val = self.section.children[key]
            self.children.update({key:{}})
            for cKey, cVal in val.iteritems():
                #topwidget = self.container_classes.get(cVal.container_widget, self.container_classes['VBox'])
                #topwidget = self.container_classes['Frame']
                #topwidget = self.container_classes.get(cVal.container_widget, self.container_classes['VBox'])
                #twkwargs = {}
                #if cVal.container_size is not None:
                #    twkwargs.update({'rows':cVal.container_size[0], 'columns':cVal.container_size[1]})
                #if topwidget is None:
                #    topwidget = VBox
                child = ControlContainer(section=cVal, 
                                         container_classes=self.container_classes, 
                                         widget_classes=self.widget_classes)
                #self.add_child(child.topwidget)
                cbox.pack_end(child.topwidget)
                self.children[key].update({cKey:child})
            self.add_child(cbox)
    def unload(self):
        if self.section.params_by_group is not None:
            for group in self.controls.itervalues():
                for control in group.itervalues():
                    control.unlink()
        else:
            for control in self.controls.itervalues():
                control.unlink()
        for cType in self.children.itervalues():
            for child in cType.itervalues():
                child.unload()
        del self.section
        del self.children
