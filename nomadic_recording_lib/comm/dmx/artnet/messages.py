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
# messages.py (package: comm.dmx.artnet)
# Copyright (c) 2011 Matthew Reid

import struct
if __name__ == '__main__':
    import sys
    sys.path.append('/home/nocarrier/programs/openlightingdesigner/openlightingdesigner/')
    
from Bases import BaseObject, ChildGroup
import fields as FieldClasses

PROTOCOL_VERSION = 14

FIELD_DEFAULTS = {'ID': 'Art-Net', 'ProtVer':PROTOCOL_VERSION}

LOG = BaseObject().LOG

class ArtBaseMsg(object):
    _fields = {1:'ID', 2:'OpCode'}
    def __init__(self, **kwargs):
        self.msg_type = kwargs.get('msg_type', self.__class__.__name__)
        cls = self.__class__
        fields = {}
        while cls != ArtBaseMsg:
            fields.update(getattr(cls, '_fields', {}))
            cls = cls.__bases__[0]
        fields.update(ArtBaseMsg._fields)
        self.Fields = ChildGroup(name='Fields')
        for index, key in fields.iteritems():
            fcls = getattr(FieldClasses, key, None)
            if fcls is not None:
                fobj = self.Fields.add_child(fcls, Index=index)
        for i in range(1, self._num_fields + 1):
            current = self.Fields.indexed_items.get(i)
            if current is not None:
                field = current
            else:
                if i <= field.Index + field.expected_length - 1:
                    pass
                else:
                    fobj = self.Fields.add_child(FieldClasses.Dummy, id='Dummy_%s' % (i), Index=i)
                    #print 'added dummyobj: i=%s, current=%s, field=%s' % (i, current, field)
                    
        self.init_msg(**kwargs)
        
        datastr = kwargs.get('from_string')
        if datastr:
            self._parse_success = True
            result = self.from_string(datastr)
            if result is False:
                self._parse_success = False
        else:
            for key, field in self.Fields.iteritems():
                value = getattr(self, key, kwargs.get(key, FIELD_DEFAULTS.get(key)))
                if value is not None:
                    field.value = value
    def init_msg(self, **kwargs):
        pass
    def from_string(self, string):
        if string is None:
            return False
        l, fmt = self.get_data()
        while len(string) < struct.calcsize(fmt):
            before = fmt
            fmt = fmt[:-1]
            #print 'fmt trunc: before=%s, after=%s' % (before, fmt)
        if len(string) > struct.calcsize(fmt):
            string = string[:struct.calcsize(fmt)]
        try:
            values = list(struct.unpack(fmt, string))
        except:
            LOG.warning(self, 'could not unpack', struct.calcsize(fmt), len(string))
            return False
        #print 'from_string: ', values
        for field in self.Fields.indexed_items.itervalues():
            length = field.expected_length
            if length > len(values):
                #print 'not enough data for field: ', field.id
                break
            field.set_data(values[:length])
            #print field.__class__.__name__, values[:length], values
            del values[:length]
        
    def get_data(self):
        l = []
        #print 'getdata: ', self.msg_type
        for field in self.Fields.indexed_items.itervalues():
            data = field.get_data()
            #print field.id, data
            l.extend(data)
            
        fmt = '=%s' % (''.join([type(item).struct_fmt for item in l]))
        return l, fmt
        
    def build_string(self):
        l, fmt = self.get_data()
        return struct.pack(fmt, *l)
        
    def copy(self):
        msg = self.__class__()
        for i, field in self.Fields.indexed_items.iteritems():
            msg.Fields.indexed_items[i].value = field.value
        return msg
        
    def __str__(self):
        keys = sorted(self.Fields.indexed_items.keys())
        fields = ', '.join([str(self.Fields.indexed_items[key]) for key in keys])
        return ': '.join([self.msg_type, fields])
        
class ArtPoll(ArtBaseMsg):
    _fields = {3:'ProtVer', 5:'TalkToMe', 6:'Priority'}
    _num_fields = 6
    OpCode = 0x2000
    Priority = 0x10
    #def __init__(self, **kwargs):
    #    super(ArtPoll, self).__init__(**kwargs)
    
class ArtPollReply(ArtBaseMsg):
    _fields = {3:'IPAddress', 4:'Port', 5:'VersInfo', 7:'SubSwitch', 9:'Oem', 
               11:'UbeaVersion', 12:'Status1', 13:'EstaMan', 14:'ShortName', 
               15:'LongName', 16:'NodeReport', 17:'NumPorts', 19:'PortTypes', 
               20:'GoodInput', 21:'GoodOutput', 22:'Swin', 23:'Swout', 
               24:'SwVideo', 25:'SwMacro', 26:'SwRemote', 30:'Style', 31:'MAC', 
               37:'BindIp', 38:'BindIndex', 39:'Status2'}
    _num_fields = 39
    OpCode = 0x2100
    
class ArtDmx(ArtBaseMsg):
    _fields = {3:'ProtVer', 5:'Sequence', 6:'Physical', 7:'Universe', 
               8:'Length', 10:'Data'}
    _num_fields = 10
    OpCode = 0x5000
    def init_msg(self, **kwargs):
        #self._on_length_field_set()
        #self.Fields['Length'].bind(value=self._on_length_field_set)
        if 'Data' in kwargs:
            self.Fields['Length'].value = len(kwargs.get('Data'))
    def _on_length_field_set(self, **kwargs):
        return
        i = self.Fields['Length'].value
        if i is not None:
            #print 'setting dmx length: ', i
            self.Fields['Data'].length = i
    def blahfrom_string(self, string):
        if string is None:
            return
        l, fmt = self.get_data()
        values = struct.unpack(fmt[:-1], string[:18])
        self.Fields['Length'].value = values[16]
        super(ArtDmx, self).from_string(string)
    
class ArtTimeCode(ArtBaseMsg):
    _fields = {3:'ProtVer', 7:'Frames', 8:'Seconds', 9:'Minutes', 10:'Hours', 11:'FrameRate'}
    _num_fields = 10
    OpCode = 0x9700
    
MESSAGES = (ArtPoll, ArtPollReply, ArtDmx, ArtTimeCode)
MESSAGES_BY_OPCODE = dict(zip([msg.OpCode for msg in MESSAGES], MESSAGES))

def parse_message(string):
    try:
        data = struct.unpack('=BBBBBBBBH', string[:10])
    except:
        LOG.warning('could not determine opcode')
    #print 'data: ', data
    opcode = data[8]
    
    cls = MESSAGES_BY_OPCODE.get(opcode)
    if cls is not None:
        obj = cls(from_string=string)
        if obj._parse_success:
            return obj
    LOG.warning('could not parse msg: opcode=%s' % (opcode))
    return False

if __name__ == '__main__':
    poll = ArtPoll()
    #reply = ArtPollReply(IPAddress='192.168.1.51', LongName='blahblahstuff', ShortName='blahstuff', 
    #                     NumPorts=4, PortTypes=[0xC0]*4)
    s = poll.build_string()
    poll2 = parse_message(s)
    #poll2.from_string(s)
    dmx = ArtDmx(Data=[1, 2, 3, 4, 5, 6, 7])
    dmx2 = parse_message(dmx.build_string())
    
    bob
