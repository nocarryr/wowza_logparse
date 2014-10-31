import sys
import os.path
import imp

from Bases import BaseObject, setID

if 'jhbuild' in sys.argv:
    path = os.path.expanduser('~/src/gstreamer/install/lib/python2.7/site-packages/gst-0.10')
    t = imp.find_module('gst', [path])
    gst = imp.load_module('gst', *t)
else:
    import gst

class gstBase(BaseObject):
    def __init__(self, **kwargs):
        super(gstBase, self).__init__(**kwargs)
        self.id = setID(kwargs.get('id'))
        if not hasattr(self, 'name'):
            self.name = kwargs.get('name', self.__class__.__name__)
        #self._gst_module = kwargs.get('_gst_module')
        self._gst_module = gst
