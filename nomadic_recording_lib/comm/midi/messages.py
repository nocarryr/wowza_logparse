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
# messages.py
# Copyright (c) 2011 Matthew Reid

import array

class MidiMessage(object):
    _byte_order = ['status']
    def __init__(self, **kwargs):
        cls = self.__class__
        byte_order = []
        while cls != MidiMessage:
            if '_byte_order' in cls.__dict__:
                l = cls._byte_order[:]
                l.reverse()
                byte_order.extend(l)
            cls = cls.__bases__[0]
        l = MidiMessage._byte_order[:]
        l.reverse()
        byte_order.extend(l)
        byte_order.reverse()
        self.byte_order = byte_order
        self.data = kwargs.get('data')
        self.timestamp = kwargs.get('timestamp')
        if self.data is not None:
            result = self.parse(**kwargs)
            self.parse_fail = result is False
        else:
            self.init_message(**kwargs)
    @staticmethod
    def from_binary(cls, **kwargs):
        return cls(**kwargs)
    def init_message(self, **kwargs):
        self.status = self._valid_status_byte
    def parse(self, **kwargs):
        self.status = self.data[0]
    def build_data(self):
        return [int(getattr(self, key)) for key in self.byte_order]
    def build_string(self):
        a = array.array('B', self.build_data())
        return a.tostring()
    def __str__(self):
        name = self.__class__.__name__
        if 'Message' in name:
            name = ''.join(name.split('Message'))
        values = ', '.join(['%s=%s' % (key, getattr(self, key)) for key in self.byte_order[1:]])
        data = ','.join([hex(v) for v in self.build_data()]).join(['(', ')'])
        return ' '.join([name, values, data])
        
class ChannelMessage(MidiMessage):
    def init_message(self, **kwargs):
        super(ChannelMessage, self).init_message(**kwargs)
        self.channel = kwargs.get('channel', 0)
        self.status += self.channel
    def parse(self, **kwargs):
        super(ChannelMessage, self).parse(**kwargs)
        self.channel = self.data[0] - self._valid_status_byte
        
class NoteMessage(ChannelMessage):
    _byte_order = ['note', 'velocity']
    def init_message(self, **kwargs):
        super(NoteMessage, self).init_message(**kwargs)
        self.note = kwargs.get('note', 0)
        self.velocity = kwargs.get('velocity', 100)
    def parse(self, **kwargs):
        super(NoteMessage, self).parse(**kwargs)
        self.note = self.data[1]
        self.velocity = self.data[2]
        
class NoteOffMessage(NoteMessage):
    _valid_status_byte = 0x80
    
class NoteOnMessage(NoteMessage):
    _valid_status_byte = 0x90
    @staticmethod
    def from_binary(cls, **kwargs):
        msg = cls(**kwargs)
        if msg.velocity == 0:
            msg = NoteOffMessage(**kwargs)
        return msg
    
class AftertouchMessage(ChannelMessage):
    _valid_status_byte = 0xA0
    _byte_order = ['note', 'value']
    def init_message(self, **kwargs):
        super(AftertouchMessage, self).init_message(**kwargs)
        self.note = kwargs.get('note', 0)
        self.value = kwargs.get('value', 0)
    def parse(self, **kwargs):
        super(AftertouchMessage, self).parse(**kwargs)
        self.note = self.data[1]
        self.value = self.data[2]
    
class ControlMessage(ChannelMessage):
    _valid_status_byte = 0xB0
    _byte_order = ['controller', 'value']
    def init_message(self, **kwargs):
        super(ControlMessage, self).init_message(**kwargs)
        self.controller = kwargs.get('controller', 0)
        self.value = kwargs.get('value', 0)
    def parse(self, **kwargs):
        super(ControlMessage, self).parse(**kwargs)
        self.controller = self.data[1]
        self.value = self.data[2]
    
class SystemMessage(MidiMessage):
    _valid_status_byte = 0xF0
    
class SysexMessage(SystemMessage):
    def init_message(self, **kwargs):
        super(SysexMessage, self).init_message(**kwargs)
        self.sysex = kwargs.get('sysex', [])
    def parse(self, **kwargs):
        super(SysexMessage, self).parse(**kwargs)
        self.sysex = []
        if 0xF7 not in self.data:
            return False
        sxstart = self.data.index(0xF0)
        sxend = self.data.index(0xF7)
        self.sysex = self.data[sxstart+1:sxend]
    def build_data(self):
        return [0xF0] + self.sysex + [0xF7]
    
class MidiTimeCodeMessage(SystemMessage):
    _frame_rate_types = [24, 25, 29.97, 30]
    _tc_keys = ['hour', 'minute', 'second', 'frame']
    def __init__(self, **kwargs):
        self.tcdata = {}
        self.frame_rate = None
        super(MidiTimeCodeMessage, self).__init__(**kwargs)
        
    def init_message(self, **kwargs):
        super(MidiTimeCodeMessage, self).init_message(**kwargs)
        self.frame_rate = kwargs.get('frame_rate', 29.97)
        tcdata = kwargs.get('tcdata')
        if tcdata is not None:
            self.tcdata.update(tcdata)
        else:
            for key in self._tc_keys:
                if key in kwargs:
                    self.tcdata[key] = kwargs[key]
        
class MTCFullMessage(MidiTimeCodeMessage):
    def init_message(self, **kwargs):
        super(MTCFullMessage, self).init_message(**kwargs)
        h = self.tcdata['hour']
        fr = self._frame_rate_types.index(self.frame_rate)
        fr = fr << 5
        h += fr
        tcdata = self.tcdata.copy()
        tcdata['hour'] = h
        self.sysex = [0x7F, 0x7F, 0x01, 0x01]
        for key in self._tc_keys:
            self.sysex.append(tcdata[key])
    def parse(self, **kwargs):
        super(MTCFullMessage, self).parse(**kwargs)
        sxstart = self.data.index(0xF0)
        sxend = self.data.index(0xF7)
        self.sysex = self.data[sxstart+1:sxend]
        if self.sysex[:4] != [0x7F, 0x7F, 0x01, 0x01]:
            return False
        tclist = self.sysex[4:8]
        tcdata = dict(zip(self._tc_keys, tclist))
        h = tcdata['hour']
        fr = h >> 5
        h -= fr << 5
        tcdata['hour'] = h
        self.frame_rate = self._frame_rate_types[fr]
        self.tcdata.update(tcdata)
    def build_data(self):
        return [0xF0] + self.sysex + [0xF7]
    
class MTCQuarterMessage(MidiTimeCodeMessage):
    _valid_status_byte = 0xF1
    _Piece_keys = ['frameLSB', 'frameMSB', 'secondLSB', 'secondMSB', 
                   'minuteLSB', 'minuteMSB', 'hourLSB', 'rate/hourMSB']
    _byte_order = ['value']
    def init_message(self, **kwargs):
        super(MTCQuarterMessage, self).init_message(**kwargs)
        self.MTCPiece = kwargs.get('MTCPiece')
        #self.value = kwargs.get('value')
        key = self._Piece_keys[self.MTCPiece]
        if 'MSB' in key:
            key = key.split('MSB')[0]
            msb = True
        else:
            key = key.split('LSB')[0]
            msb = False
        if '/' in key:
            key = key.split('/')[1]
            value = self.tcdata.get(key) >> 4
            fr = self._frame_rate_types.index(self.frame_rate)
            fr = fr << 1
            value += fr
        else:
            value = self.tcdata.get(key)
            if msb:
                value = value >> 4
            else:
                value = value % 0x10
        value += self.MTCPiece << 4
        self.value = value
    def parse(self, **kwargs):
        super(MTCQuarterMessage, self).parse(**kwargs)
        self.value = self.data[1]
        self.MTCPiece = self.data[1] >> 4
        key = self._Piece_keys[self.MTCPiece]
        #self.value = self.data[1] - (self.MTCPiece << 4)
        value = self.value - (self.MTCPiece << 4)
        if 'MSB' in key:
            key = key.split('MSB')[0]
            msb = True
        else:
            key = key.split('LSB')[0]
            msb = False
        if '/' in key:
            fr = value >> 1
            value -= fr << 1
            self.frame_rate = self._frame_rate_types[fr]
            key = key.split('/')[1]
        if msb:
            value = value << 4
        self.tcdata[key] = value
    
class SongPositionMessage(SystemMessage):
    _valid_status_byte = 0xF2
    _byte_order = ['beatsLSB', 'beatsMSB']
    def init_message(self, **kwargs):
        super(SongPositionMessage, self).init_message(**kwargs)
        self.beats = kwargs.get('beats')
        self.beatsMSB = self.beats >> 7
        self.beatsLSB = self.beats - (self.beatsMSB << 7)
    def parse(self, **kwargs):
        super(SongPositionMessage, self).parse(**kwargs)
        self.beatsLSB = self.data[1]
        self.beatsMSB = self.data[2]
        self.beats = self.beatsLSB + (self.beatsMSB << 7)
    
class ClockMessage(SystemMessage):
    _valid_status_byte = 0xF8
    
class StartMessage(SystemMessage):
    _valid_status_byte = 0xFA
    
class ContinueMessage(SystemMessage):
    _valid_status_byte = 0xFB
    
class StopMessage(SystemMessage):
    _valid_status_byte = 0xFC

_msgs = (NoteOffMessage, NoteOnMessage, AftertouchMessage, ControlMessage, 
         SysexMessage, MTCQuarterMessage, SongPositionMessage, ClockMessage, 
         StartMessage, ContinueMessage, StopMessage)
MIDI_MESSAGES = dict(zip([cls._valid_status_byte for cls in _msgs], _msgs))
_status_byte_order = sorted(MIDI_MESSAGES.keys())
_status_byte_order.reverse()

SYSEX_MESSAGES = (MTCFullMessage, )

def parse_midi_message(data, timestamp=None):
    for key in _status_byte_order:
        if data[0] & key == key:
            cls = MIDI_MESSAGES[key]
            if cls == SysexMessage:
                for sxcls in SYSEX_MESSAGES:
                    msg = sxcls(data=data, timestamp=timestamp)
                    if msg.parse_fail:
                        continue
                    return msg
            return cls.from_binary(cls, data=data, timestamp=timestamp)
            
#if __name__ == '__main__':
#    cm = ControlMessage(channel=1, controller=7, value=63)
#    l = cm.build_data()
#    print 'controller msg:    ', l, cm.byte_order
#    parsed = parse_midi_message(l)
#    print 'controller parsed: ', parsed.build_data()
#    nm = NoteOnMessage(channel=1, note=20, velocity=100)
#    l = nm.build_data()
#    print 'note on msg:    ', l, nm.byte_order
#    parsed = parse_midi_message(l)
#    print 'note on parsed: ', parsed.build_data()
#    
#    tcdata = dict(hour=20, minute=31, second=59, frame=18)
#    
#    qmsgs = []
#    qparsed = []
#    for i in range(8):
#        qm = MTCQuarterMessage(MTCPiece=i, tcdata=tcdata)
#        qmsgs.append(qm)
#        qparsed.append(parse_midi_message(qm.build_data()))
#    newtcdata = {}
#    for parsed in qparsed:
#        for key, val in parsed.tcdata.iteritems():
#            v = newtcdata.get(key, 0)
#            v += val
#            newtcdata[key] = v
#    print newtcdata
#    
#    tcfull = MTCFullMessage(tcdata=tcdata)
#    print 'tcfull:   ', tcfull.build_data()
#    parsed = parse_midi_message(tcfull.build_data())
#    print 'tcparsed: ', parsed.build_data(), parsed.tcdata
#    
#    p = SongPositionMessage(beats=400)
#    print 'pos:        ', p.build_data()
#    parsed = parse_midi_message(p.build_data())
#    print 'pos parsed: ', parsed.build_data()
#    
#    cl = ClockMessage()
#    print 'clock:        ', cl.build_data()
#    parsed = parse_midi_message(cl.build_data())
#    print 'clock parsed :', parsed.build_data()
#    
##    qm1 = MTCQuarterMessage(MTCPiece=6, tcdata=tcdata)
##    print 'mtcq1 msg:    ', qm1.build_data()
##    parsed1 = parse_midi_message(qm1.build_data())
##    print 'mtcq1 parsed: ', parsed1.build_data()
##    qm2 = MTCQuarterMessage(MTCPiece=7, tcdata=tcdata)
##    print 'mtcq2 msg:    ', qm2.build_data()
##    parsed2 = parse_midi_message(qm2.build_data())
##    print 'mtcq2 parsed: ', parsed2.build_data()
##    print 'q1 tc=%s, q2 tc=%s' % (parsed1.tcdata, parsed2.tcdata)
