from Bases import ChildGroup
from bin import Bin



class Pipeline(Bin):
    _Properties = {'pipeline_state':dict(default='null')}
    base_class = 'Pipeline'
    def __init__(self, **kwargs):
        self.bin_data = kwargs.get('bin_data', [])
        if len(self.bin_data):
            kwargs['simple_links'] = False
        super(Pipeline, self).__init__(**kwargs)
        
        statekeys = ['NULL', 'PAUSED', 'PLAYING', 'READY', 'VOID_PENDING']
        gststates = [int(getattr(self._gst_module, '_'.join(['STATE', key]))) for key in statekeys]
        self.gst_state_map = dict(zip(gststates, [key.lower() for key in statekeys]))
        
        self.Bins = ChildGroup(name='Bins', child_class=Bin)
        for bindata in self.bin_data:
            if isinstance(bindata, Bin):
                bindata = {'existing_object':bindata}
            self.add_bin(**bindata)
        self.link_bins()
            
        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self.on_bus_message)
        self.bind(pipeline_state=self.on_pipeline_state)
        
    def on_pipeline_state(self, **kwargs):
        #print kwargs
        pass
        
    def init_instance(self, **kwargs):
        self._pipeline = self._gst_module.Pipeline(self.name)
        self.elem_container = self._pipeline
        
    def add_bin(self, **kwargs):
        bin = self.Bins.add_child(**kwargs)
        self.elem_container.add(bin.elem_container)
        
    def link_bins(self):
        if len(self.Bins) < 2:
            return
        for index, bin in self.Bins.indexed_items.iteritems():
            nextbin = self.Bins.indexed_items.get(index+1)
            if nextbin is None:
                continue
            #print index, bin.name, nextbin.name
            try:
                bin.elem_container.link(nextbin.elem_container)
            except:
                print 'could not link %s with %s' % (bin.name, nextbin.name)
                continue
                
#            for i, src in enumerate(bin.GhostPads['src']):
#                if len(nextbin.GhostPads['sink']) <= i - 1:
#                    print src.get_name(), ' linking to ', nextbin.GhostPads['sink'][i].get_name()
#                    src.link(nextbin.GhostPads['sink'][i])
                
        
    def on_bus_message(self, bus, message):
        self.pipeline_state = self.gst_state_map.get(int(self._pipeline.get_state()[1]))
        #print 'bus message: ', self.pipeline_state, self._pipeline.get_state()
        
    def start(self):
        self._pipeline.set_state(self._gst_module.STATE_PLAYING)
    def stop(self):
        self._pipeline.set_state(self._gst_module.STATE_NULL)
        self.pipeline_state = 'null'
        
