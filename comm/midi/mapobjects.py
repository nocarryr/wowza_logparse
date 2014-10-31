#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# mapobjects.py
# Copyright (c) 2011 Matthew Reid

from Bases import BaseObject, setID
from Bases.Properties import PropertyConnector

import messages


class MapObject(BaseObject, PropertyConnector):
    _Properties = {'name':dict(type=str), 
                   '_Index':dict(type=int), 
                   'map_type':dict(type=str), 
                   'channel':dict(type=int, min=0, max=15)}
    _SettingsProperties = ['Index', '_Index', 'map_type', 'name', 'channel']
    _saved_attributes = ['id']
    _map_attrs = ['map_type', 'channel']
    def __init__(self, **kwargs):
        self.value_changed_by_midi = False
        cls = self.__class__
        map_attrs = []
        while cls != MapObject:
            if hasattr(cls, '_map_attrs'):
                attrs = cls._map_attrs[:]
                attrs.reverse()
                map_attrs.extend(attrs)
            cls = cls.__bases__[0]
        attrs = MapObject._map_attrs[:]
        attrs.reverse()
        map_attrs.extend(attrs)
        map_attrs.reverse()
        self.map_attrs = map_attrs
        self.in_devices = set(kwargs.get('in_devices', []))
        self.out_devices = set(kwargs.get('out_devices', []))
        
        super(MapObject, self).__init__(**kwargs)
        if 'deserialize' not in kwargs:
            self._Index = kwargs.get('_Index')
            self.name = kwargs.get('name', str(self._Index))
            self.channel = kwargs.get('channel', 0)
            #self.id = setID(kwargs.get('id'))
        self.all_inputs = kwargs.get('all_inputs', True)
        self.all_outputs = kwargs.get('all_outputs', True)
        self.init_map(**kwargs)
        if 'deserialize' not in kwargs:
            self.id = kwargs.get('id', '%s:%s' % (self.map_type, zip(self.map_attrs, [getattr(self, attr) for attr in self.map_attrs])))
            
        #for dev in self.in_devices:
        #    dev.bind(msg_received=self.on_msg_received)
        
    def unlink(self):
        self.Property = None
        for dev in self.in_devices:
            dev.unbind(self)
        super(MapObject, self).unlink()
        
    def attach_Property(self, prop):
        super(MapObject, self).attach_Property(prop)
        self.value_changed_by_midi = True
        self.on_Property_value_changed()
        self.value_changed_by_midi = False
        self.send_message()
        
    def detach_Property(self, prop):
        super(MapObject, self).detach_Property(prop)
        self.value_changed_by_midi = True
        self.on_Property_value_changed()
        self.value_changed_by_midi = False
        self.send_message()
        
    def send_message(self):
        if self.value_changed_by_midi:
            return
        #if not len(self.out_devices):
        #    return
        msg = self.build_message()
        #print msg.build_data()
        for dev in self.out_devices:
            dev.send(data=msg.build_data(), msg=msg)
        
#    def on_msg_received(self, **kwargs):
#        msg = kwargs.get('msg')
#        if not hasattr(msg, 'channel') or msg.channel != self.channel:
#            return
#        self.process_message(msg)

    def is_message_valid(self, msg):
        return isinstance(msg, messages.ChannelMessage) and msg.channel == self.channel
        
    def process_message(self, msg):
        if not self.is_message_valid(msg):
            return
        self.value_changed_by_midi = True
        self._process_message(msg)
        self.value_changed_by_midi = False
    
class NoteMapObject(MapObject):
    _saved_class_name = 'NoteMapObject'
    _Properties = {'note':dict(type=int, min=0, max=127), 
                   'state':dict(default=False), 
                   'velocity':dict(default=100, min=0, max=127)}
    _SettingsProperties = ['note']
    _map_attrs = ['note']
    map_type = 'Note'
    def init_map(self, **kwargs):
        #self.map_type = 'Note'
        if 'deserialize' not in kwargs:
            self.note = kwargs.get('note', 0)
        v = kwargs.get('velocity')
        if v is not None:
            self.velocity = v
        self.bind(state=self._on_state_set, 
                  velocity=self._on_velocity_set)
        
    def attach_Property(self, prop):
        oldv = self.velocity
        super(NoteMapObject, self).attach_Property(prop)
        if oldv == 0:
            self.velocity = 100
        
    def _on_state_set(self, **kwargs):
        if self.Property is None:
            return
        state = kwargs.get('value')
        if self.Property.type == bool:
            self.set_Property_value(state)
        else:
            value = self.Properties['velocity'].normalized_and_offset
            self.Property.normalized_and_offset = value
        self.send_message()
        
    def _on_velocity_set(self, **kwargs):
        value = kwargs.get('value')
        if value == 0:
            self.state = False
        
    def on_Property_value_changed(self, **kwargs):
        if self.Property is None:
            self.velocity = 0
            self.state = False
            return
        value = self.get_Property_value()
        if self.Property.type == bool:
            self.state = value
        else:
            self.Properties['velocity'].normalized_and_offset = self.Property.normalized_and_offset
            state = value > self.Property.min
            if state != self.state:
                self.state = state
            else:
                self.send_message()
            
    def is_message_valid(self, msg):
        valid = isinstance(msg, messages.NoteMessage) and msg.note == self.note
        return valid and super(NoteMapObject, self).is_message_valid(msg)
        
    def _process_message(self, msg):
        state = isinstance(msg, messages.NoteOnMessage)
        if state:
            self.velocity = msg.velocity
            self.state = True
        else:
            self.velocity = 0
        #self.state = state
        
    def build_message(self):
        if self.state:
            cls = messages.NoteOnMessage
        else:
            cls = messages.NoteOffMessage
        msg = cls(channel=self.channel, note=self.note, velocity=self.velocity)
        return msg
        
class ControllerMapObject(MapObject):
    _saved_class_name = 'ControllerMapObject'
    _Properties = {'controller':dict(type=int, min=1, max=127), 
                   'value':dict(default=0, min=0, max=127, quiet=True)}
    _SettingsProperties = ['controller']
    _map_attrs = ['controller']
    map_type = 'Control'
    def init_map(self, **kwargs):
        #self.map_type = 'Control'
        if 'deserialize' not in kwargs:
            self.controller = kwargs.get('controller', 1)
        self.bind(value=self._on_value_set)
        
    def _on_value_set(self, **kwargs):
        if self.Property is None:
            return
        prop = kwargs.get('Property')
        self.Property.normalized_and_offset = prop.normalized_and_offset
        self.send_message()
        
    def on_Property_value_changed(self, **kwargs):
        if self.Property is None:
            self.value = 0
            return
        prop = self.Properties['value']
        prop.normalized_and_offset = self.Property.normalized_and_offset
        
    def is_message_valid(self, msg):
        valid = isinstance(msg, messages.ControlMessage) and msg.controller == self.controller
        return valid and super(ControllerMapObject, self).is_message_valid(msg)
        
    def _process_message(self, msg):
        self.value = msg.value
        
    def build_message(self):
        msg = messages.ControlMessage(channel=self.channel, 
                                      controller=self.controller, 
                                      value=self.value)
        return msg


MAP_CLASSES = (NoteMapObject, ControllerMapObject)
MAPS_BY_TYPE = dict(zip([cls.map_type for cls in MAP_CLASSES], MAP_CLASSES))
MAPS_BY_CLASS_NAME = dict(zip([cls._saved_class_name for cls in MAP_CLASSES], MAP_CLASSES))
