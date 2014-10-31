#  This file is part of OpenLightingDesigner.
# 
#  OpenLightingDesigner is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  OpenLightingDesigner is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with OpenLightingDesigner.  If not, see <http://www.gnu.org/licenses/>.
#
# CommDispatcher.py
# Copyright (c) 2010 - 2011 Matthew Reid

import os.path
import pkgutil

from Bases import BaseObject, ChildGroup
import BaseIO
try:
    from interprocess.ServiceConnector import ServiceConnector
except:
    class ServiceConnector(BaseObject):
        def publish(self, *args, **kwargs):
            pass
        def unpublish(self, *args, **kwargs):
            pass
        def add_service(self, *args, **kwargs):
            pass
        def update_service(self, *args, **kwargs):
            pass
        def add_listener(self, *args, **kwargs):
            pass
from . import IO_CLASSES


class CommDispatcherBase(BaseIO.BaseIO):
    def __init__(self, **kwargs):
        super(CommDispatcherBase, self).__init__(**kwargs)
        self.IO_MODULES = {}
        self.IO_MODULE_UPDN_ORDER = {}
        for key in ['up', 'dn']:
            self.IO_MODULE_UPDN_ORDER[key] = ChildGroup(name=key, child_class=DummyIOObj)
        self.ServiceConnector = ServiceConnector()
    
    @property
    def SystemData(self):
        return self.GLOBAL_CONFIG.get('SystemData')
    
    @property
    def IO_CLASSES(self):
        return IO_CLASSES
        
    def do_connect(self, **kwargs):
        self.ServiceConnector.publish()
        updnobj = self.IO_MODULE_UPDN_ORDER['up'].indexed_items
        for key in sorted(updnobj.keys()):
            obj = updnobj[key].io_obj
            obj.do_connect(**kwargs)
        self.connected = True
        
    def do_disconnect(self, **kwargs):
        updnobj = self.IO_MODULE_UPDN_ORDER['dn'].indexed_items
        for key in reversed(sorted(updnobj.keys())):
            obj = updnobj[key].io_obj
            obj.do_disconnect(**kwargs)
        self.ServiceConnector.unpublish()
        self.connected = False
        
    def shutdown(self):
        updnobj = self.IO_MODULE_UPDN_ORDER['dn'].indexed_items
        for key in reversed(sorted(updnobj.keys())):
            obj = updnobj[key].io_obj
            if hasattr(obj, 'shutdown'):
                obj.shutdown()
            else:
                obj.do_disconnect(blocking=True)
        self.ServiceConnector.unpublish(blocking=True)
        self.connected = False
    
    def build_io_module(self, name, updn_order=False, **kwargs):
        cls = self.IO_CLASSES.get(name)
        if not cls:
            return
        if updn_order is True:
            updn_order = [None, None]
        kwargs.setdefault('comm', self)
        obj = cls(**kwargs)
        self.IO_MODULES[name] = obj
        if type(updn_order) in [list, tuple]:
            for i, key in enumerate(['up', 'dn']):
                index = updn_order[i]
                c_kwargs = dict(id=name, obj=obj)
                if index is not None:
                    c_kwargs['Index'] = index
                dobj = self.IO_MODULE_UPDN_ORDER[key].add_child(**c_kwargs)
        return obj
        
    def remove_io_module(self, name):
        obj = self.IO_MODULES.get(name)
        if not obj:
            return
        if hasattr(obj, 'shutdown'):
            obj.shutdown()
        else:
            obj.do_disconnect(blocking=True)
        obj.unlink()
        del self.IO_MODULES[name]
        return obj

class DummyIOObj(BaseObject):
    def __init__(self, **kwargs):
        super(DummyIOObj, self).__init__(**kwargs)
        self.id = kwargs.get('id')
        self.io_obj = kwargs.get('obj')
    
