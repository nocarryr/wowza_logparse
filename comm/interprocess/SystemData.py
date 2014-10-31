import socket
import uuid

from Bases import BaseObject

class SystemData(BaseObject):
    _Properties = {'name':dict(default=''),
                   'id':dict(type=str),
                   'appname':dict(type=str),
                   'address':dict(ignore_type=True),
                   'hostname':dict(type=str)}
    def __init__(self, **kwargs):
        super(SystemData, self).__init__(**kwargs)
        self.global_config_key_map = {}
        self.bind(property_changed=self._on_own_property_changed)
        d = {'name':{'default':socket.gethostname()},
             'id':{'default':uuid.uuid4().urn},
             'appname':{'default':'', 'gckey':'app_name'}}
        for key, val in d.iteritems():
            value = kwargs.get(key)
            gckey = val.get('gckey')
            if gckey is not None:
                self.global_config_key_map[key] = gckey
            if value is None and gckey is not None:
                value = self.GLOBAL_CONFIG.get(gckey)
            if value is None:
                value = val['default']
            setattr(self, key, value)
        if self.hostname is None:
            self.hostname = '.'.join([self.name, 'local'])
        self.GLOBAL_CONFIG.bind(update=self.on_GLOBAL_CONFIG_update)

    def on_GLOBAL_CONFIG_update(self, **kwargs):
        for key, gckey in self.global_config_key_map.iteritems():
            gcval = self.GLOBAL_CONFIG.get(gckey)
            if gcval == getattr(self, key):
                continue
            setattr(self, key, gcval)
        
    def _on_own_property_changed(self, **kwargs):
        prop = kwargs.get('Property')
        value = kwargs.get('value')
        gckey = self.global_config_key_map.get(prop.name)
        if gckey is None:
            return
        if self.GLOBAL_CONFIG.get(gckey) != value:
            self.GLOBAL_CONFIG[gckey] = value
            
