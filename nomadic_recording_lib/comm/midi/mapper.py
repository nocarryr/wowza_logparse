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
# mapper.py
# Copyright (c) 2011 Matthew Reid

from Bases import BaseObject, ChildGroup, setID
from Bases.Properties import PropertyConnector

import messages
import mapobjects

class MidiMapper(BaseObject):
    _saved_class_name = 'MidiMapper'
    _saved_child_objects = ['Map']
    _saved_child_classes = list(mapobjects.MAP_CLASSES)
    _saved_attributes = ['ActiveAutoMappers']
    _ChildGroups = {'Map':{}}
    def __init__(self, **kwargs):
        self._MainController = None
        self._AutoMapper = None
        self.AutoMappers = {}
        self._ActiveAutoMappers = set()
        self.applying_automapper = False
        self.automap_presets = dict(zip([p.name for p in AUTOMAP_PRESETS], AUTOMAP_PRESETS))
        self.map_dict = {}
        self.map_types = mapobjects.MAPS_BY_TYPE.keys()
        self.midi_io = kwargs.get('midi_io')
        super(MidiMapper, self).__init__(**kwargs)
        
        #self.Map = ChildGroup(name='Map')
        
        #self.Map.bind(child_update=self.on_Map_child_update)
        self.midi_io.bind(msg_received=self.on_midi_msg_received, 
                          connected=self.on_midi_io_connected)
        self.midi_io.devices['in'].bind(child_update=self.on_in_devies_child_update)
        self.midi_io.devices['out'].bind(child_update=self.on_out_devies_child_update)
        
#    @property
#    def AutoMapper(self):
#        return self._AutoMapper
#    @AutoMapper.setter
#    def AutoMapper(self, value):
#        cls = self.automap_presets.get(value)
#        if self.AutoMapper is not None:
#            self.AutoMapper.unlink()
#        if cls is None:
#            self._AutoMapper = None
#            return
#        self.applying_automapper = True
#        self._AutoMapper = cls(Mapper=self)
#        self.applying_automapper = False
    @property
    def ActiveAutoMappers(self):
        return self._ActiveAutoMappers
    @ActiveAutoMappers.setter
    def ActiveAutoMappers(self, value):
        if len(self.ActiveAutoMappers):
            for name in list(self.ActiveAutoMappers):
                self.del_AutoMapper(name)
        self._ActiveAutoMappers = value
        if len(self.ActiveAutoMappers):
            for name in self.ActiveAutoMappers:
                self.add_AutoMapper(name)
    def add_AutoMapper(self, name):
        if name in self.AutoMappers:
            return self.AutoMappers[name]
        cls = self.automap_presets.get(name)
        self.applying_automapper = True
        self.ActiveAutoMappers.add(name)
        obj = cls(Mapper=self)
        self.AutoMappers[name] = obj
        self.applying_automapper = False
        return obj
    def del_AutoMapper(self, name):
        self.ActiveAutoMappers.discard(name)
        obj = self.AutoMappers.get(name)
        if obj is None:
            return
        obj.unlink()
        del self.AutoMappers[name]
#    @property
#    def AutoMapperName(self):
#        return self.AutoMapper.name
#    @AutoMapperName.setter
#    def AutoMapperName(self, value):
#        self.AutoMapper = value
    @property
    def MainController(self):
        return self._MainController
    @MainController.setter
    def MainController(self, value):
        self._MainController = value
        self.MainController.Archive.add_member(name='MidiMapper', 
                                               path='CommSettings', 
                                               filename='MidiMapper.js', 
                                               serialize_obj={'MidiMapper':self})
        
    def add_ChildGroup(self, **kwargs):
        cg = super(MidiMapper, self).add_ChildGroup(**kwargs)
        cg.bind(child_update=self.on_Map_child_update)
        return cg
        
    def add_map(self, **kwargs):
        '''
        :Parameters:
            'name' : 
            'id' : 
            'type' : ('Note', 'Control')
            'channel' :
            'note' : 
            'controller' :
        '''
        cls = mapobjects.MAPS_BY_TYPE.get(kwargs.get('type'))
        kwargs.setdefault('in_devices', self.midi_io.devices['in'].values())
        kwargs.setdefault('out_devices', self.midi_io.devices['out'].values())
        obj = self.Map.add_child(cls, **kwargs)
        return obj
        
    def del_map(self, **kwargs):
        map = kwargs.get('map')
        id = kwargs.get('id')
        if not map:
            map = self.Map.get(id)
        if not map:
            return
        self.Map.del_child(map)
        
    def on_Map_child_update(self, **kwargs):
        mode = kwargs.get('mode')
        obj = kwargs.get('obj')
        d = self.map_dict
        if mode == 'remove':
            for i, attr in enumerate(obj.map_attrs):
                key = getattr(obj, attr)
                if attr not in d or key not in d[attr]:
                    return
                if i == len(obj.map_attrs) - 1:
                    del d[attr][key]
                else:
                    d = d[attr][key]
        else:
            for i, attr in enumerate(obj.map_attrs):
                key = getattr(obj, attr)
                if attr not in d:
                    d[attr] = {}
                if i == len(obj.map_attrs) - 1:
                    
                    d[attr][key] = obj
                    return
                if key not in d[attr]:
                    d[attr][key] = {}
                d = d[attr][key]
        
    def on_midi_msg_received(self, **kwargs):
        msg = kwargs.get('msg')
        if isinstance(msg, messages.NoteMessage):
            mapattrs = {'attrs':['map_type', 'channel', 'note'], 
                        'keys':['Note', msg.channel, msg.note]}
        elif isinstance(msg, messages.ControlMessage):
            mapattrs = {'attrs':['map_type', 'channel', 'controller'], 
                        'keys':['Control', msg.channel, msg.controller]}
        else:
            return
        obj = None
        d = self.map_dict
        for i, mapkey in enumerate(mapattrs['keys']):
            attr = mapattrs['attrs'][i]
            if attr not in d or mapkey not in d[attr]:
                return
            if i == len(mapattrs['keys']) - 1:
                obj = d[attr][mapkey]
                break
            else:
                d = d[attr][mapkey]
        if obj is not None:
            obj.process_message(msg)
            
    def on_in_devies_child_update(self, **kwargs):
        mode = kwargs.get('mode')
        obj = kwargs.get('obj')
        if mode == 'add':
            for mp in self.Map.itervalues():
                if mp.all_inputs:
                    mp.in_devices.add(obj)
        elif mode == 'remove':
            for mp in self.Map.itervalues():
                mp.in_devices.discard(obj)
                
    def on_out_devies_child_update(self, **kwargs):
        mode = kwargs.get('mode')
        obj = kwargs.get('obj')
        if mode == 'add':
            for mp in self.Map.itervalues():
                if mp.all_outputs:
                    mp.out_devices.add(obj)
        elif mode == 'remove':
            for mp in self.Map.itervalues():
                mp.out_devices.discard(obj)
        
    def on_midi_io_connected(self, **kwargs):
        if kwargs.get('value'):
            for mp in self.Map.itervalues():
                mp.send_message()
        
    def _get_saved_attr(self, **kwargs):
        d = super(MidiMapper, self)._get_saved_attr(**kwargs)
        #if self.AutoMapper is not None:
        for mapper in self.AutoMappers.itervalues():
            for mp in mapper.watched_maps.itervalues():
                if mp.id in d['saved_children']['Map']:
                    del d['saved_children']['Map'][mp.id]
        return d
        
    def _deserialize_child(self, d):
        cls = mapobjects.MAPS_BY_CLASS_NAME.get(d['saved_class_name'])
        if cls is None:
            return super(MidiMapper, self)._deserialize_child(d)
        #if self.AutoMapper is not None:
        for mapper in self.AutoMappers.itervalues():
            conflicts = mapper.find_map_conflicts(**d['attrs'])
            if len(conflicts):
                return False
        mkwargs = dict(in_devices=self.midi_io.devices['in'].values(), 
                       out_devices=self.midi_io.devices['out'].values(), 
                       deserialize=d)
        obj = self.Map.add_child(cls, **mkwargs)
        return obj

class AutoMapPreset(BaseObject):
    def __init__(self, **kwargs):
        super(AutoMapPreset, self).__init__(**kwargs)
        self.Mapper = kwargs.get('Mapper')
        self.MainController = self.Mapper.MainController
        #self.Mapper.Map.clear()
        self.watched_maps = {}
        if not hasattr(self, 'MapSource'):
            self.MapSource = self.get_MapSource(**kwargs)
        self.init_map(**kwargs)
        for key, val in self.MapSource.indexed_items.iteritems():
            #mp = self.Mapper.Map.indexed_items.get(key)
            mp = self.watched_maps.get(key)
            if mp is None:
                continue
            mp.Property = self._find_Property_from_obj(val)
        self.MapSource.bind(child_update=self.on_MapSource_child_update)
        
    def unlink(self):
        #self.Mapper.Map.clear()
        for mp in self.watched_maps.values()[:]:
            self.Mapper.del_map(map=mp)
        self.MapSource.unbind(self)
        super(AutoMapPreset, self).unlink()
        
    def get_MapSource(self, **kwargs):
        pass
        
    def add_map(self, **kwargs):
        mp = self.Mapper.add_map(**kwargs)
        self.watched_maps[mp._Index] = mp
        
    def find_map_conflicts(self, **kwargs):
        conflicts = set()
        for mp in self.watched_maps.itervalues():
            mp_conflict = True
            for attr in mp.map_attrs:
                if kwargs.get(attr) != getattr(mp, attr):
                    mp_conflict = False
            if mp_conflict:
                conflicts.add(mp)
        return conflicts
        
    def _find_Property_from_obj(self, obj):
        if hasattr(obj, 'value_attribute'):
            prop = obj.Properties.get(obj.value_attribute)
        else:
            prop = obj.Properties.get('value')
        return prop
        
    def on_MapSource_child_update(self, **kwargs):
        mode = kwargs.get('mode')
        obj = kwargs.get('obj')
        mp = self.watched_maps.get(obj.Index)
        if mode == 'add':
            if mp is None:
                return
            mp.Property = self._find_Property_from_obj(obj)
        elif mode == 'Index':
            old = kwargs.get('old')
            value = kwargs.get('value')
            oldmp = self.watched_maps.get(old)
            if oldmp is not None:
                oldmp.Property = None
            if mp is not None:
                mp.Property = self._find_Property_from_obj(obj)
        elif mode == 'remove':
            if mp is None:
                return
            mp.Property = None
    
class DimmerMapPreset(AutoMapPreset):
    name = 'Dimmer Map'
    description = 'Maps Device Dimmers 1:1 to Midi Controllers on channel 1'
    
    def get_MapSource(self, **kwargs):
        return self.MainController.DeviceSystem.PatchedDevices
        
    def init_map(self, **kwargs):
        self.chan_control_map = {}
        self.rev_chan_control_map = {}
        for ctl in range(1, 128):
            #self.chan_control_map[i] = (chan, ctl)
            #self.rev_chan_control_map[(chan, ctl)] = i
            mp = self.add_map(name='Dimmer %03d' % (ctl), 
                              type='Control', 
                              channel=0, 
                              controller=ctl, 
                              _Index=ctl)
        
    def _find_Property_from_obj(self, obj):
        return super(DimmerMapPreset, self)._find_Property_from_obj(obj.Groups['Dimmer'])
        

class BigDimmerMapPreset(DimmerMapPreset):
    name = 'Big Dimmer Map'
    description = 'Maps Device Dimmers 1:1 to Midi Controllers on all 16 channels'
    
    def init_map(self, **kwargs):
        self.chan_control_map = {}
        self.rev_chan_control_map = {}
        i = 1
        for chan in range(16):
            for ctl in range(1, 128):
                self.chan_control_map[i] = (chan, ctl)
                self.rev_chan_control_map[(chan, ctl)] = i
                mp = self.add_map(name='Dimmer %03d' % (i), 
                                  type='Control', 
                                  channel=chan, 
                                  controller=ctl, 
                                  _Index=i)
                i += 1
                
class DimmerNoteMapPreset(AutoMapPreset):
    name = 'Dimmer Note Map'
    description = 'Maps Device Dimmers 1:1 to Midi notes on channel 1'
    def get_MapSource(self, **kwargs):
        return self.MainController.DeviceSystem.PatchedDevices
    def init_map(self, **kwargs):
        for note in range(128):
            mp = self.add_map(name='Dimmer %03d' % (note+1), 
                              type='Note', 
                              channel=0, 
                              note=note, 
                              velocity=127, 
                              _Index=note + 1)
    def _find_Property_from_obj(self, obj):
        return super(DimmerNoteMapPreset, self)._find_Property_from_obj(obj.Groups['Dimmer'])
    
class DimmerGroupMapPreset(AutoMapPreset):
    name = 'Group Dimmer Map'
    description = 'Maps Group Dimmers 1:1 to Midi Controllers on channel 1'
    
    def get_MapSource(self, **kwargs):
        return self.MainController.Groups
        
    def init_map(self, **kwargs):
        self.chan_control_map = {}
        self.rev_chan_control_map = {}
        for ctl in range(1, 128):
            #self.chan_control_map[i] = (chan, ctl)
            #self.rev_chan_control_map[(chan, ctl)] = i
            mp = self.add_map(name='GroupDimmer %03d' % (ctl), 
                              type='Control', 
                              channel=0, 
                              controller=ctl, 
                              _Index=ctl)
        
    def _find_Property_from_obj(self, obj):
        return super(DimmerGroupMapPreset, self)._find_Property_from_obj(obj.AttributeGroups['Dimmer'])
        
class PaletteMapPreset(AutoMapPreset):
    def __init__(self, **kwargs):
        super(PaletteMapPreset, self).__init__(**kwargs)
        
    def get_MapSource(self, **kwargs):
        return self.MainController.CategoryPalettes
    def init_map(self, **kwargs):
        self.submaps = {}
        for i, pgroup in self.MapSource.indexed_items.itervalues():
            submap = PaletteGroupMap(parent=self, index=i, palette_group=pgroup)
            self.submaps[i] = submap
    
class PaletteGroupMap(AutoMapPreset):
    def init_map(self, **kwargs):
        self.parent = kwargs.get('parent')
        self.index = kwargs.get('index')
        for i, palette in self.MapSource.iteritems():
            dostuff
    def get_MapSource(self, **kwargs):
        return kwargs.get('palette_group')

AUTOMAP_PRESETS = (DimmerMapPreset, BigDimmerMapPreset, DimmerNoteMapPreset, DimmerGroupMapPreset)
