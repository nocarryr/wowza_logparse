from Bases import ChildGroup

from base import gstBase
from element import Element

class Bin(gstBase):
    base_class = 'Bin'
    def __init__(self, **kwargs):
        super(Bin, self).__init__(**kwargs)
        if not hasattr(self, 'element_data'):
            self.element_data = kwargs.get('element_data', [])
        self.simple_links = kwargs.get('simple_links', True)
        if self.base_class == 'Bin':
            self._bin = self._gst_module.Bin(self.name)
            self.elem_container = self._bin
            
        self.Elements = ChildGroup(name='Elements', child_class=Element)
        self.unlinked_elements = {}
        self.init_instance(**kwargs)
        self.build_elements()
        self.link_elements()
        if self.base_class == 'Bin':
            self.enable_ghost_pads = set(kwargs.get('enable_ghost_pads', ['src', 'sink']))
            self.build_ghost_pads()
            
    def build_ghost_pads(self):
        padmap = {self._gst_module.PAD_SINK:'sink', 
                  self._gst_module.PAD_SRC:'src'}
        self.GhostPads = {'sink':[], 'src':[]}
        elems = {'sink':self.Elements.indexed_items.values()[0], 
                 'src':self.Elements.indexed_items.values()[-1:][0]}
        for key, elem in elems.iteritems():
            if key not in self.enable_ghost_pads:
                continue
            for p in elem._element.pads():
                direction = padmap.get(p.get_direction())
                if direction != key:
                    continue
                name = ''.join(['Ghost', p.get_name()])
                gpad = self._gst_module.GhostPad(name, p)
                self.elem_container.add_pad(gpad)
                self.GhostPads[key].append(gpad)
                
    def init_instance(self, **kwargs):
        pass
    def build_elements(self):
        for edata in self.element_data:
            if isinstance(edata, Element):
                edata = {'existing_object':edata}
            elif type(edata) == str:
                edata = {'gst_name':edata}
            self.add_element(**edata)
    def link_elements(self):
        if not self.simple_links or len(self.Elements) < 2:
            return
        for i, elem in self.Elements.indexed_items.iteritems():
            nextelem = self.Elements.indexed_items.get(i+1)
            if nextelem is None:
                continue
            try:
                elem._element.link(nextelem._element)
            except:
                sigs = []
                for e in [elem, nextelem]:
                    sigs.append(e._element.connect('pad-added', self.on_element_pad_added, i))
                self.unlinked_elements[i] = ((elem, nextelem), sigs)
    def add_element(self, **kwargs):
        element = self.Elements.add_child(**kwargs)
        self.elem_container.add(element._element)
    def on_element_pad_added(self, element, pad, index):
        if index not in self.unlinked_elements:
            return
        elems, gsignals = self.unlinked_elements.get(index)
        try:
            elems[0]._element.link(elems[1]._element)
            for e, sig in zip(elems, gsignals):
                e.disconnect(sig)
            del self.unlinked_elements[index]
        except:
            return
            
