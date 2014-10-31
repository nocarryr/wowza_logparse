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
# fields.py (package: comm.dmx.artnet)
# Copyright (c) 2011 Matthew Reid

import struct

from Bases import BaseObject


class int8(int):
    struct_fmt = 'B'
#    def __init__(self, value):
#        if isinstance(value, string):
#            value = struct.unpack('=B', value)
#        int.__init__(self, value)
#    def get_struct(self):
#        return struct.pack('=B', self)
    
class int16(int):
    struct_fmt = 'H'
#    def __init__(self, value):
#        if isinstance(value, string):
#            value = struct.unpack('=H', value)
#        int.__init__(self, value)
#    def get_struct(self):
#        return struct.pack('=H', self)


class BitwiseInt(object):
    def __init__(self, **kwargs):
        #self.length = kwargs.get('length', 8)
        self.src_object = kwargs.get('src_object')
        self.src_attrs = kwargs.get('src_attrs')
    @property
    def length(self):
        if len(self.src_attrs):
            return max(self.src_attrs.keys())
        return 0
    @property
    def value(self):
        value = 0
        bit = 1
        for i in range(self.length):
            attr = self.src_attrs.get(i)
            if attr and getattr(self.src_object, attr, False):
                value += bit
            bit *= 2
        return value

class Field(BaseObject):
    _Properties = {'value':{'default':None, 'ignore_type':True}}#dict(fvalidate='_value_validate', fformat='_value_format')}
    pytype = int
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', self.__class__.__name__)
        super(Field, self).__init__(**kwargs)
        #self.Properties['value'].type = self.type
        if not hasattr(self, 'length'):
            self.length = 1
        if self.length > 1 and self.pytype == int:
            self.pytype = list
        else:
            if hasattr(self, 'bitwise_codes'):
                for code in self.bitwise_codes.itervalues():
                    setattr(self, code, kwargs.get(code, False))
                self._bitwise = BitwiseInt(src_object=self, src_attrs=self.bitwise_codes)
            self.init_field(**kwargs)
        self.bind(value=self._on_value_set)
        self.value = kwargs.get('value', getattr(self, 'default_value', None))
    
    @property
    def expected_length(self):
        if hasattr(self, 'byte_split'):
            return self.byte_split
        return self.length
        
    def _value_validate(self, value):
        return True
    def _value_format(self, value):
        return value
    def init_field(self, **kwargs):
        pass
    def add_subfield(self, subfield_index, **kwargs):
        new_kwargs = kwargs.copy()
        new_kwargs['subfield_index'] = subfield_index
        field = self._subfield_cls(**new_kwargs)
        self.subfields[subfield_index] = field
    def _on_value_set(self, **kwargs):
        pass
        #print self, self.value
    def set_data(self, value):
        if hasattr(self, 'byte_split'):
            byteval = 1
            unsplit = 0
            val_rev = value
            val_rev.reverse()
            for v in val_rev:
                unsplit += v * byteval
                byteval = byteval << 8
            self.value = self.pytype(unsplit)
        else:
            if self.pytype == str:
                self.value = ''.join([chr(i) for i in value])
            elif self.pytype == int:
                self.value = value[0]
            else:
                self.value = self.pytype(value)
    def get_data(self):
        value = self.value
        if value is None:
            value = [self.type(0)] * self.length
            
        if hasattr(self, 'byte_split'):
            if type(value) in [list, tuple]:
                value = value[0]
            remaining = value
            split = []
            for i in range(self.byte_split-1, -1, -1):
                numBits = (i+1) * 8
                byteval = 1 << numBits
                current, remaining = divmod(remaining, byteval)
                shifted = current >> (numBits - 8)
                split.append(self.type(shifted))
            split.reverse()
            #print 'bytesplit=%s, value=%s, split=%s' % (self.byte_split, value, split)
            value = split
        elif isinstance(value, str):
            value = [self.type(ord(c)) for c in value]
        elif type(value) in [list, tuple]:
            value = [self.type(v) for v in value]
        else:
            value = [self.type(value)]
            
        if len(value) < self.length:
            value.extend([self.type(0)] * (self.length - len(value)))
        return value
    def build_string(self, value=None):
        if value is None:
            value = self.value
        if value is None:
            value = [self.type(0)] * self.length
        else:
            if isinstance(value, str):
                value = [self.type(ord(c)) for c in value]
            elif type(value) in [list, tuple]:
                value = [self.type(v) for v in value]
            else:
                value = [self.type(value)]
        if len(value) < self.length:
            value.extend([self.type(0)] * (self.length - len(value)))
        s = '=%s' % (self.type.struct_fmt * self.length)
        return struct.pack(s, *value)
    def copy(self):
        kwargs = dict(id=self.id, value=self.value)
        return self.__class__(**kwargs)
    def __str__(self):
        return ': '.join([self.id, str(self.value)])
    
class ID(Field):
    type = int8
    length = 8
    pytype = str
    default_value = 'Art-Net'

class OpCode(Field):
    type = int16
    
class ProtVer(Field):
    type = int8
    byte_split = 2
    
class TalkToMe(Field):
    type = int8
    bitwise_codes = {1:'enable_unsolicited', 
                     2:'enable_diagnostics', 
                     3:'diagnostics_unicast'}
#    def init_field(self, **kwargs):
#        self.enable_diagnostics = kwargs.get('enable_diagnostics', False)
#        self.diagnostics_unicast = kwargs.get('diagnostics_unicast', False)
#        self.enable_unsolicited = kwargs.get('enable_unsolicited', True)
#        d = {1:'enable_unsolicited', 2:'enable_diagnostics', 3:'diagnostics_unicast'}
#        self._bitwise = BitwiseInt(src_object=self, src_attrs=d)
    
class Priority(Field):
    type = int8
    value_map = {0x10:'low', 0x40:'med', 0x80:'high', 0xE0:'critical', 0xFF:'volatile'}
    default_value = 0x40
    
class IPAddress(Field):
    type = int8
    length = 4
    def set_data(self, value):
        self.value = '.'.join([str(i) for i in value])
    def get_data(self):
        if self.value is None:
            value = [self.type(0)] * self.length
        else:
            value = [self.type(s) for s in self.value.split('.')]
        return value
    
class Port(Field):
    type = int16
    
class VersInfo(Field):
    type = int8
    byte_split = 2
    
class SubSwitch(Field):
    type = int8
    byte_split = 2
    
class Oem(Field):
    type = int8
    byte_split = 2
    
class UbeaVersion(Field):
    type = int8
    has_multiple = True
    
class Status1(Field):
    type = int8
    bitwise_codes = {0:'ubea_present', 
                     1:'rdm_capable', 
                     2:'booted_from_rom'}
    
class EstaMan(Field):
    type = int16

class ShortName(Field):
    type = int8
    length = 18
    pytype = str
    
class LongName(Field):
    type = int8
    length = 64
    pytype = str
    
class NodeReport(Field):
    type = int8
    length = 64
    
class NumPorts(Field):
    type = int8
    byte_split = 2
    
class PortTypes(Field):
    type = int8
    length = 4
    bitwise_codes = {6:'Input', 
                     7:'Output'}
    
class GoodInput(Field):
    type = int8
    length = 4
    bitwise_codes = {2:'receive_errors', 
                     3:'input_disabled', 
                     4:'includes_text_packets', 
                     5:'includes_SIP', 
                     6:'includes_test_packets', 
                     7:'data_received'}
    
class GoodOutput(Field):
    type = int8
    length = 4
    bitwise_codes = {1:'merge_mode_ltp', 
                     2:'output_short', 
                     3:'merge_enabled', 
                     4:'includes_text_packets', 
                     5:'includes_SIP', 
                     6:'includes_test_packets', 
                     7:'data_transmitting'}

class Swin(Field):
    type = int8
    length = 4
    
class Swout(Field):
    type = int8
    length = 4
    
class SwVideo(Field):
    type = int8
    bitwise_codes = {0:'display_ethernet_data'}
    
class SwMacro(Field):
    type = int8
    bitwise_codes = dict(zip(range(8), ['Macro%s' % (i+1) for i in range(8)]))
    
class SwRemote(Field):
    type = int8
    bitwise_codes = dict(zip(range(8), ['Remote%s' % (i+1) for i in range(8)]))
    
class Spare(Field):
    type = int8
    
class Style(Field):
    type = int8
    codes = dict(zip(range(6), ['St'+key for key in ['Node', 'Server', 'Media', 'Route', 'Backup', 'Config']]))
    
class MAC(Field):
    type = int8
    #pytype = long
    byte_split = 6
    
class BindIp(Field):
    type = int8
    length = 4
    
class BindIndex(Field):
    type = int8

class Status2(Field):
    type = int8
    bitwise_codes = {0:'web_conf_supported', 
                     1:'dhcp_enabled', 
                     2:'dhcp_capable'}

class Sequence(Field):
    type = int8
    
class Physical(Field):
    type = int8
    
class Universe(Field):
    type = int16
    
class Length(Field):
    type = int8
    byte_split = 2
    default_value = 512
    
class Data(Field):
    type = int8
    #length = 512
    pytype = list
    def __init__(self, **kwargs):
        self.length = 512
        super(Data, self).__init__(**kwargs)
    def _on_value_set(self, **kwargs):
        value = kwargs.get('value')
        if isinstance(value, list):
            self.length = len(value)
        super(Data, self)._on_value_set(**kwargs)
    
class Dummy(Field):
    def __init__(self, **kwargs):
        self.type = kwargs.get('type', int8)
        self.length = kwargs.get('length', 1)
        super(Dummy, self).__init__(**kwargs)
    
class Frames(Field):
    type = int8
    
class Seconds(Field):
    type = int8
    
class Minutes(Field):
    type = int8
    
class Hours(Field):
    type = int8
    
class FrameRate(Field):
    type = int8
    codes = {0:24, 1:25, 2:29.97, 3:30}
    
if __name__ == '__main__':
    test = GoodInput()
    bob
