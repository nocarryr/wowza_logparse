import time
import array
import collections
import struct

from BaseObject import BaseObject
import incrementor

def biphase_encode(data, num_samples, max_value):
    samples_per_period = num_samples / len(data) / 2
    #print 'num_samp=%s, maxv=%s, s_per_period=%s' % (num_samples, max_value, samples_per_period)
    min_value = max_value * -1
    values = {True:max_value, False:min_value}
    #a = array.array('h')
    l = biphase_clock_before_data(data)
    a = []
    for v in l:
        a.extend([values[v]] * samples_per_period)
    while len(a) < num_samples:
        a.append(a[-1:][0])
    return a

def biphase_clock_before_data(data, transition_value=True):
    encoded = []
    for i, value in enumerate(data):
        if i == 0:
            last = True
        clock = not last
        if value:
            value = not clock
        else:
            value = clock
        encoded.extend([clock, value])
        last = value
    return encoded

class LTCGenerator(BaseObject):
    def __init__(self, **kwargs):
        self.framerate = kwargs.get('framerate', 29.97)
        best_sr = kwargs.get('use_best_samplerate', False)
        if best_sr:
            fr = self.framerate
            #r, frac = divmod(fr, int(fr))
            r = int(fr)
            frac = fr % r
            sr = (r * 100) + int(round(frac * 100))
            while (sr / fr) / 80 < 16:
                sr *= 2
            self.samplerate = sr
            self.samples_per_frame = int(round(sr / fr))
            
            print 'samplerate=%s, s_per_frame=%s' % (self.samplerate, self.samples_per_frame)
        else:
            sr = kwargs.get('samplerate', 48000)
            fr = self.framerate
            self.samplerate = sr
            #spf, r = divmod(self.samplerate, float(self.framerate))
            spf = sr / float(fr)
            self.samples_per_frame = int(spf)
            if self.samples_per_frame % 2 != 0:
                self.samples_per_frame -= 1
            self.real_samples_per_frame = spf
            r = sr - (self.samples_per_frame * float(fr))
            print r
            self.extra_samples_per_second = r
            self.sample_pad_positions = [(sr / r) * v for v in range(int(round(r)))]
            print self.sample_pad_positions
            self.sample_pad_last_index = None
        self.bitdepth = kwargs.get('bitdepth', 16)
        self.max_sampleval = 1 << (self.bitdepth - 2)
        self.current_sample_position = 0
        if type(self.framerate) == float:
            cls = DropFrame
        else:
            cls = NonDropFrame
        self.is_dropframe = cls == DropFrame
        self.frame_obj = cls(framerate=self.framerate)
        self.datablock = LTCDataBlock(framerate=self.framerate, frame_obj=self.frame_obj)

    def build_datablock(self, **kwargs):
        return self.datablock.build_data()

    def build_audio_data(self, **kwargs):
        data = self.build_datablock()
        spf = self.samples_per_frame
        sr = self.samplerate
        if self.current_sample_position > sr:
            self.current_sample_position = 0
            self.sample_pad_last_index = None
        s_pos = self.current_sample_position
        if self.is_dropframe:
            real_spf = self.real_samples_per_frame
            pad_positions = self.sample_pad_positions
            if self.sample_pad_last_index is None:
                if pad_positions[0] >= s_pos:
                    spf += 1
                    self.sample_pad_last_index = 0
                    #print 'padding from none: ', 0
            else:
                i = self.sample_pad_last_index
                if len(pad_positions) > i+1 and pad_positions[i+1] >= s_pos:
                    spf += 1
                    self.sample_pad_last_index += 1
                    #print 'padding: ', self.sample_pad_last_index
        self.current_sample_position += spf
        #print self.current_sample_position
        a = biphase_encode(data, spf, self.max_sampleval)
        return a

class DropFrame(incrementor.Incrementor):
    def __init__(self, **kwargs):
        fr = kwargs.get('framerate', 29.97)
        res = int(round(fr))
        self.drop_period = int((res - fr) * 100)
        self.drop_count = 0
        self.framerate = fr
        self._enable_drop = False
        kwargs['resolution'] = res
        kwargs['name'] = 'frame'
        super(DropFrame, self).__init__(**kwargs)
        self.add_child('second', DropFrameSecond)

    @property
    def enable_drop(self):
        return self._enable_drop
    @enable_drop.setter
    def enable_drop(self, value):
        if value == self.enable_drop:
            return
        self._enable_drop = value
        #print 'enable_drop: ', value
        
    @property
    def current_resolution(self):
        r = self.resolution
        if self.enable_drop:
            return r - 2
        return r

    def _on_value_set(self, **kwargs):
        if not self.enable_drop:
            return
        value = kwargs.get('value')
        if value in [0, 1]:
            self.value = 2
        self.enable_drop = False

class DropFrameSecond(incrementor.Second):
    def __init__(self, **kwargs):
        super(DropFrameSecond, self).__init__(**kwargs)
        self.children['minute'].bind(value=self._on_minute_value_set)
    def check_for_drop(self):
        if self.value > 0:
            return
        if self.children['minute'].value % 10 != 0:
            self.parent.enable_drop = True
        else:
            self.parent.enable_drop = False
    def _on_value_set(self, **kwargs):
        self.check_for_drop()
    def _on_minute_value_set(self, **kwargs):
        self.check_for_drop()

class NonDropFrame(incrementor.Incrementor):
    def __init__(self, **kwargs):
        fr = kwargs.get('framerate', 30)
        kwargs['resolution'] = fr
        kwargs['name'] = 'frame'
        super(NonDropFrame, self).__init__(**kwargs)
        self.add_child('second', incrementor.Second)


class LTCDataBlock(object):
    def __init__(self, **kwargs):
        self.framerate = kwargs.get('framerate')
        self.frame_obj = kwargs.get('frame_obj')
        self.all_frame_obj = self.frame_obj.get_all_obj()
        self.fields = {}
        self.fields_by_name = {}
        for key, cls in FIELD_CLASSES.iteritems():
            if type(key) == int:
                field = cls(parent=self)
                self.fields[key] = field
                self.fields_by_name[field.name] = field
            elif type(key) in [list, tuple]:
                for i, startbit in enumerate(key):
                    name = cls.__name__ + str(i)
                    field = cls(parent=self, start_bit=startbit, name=name)
                    self.fields[startbit] = field
                    self.fields_by_name[field.name] = field
        #keys = self.fields.keys()
        #fields = [self.fields[key] for key in keys]
        #data = self.build_data()
        #print zip(keys, [(f.bit_length, f.name, f.get_value()) for i, f in enumerate(fields)])

    @property
    def tc_data(self):
        fobj = self.all_frame_obj
        keys = fobj.keys()[:]
        return dict(zip(keys, [fobj[key].value for key in keys]))

    def build_data(self):
        i = 0
        l = []
        for bit, field in self.fields.iteritems():
            value = field.get_value()
            i += value << field.start_bit
            l.extend(field.get_list_value())
        s = bin(i)[2:]
        if s.count('0') % 2 == 1:
            i += 1 << self.fields_by_name['ParityBit'].start_bit
            l[self.fields_by_name['ParityBit'].start_bit] = True
        return l

class Field(object):
    def __init__(self, **kwargs):
        self.parent = kwargs.get('parent')
        self.name = kwargs.get('name', self.__class__.__name__)
        if hasattr(self, '_start_bit'):
            self.start_bit = self._start_bit
        else:
            self.start_bit = kwargs.get('start_bit')
        if hasattr(self, '_bit_length'):
            self.bit_length = self._bit_length
        else:
            self.bit_length = 1
    def get_shifted_value(self):
        value = self.get_value()
        return value << self.start_bit
    def get_value(self):
        value = self.value_source()
        value = self.calc_value(value)
        return value
    def get_list_value(self):
        value = self.get_value()
        l = [bool(int(c)) for c in bin(value)[2:]]
        l.reverse()
        while len(l) < self.bit_length:
            l.append(False)
        return l

    def value_source(self):
        return 0
    def calc_value(self, value):
        return value

class FrameUnits(Field):
    _start_bit = 0
    _bit_length = 4
    def value_source(self):
        return self.parent.tc_data['frame']
    def calc_value(self, value):
        return value % 10

class FrameTens(Field):
    _start_bit = 8
    _bit_length = 2
    def value_source(self):
        return self.parent.tc_data['frame']
    def calc_value(self, value):
        return value / 10

class DropFlag(Field):
    _start_bit = 10
    def value_source(self):
        if type(self.parent.framerate) == float:
            return 1
        return 0

class ColorFlag(Field):
    _start_bit = 11

class SecondUnits(Field):
    _start_bit = 16
    _bit_length = 4
    def value_source(self):
        return self.parent.tc_data['second']
    def calc_value(self, value):
        return value % 10

class SecondTens(Field):
    _start_bit = 24
    _bit_length = 3
    def value_source(self):
        return self.parent.tc_data['second']
    def calc_value(self, value):
        return value / 10

class ParityBit(Field):
    _start_bit = 27

class MinuteUnits(Field):
    _start_bit = 32
    _bit_length = 4
    def value_source(self):
        return self.parent.tc_data['minute']
    def calc_value(self, value):
        return value % 10

class MinuteTens(Field):
    _start_bit = 40
    _bit_length = 3
    def value_source(self):
        return self.parent.tc_data['minute']
    def calc_value(self, value):
        return value / 10

class BinaryGroupFlag(Field):
    _start_bits = (43, 59)

class HourUnits(Field):
    _start_bit = 48
    _bit_length = 4
    def value_source(self):
        return self.parent.tc_data['hour']
    def calc_value(self, value):
        return value % 10

class HourTens(Field):
    _start_bit = 56
    _bit_length = 2
    def value_source(self):
        return self.parent.tc_data['hour']
    def calc_value(self, value):
        return value / 10

class Reserved(Field):
    _start_bit = 58

class SyncWord(Field):
    _start_bit = 64
    _bit_length = 16
    def value_source(self):
        return 0x3FFD

class UBits(Field):
    _bit_length = 4
    _start_bits = (4, 12, 20, 28, 36, 44, 52, 60)

def _GET_FIELD_CLASSES():
    d = {}
    for key, val in globals().iteritems():
        if type(val) != type:
            continue
        if issubclass(val, Field) and val != Field:
            if hasattr(val, '_start_bit'):
                dkey = val._start_bit
            elif hasattr(val, '_start_bits'):
                dkey = val._start_bits
            else:
                dkey = key
            d[dkey] = val
    return d

FIELD_CLASSES = _GET_FIELD_CLASSES()

if False:#__name__ == '__main__':
    tcgen = LTCGenerator(use_best_samplerate=False)
    d = {'frame':10, 'second':5, 'minute':20, 'hour':2}
    tcgen.frame_obj.set_values(**d)
    print tcgen.frame_obj.get_values()
    #data = tcgen.build_datablock()
    #print len(data), data
    #print tcgen.build_audio_data()
    chunks = []
    for i in range(30):
        tcgen.frame_obj += 1
        chunks.append(tcgen.build_audio_data())
    l = [len(chunk) for chunk in chunks]
    total = 0
    for chunk in chunks:
        total += len(chunk)
    print l
    print total
    
if __name__ == '__main__':
    import time
    import threading
    import datetime
    import gobject, glib
    import gst

    class A(object):
        def __init__(self):
            self.tcgen = LTCGenerator(use_best_samplerate=False)
            now = datetime.datetime.now()
            self.buffer_lock = threading.Lock()
            self.start = now
            d = {}
            for key in ['hour', 'minute', 'second']:
                d[key] = getattr(now, key)
            ms = float(now.microsecond) / (10 ** 6)
            if d['second'] == 0 and d['minute'] % 10 != 0:
                frame = int(round(ms / (1/28.)))
                frame += 2
            else:
                frame = int(round(ms / (1/30.)))
            if frame > 29:
                frame = 29
            d['frame'] = frame
            self.tcgen.frame_obj.set_values(**d)
            print 'start: ', self.tcgen.frame_obj.get_values(), now.strftime('%X.%f')
            self.last_timestamp = time.time()
            self.buffer = collections.deque()
            self.buffer.extend(self.tcgen.build_audio_data())
            self.frametimes = []
            self.buffersizes = []
            self.timestamp = None
            #self.increment_and_build_data(150)
            #self.buffer.extend(self.tcgen.build_audio_data())
            #print len(self.buffer)
        def increment_and_build_data(self, count=1):
            tcgen = self.tcgen
            fr_obj = tcgen.frame_obj
            audbuffer = self.buffer
            buffer_lock = self.buffer_lock
            for i in range(count):
                fr_obj += 1
                abuf = tcgen.build_audio_data()
                #with buffer_lock:
                audbuffer.extend(abuf)
        def on_vident_handoff(self, ident, buffer):
            #now = time.time()
            #self.frametimes.append(now)
            #self.buffersizes.append(buffer.size)
            #print now - self.last_timestamp
            #self.last_timestamp = now
            #self.increment_and_build_data()
            self.tcgen.frame_obj += 1
            #print self.tcgen.frame_obj.get_values()
            #self.timestamp = buffer.timestamp
            #print 'vident ts: ', self.timestamp
            #spf = self.tcgen.samples_per_frame
            #print 'spf: ', spf
            #self.asrc.emit('need-data', spf * 2)
#            d = self.tcgen.frame_obj.get_values()
#            timestr = ':'.join(['%02i' % (d[key]) for key in ['hour', 'minute', 'second', 'frame']])
#            print timestr, '%s.%02i' % (time.strftime('%H:%M:%S', time.localtime(now)), round((now - int(now)) * 1000 / 29.97))
#            self.toverlay.set_property('text', timestr)
            return (ident, buffer)
        def on_aident_handoff(self, ident, buffer):
            self.asrc.emit('need-data', buffer.size)
            return (ident, buffer)
        def on_audneeddata(self, element, length):
            #if self.timestamp is None:
            #    return
            #ts = element.get_clock().get_time() - element.get_base_time()
            #audbuffer = self.buffer
#            print [e.get_caps().to_string() for e in element.src_pads()]
            #print element.get_property('caps')
            #print 'length needed: ', length
            #print 'abuffer len: ', len(audbuffer)
            #if len(audbuffer) < length / 4:
            #    return
            #with self.buffer_lock:
            tcbuf = array.array('h', self.tcgen.build_audio_data())
            #tcbuf = self.get_samples_from_buffer(length / 2)
            if False:#tcbuf is False:
                print 'BUFFER EMPTY!!!'
                #element.emit('end-of-stream')
                #return
                tcbuf = array.array('h', [0]*(length/2))
            tcstr = tcbuf.tostring()
            buffer = gst.Buffer(tcstr)
            #tcgen = self.tcgen
            #buffer.duration = long((tcgen.samplerate / float(length / 2)) * (10 ** 9))
            #buffer.timestamp = gst.CLOCK_TIME_NONE
            #buffer.set_caps(self.asrccaps.copy())
            #buffer.timestamp = self.timestamp
            #self.timestamp = None
            #print 'appsrc ts: ', buffer.timestamp
            #buffer.timestamp = element.get_clock().get_time()
            #print 'buffer: ', len(tcstr)
            #print 'new abuffer len: ', len(audbuffer)
            result = element.emit('push-buffer', buffer)
            #print 'push-buffer result: ', result
        def get_samples_from_buffer(self, num_samples):
            buffer = self.buffer
            if len(buffer) < num_samples:
                return False
            out = array.array('h')
            for i in range(num_samples):
                out.append(buffer.popleft())
            return out
        def on_atestsrc_push(self, element, buffer):
            print 'atestsrcbuffer:\n', buffer
        def on_bus_message(self, bus, msg):
            print msg
    a = A()
    p = gst.Pipeline()
    bus = p.get_bus()
    bus.add_signal_watch()
    bus.connect('message', a.on_bus_message)
    vqueue = gst.element_factory_make('queue')
    vsrc = gst.element_factory_make('videotestsrc')
    vsrc.set_property('is-live', True)
    vsrc.set_property('pattern', 2)
    vident = gst.element_factory_make('identity')
    toverlay = gst.element_factory_make('cairotextoverlay')
    a.toverlay = toverlay
    vcapf = gst.element_factory_make('capsfilter')
    vcaps = gst.Caps('video/x-raw-yuv, framerate=30000/1001')
    vcapf.set_property('caps', vcaps)
    vrate = gst.element_factory_make('videorate')
    #vout = gst.element_factory_make('xvimagesink')
    vout = gst.element_factory_make('fakesink')
    
    aqueue = gst.element_factory_make('queue')
    aqueue2 = gst.element_factory_make('queue')
    testasrc = gst.element_factory_make('audiotestsrc')
    #asrc = testasrc
    #asrc.set_property('wave', 1)
    testasrc.set_property('samplesperbuffer', 1600)
    #asrc.set_property('volume', 1.)
    
    asrc = gst.element_factory_make('appsrc')
    a.asrc = asrc
    #asrc.set_do_timestamp(True)
    #asrc.set_property('size', 800)

    asrc.set_property('is-live', True)
    #asrc.set_property('size', 3200)
    asrc.set_property('max-bytes', 3200)
    asrc.set_property('min-percent', 100)
    asrc.set_property('block', True)
    asrc.set_property('emit-signals', False)
    
    capsstr = 'audio/x-raw-int, endianness=1234, rate=%s, channels=1, width=16, signed=true' % (a.tcgen.samplerate)
    asrccaps = gst.caps_from_string(capsstr)
    a.asrccaps = asrccaps
    #asrc.set_property('caps', asrccaps)
    #print 'asrc caps: ', asrccaps.to_string()
    asrccapf = gst.element_factory_make('capsfilter')
    #asrccaps = gst.Caps()
    asrccapf.set_property('caps', asrccaps.copy())
    testasrccapf = gst.element_factory_make('capsfilter')
    testasrccapf.set_property('caps', asrccaps.copy())
    #asrc.set_property('caps', asrccaps)
    aident = gst.element_factory_make('identity')
    #aident.set_property('datarate', a.tcgen.samplerate * 2)
    audrate = gst.element_factory_make('audiorate')
    #audrate.set_property('quality', 10)
    #audratecaps = gst.caps_from_string('audio/x-raw-int, rate=48000')
    audratecaps = gst.caps_from_string(capsstr)
    audratecapf = gst.element_factory_make('capsfilter')
    audratecapf.set_property('caps', audratecaps)
    aenc = gst.element_factory_make('wavenc')
    aconv = gst.element_factory_make('audioconvert')
    #arate = gst.element_factory_make('audiorate')
    #aout = gst.element_factory_make('fakesink')
    #aout = gst.element_factory_make('filesink')
    #aout.set_property('location', '/home/nocarrier/ltctest.wav')
    #aout = gst.element_factory_make('jackaudiosink')
    aout = gst.element_factory_make('autoaudiosink')
    testout = gst.element_factory_make('fakesink')
    
    vidchain = [vsrc, vrate, vqueue, vident, vcapf, vout]
    for e in vidchain:
        p.add(e)
    gst.element_link_many(*vidchain)
    audchain = [asrc, asrccapf, audrate, aout]
    for e in audchain:
        p.add(e)
    gst.element_link_many(*audchain)
    audchain2 = [testasrc, aqueue2, aident, testasrccapf, testout]
    for e in audchain2:
        p.add(e)
    gst.element_link_many(*audchain2)
    vident.connect('handoff', a.on_vident_handoff)
    aident.connect('handoff', a.on_aident_handoff)
    asrc.connect('need-data', a.on_audneeddata)
    
    gobject.threads_init()
    p.set_state(gst.STATE_PLAYING)
    #time.sleep(5.)
    #p.set_state(gst.STATE_NULL)
    #print 'finish'
    loop = glib.MainLoop()
    #t = threading.Timer(5., loop.quit)
    #t.start()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    print 'finish'
    
#if __name__ == '__main__':
#    import time
#    tcgen = LTCGenerator()
#    d = tcgen.frame_obj.get_all_obj()
#    #d['minute'].value = 1
#    #d['hour'].value = 2
#    d['second'].value = 58
#    d['frame'].value = 28
#    keys = ['hour', 'minute', 'second', 'frame']
#    values = tcgen.frame_obj.get_values()
#    #print ':'.join(['%02d' % (values[key]) for key in keys])
#    for i in range(61):
#        tcgen.frame_obj += 1
#        values = tcgen.frame_obj.get_values()
#        #print ':'.join(['%02d' % (values[key]) for key in keys]), '   ', i
#    a = tcgen.build_audio_data()
#    #print a
#    
