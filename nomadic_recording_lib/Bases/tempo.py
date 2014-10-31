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
# tempo.py
# Copyright (c) 2011 Matthew Reid

import collections
import datetime

from BaseObject import BaseObject
from masterclock import MasterClock
from incrementor import Incrementor


def seconds_to_bpm(seconds):
    return 60. / seconds
    
def bpm_to_seconds(bpm):
    return 60. / bpm


class TapTempo(BaseObject):
    _Properties = {'tempo':dict(default=0., quiet=True), 
                   'tap':dict(default=False, quiet=True)}
    _minimum_tap_count = 2
    _maximum_tap_count = 4
    _maximum_tap_distance = 2  ##(seconds)
    def __init__(self, **kwargs):
        super(TapTempo, self).__init__(**kwargs)
        self._clock_is_local = False
        clock = kwargs.get('clock')
        if not clock:
            clock = MasterClock()
            clock.start()
            self._clock_is_local = True
        self.clock = clock
        self.last_taps = collections.deque()
        self.bind(tap=self._on_tap)
        
    def unlink(self):
        super(TapTempo, self).unlink()
        if self._clock_is_local:
            self.clock.stop()
        
    def _on_tap(self, **kwargs):
        if not kwargs.get('value'):
            return
        now = self.clock.get_now()
        seconds = self.clock.calc_seconds(now)
        self.last_taps.append(seconds)
        self.tap = False
        if len(self.last_taps) >= self._minimum_tap_count:
            self.calculate_tempo()
            
    def calculate_tempo(self):
        if len(self.last_taps) < self._minimum_tap_count:
            return
        if len(self.last_taps) > self._maximum_tap_count:
            t = self.last_taps.popleft()
        remove_tap = None
        tapsum = 0.
        for i, tap in enumerate(self.last_taps):
            if i == 0:
                continue
            lasttap = self.last_taps[i-1]
            diff = tap - lasttap
            if diff > self._maximum_tap_distance:
                remove_tap = i - 1
                break
            tapsum += diff
        if remove_tap is not None:
            del self.last_taps[remove_tap]
            return self.calculate_tempo()
        avg = tapsum / (len(self.last_taps) - 1)
        self.tempo = seconds_to_bpm(avg)

class Sequencer(BaseObject):
    _mbt_keys = ['measure', 'beat', 'tick', 'total_beats']
    _Properties = {'tempo':dict(default=120., min=30., max=300.), 
                   'playing':dict(default=False), 
                   'tick_resolution':dict(default=120), 
                   'position_mbt':dict(default=dict(zip(_mbt_keys, [1]*4)), quiet=True), 
                   'position_seconds':dict(default=0., quiet=True)}
    _SettingsProperties = ['tempo', 'tick_resolution']
    def __init__(self, **kwargs):
        super(Sequencer, self).__init__(**kwargs)
        self.TickObj = MidiTick()
        self.time_signature_divisor = 4
        self.beats_per_measure = 4
        tick_int = bpm_to_seconds(self.tempo) / self.tick_resolution
        clock_int = tick_int / 4
        self.clock = MasterClock(tick_interval=tick_int, clock_interval=clock_int)
        self.clock.start()
        #self.clock.add_raw_tick_callback(self.on_clock_tick)
        self.clock.add_callback(self.on_clock_tick)
        
    def play(self, **kwargs):
        if self.playing:
            return
        p_mbt = kwargs.get('position_mbt')
        if p_mbt is not None:
            self.Properties['position_mbt'].set_value(p_mbt)
        self.start_mbt = self.position_mbt.copy()
        self.start_time = None
        self.playing = True
        
    def stop(self):
        self.playing = False
        
    def on_clock_tick(self, clock, seconds):
        if not self.playing:
            return
        if self.start_time is None:
            self.start_time = seconds
        self.calc_position(seconds)
        self.TickObj += 1
        
    def calc_position(self, seconds):
        total_seconds = seconds - self.start_time
        beats = total_seconds / (60. / self.tempo)
        offset = beats + self.start_mbt['total_beats'] - 1
        old_ticks = self.position_mbt['tick']
        self.mbt_set_local = True
        self.Properties['position_mbt'].set_value(self.calc_mbt(offset))
        self.mbt_set_local = False
        if self.position_mbt['tick'] != old_ticks + 1 and self.position_mbt['tick'] != 0:
            self.LOG.warning(self, 'skipped tick', old_ticks + 1)
        #self.seconds_set_local = True
        #self.position_seconds = seconds
        #self.seconds_set_local = False
        
    def calc_mbt(self, beats):
        mbt = {}
        mbt['measure'] = int(beats / self.beats_per_measure)
        #if mbt['measure'] > 0:
        mbt['beat'] = int(beats - (mbt['measure'] * self.beats_per_measure)) + 1
        #else:
        #    mbt['beat'] = int(beats)
        mbt['tick'] = int((beats - int(beats)) * self.tick_resolution)
        mbt['total_beats'] = beats
        #print ':'.join(['%03d' % (mbt[key]) for key in ['measure', 'beat', 'tick']])
        return mbt

    
class MidiTick(Incrementor):
    _resolution = 120
    def __init__(self, **kwargs):
        kwargs.setdefault('name', 'tick')
        super(MidiTick, self).__init__(**kwargs)
        self.add_child('beat', MidiBeat)
    
class MidiBeat(Incrementor):
    _resolution = 4
    def __init__(self, **kwargs):
        super(MidiBeat, self).__init__(**kwargs)
        self.add_child('measure', MidiMeasure)
        
class MidiMeasure(Incrementor):
    pass
    
    
class TestWindow(object):
    def __init__(self, **kwargs):
        self.seq = kwargs.get('seq')
        self.win = gtk.Window()
        self.val_lbls = {}
        vbox = gtk.VBox()
        mbtobj = self.seq.TickObj.get_all_obj()
        for key in Sequencer._mbt_keys:
            hbox = gtk.HBox()
            namelbl = gtk.Label(key)
            hbox.pack_start(namelbl)
            val_lbl = gtk.Label('000')
            hbox.pack_start(val_lbl)
            self.val_lbls[key] = val_lbl
            vbox.pack_start(hbox)
            if key in mbtobj:
                mbtobj[key].bind(value=self.on_mbtobj_value_set)
        hbox = gtk.HBox()
        for key in ['Play', 'Stop', 'test']:
            btn = gtk.Button(label=key)
            btn.connect('clicked', self.on_btns_clicked, key)
            hbox.pack_start(btn)
        vbox.pack_start(hbox)
        self.win.add(vbox)
        #self.seq.bind(position_mbt=self.on_mbt_set)
        self.win.show_all()
    def on_mbt_set(self, **kwargs):
        value = kwargs.get('value')
        for key in Sequencer._mbt_keys:
            self.val_lbls[key].set_text('%03d' % (value[key]))
    def on_mbtobj_value_set(self, **kwargs):
        obj = kwargs.get('obj')
        self.val_lbls[obj.name].set_text('%03d' % (obj.value + 1))
    def on_btns_clicked(self, btn, key):
        if key == 'Play':
            self.seq.play()
        elif key == 'Stop':
            self.seq.stop()
        else:
            pass
            #print 'vals: ', self.seq.TickObj.get_values()
            #print 'sum: ', self.seq.TickObj.get_root_sum()
#if __name__ == '__main__':
#    import gtk
#    gtk.gdk.threads_init()
#    seq = Sequencer()
#    tick = seq.TickObj
#    v = tick.get_root_sum()
#    print 'start sum: ', v
#    print 'start vals: ', tick.get_values()
#    for i in range(120):
#        tick += 1
#    print 'new vals: ', tick.get_values()
#    v = tick.get_root_sum()
#    print 'tickobj sum: ', v
#    print tick.get_values()
#    tick.set_root_sum(v)
#    v = tick.get_root_sum()
#    print 'new sum: ', v
#    tick.reset_values()
#    w = TestWindow(seq=seq)
#    gtk.main()
