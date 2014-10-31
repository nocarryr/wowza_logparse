from base import gstBase

class Element(gstBase):
    def __init__(self, **kwargs):
        super(Element, self).__init__(**kwargs)
        self.gst_name = kwargs.get('gst_name')
        self.gst_properties = kwargs.get('gst_properties', {})
        caps_str = kwargs.get('caps_str')
        args = [self.gst_name, ]
        if self.name != 'Element':
            args.append(self.name)
        self._element = self._gst_module.element_factory_make(*args)
        if self.name is None:
            self.name = self._element.get_name()
        for key, val in self.gst_properties.iteritems():
            self._element.set_property(key, val)
        if caps_str is not None:
            self.set_caps(caps_str=caps_str)
    def set_caps(self, **kwargs):
        caps_str = kwargs.get('caps_str')
        caps = self._gst_module.Caps(caps_str)
        self._element.set_property('caps', caps)
