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
# misc.py
# Copyright (c) 2010 - 2011 Matthew Reid

import sys
import stat
import os.path
import subprocess
import threading
import uuid
import bisect

from BaseObject import BaseObject
from RepeatTimer import RepeatTimer

def setID(id):
    if id is None:
        id = str(uuid.uuid4()).replace('-', '_')
        #id = id.urn
    return id
    
    
def iterbases(obj, lastclass='object'):
    if type(lastclass) == type:
        lastclass = lastclass.__name__
    if type(obj) == type:
        cls = obj
    else:
        cls = obj.__class__
    while cls.__name__ != lastclass:
        yield cls
        cls = cls.__bases__[0]
        
def hexstr(string, obj=None):
    outstr = ''
    if isinstance(string, str):
        l = [ord(char) for char in string]
    else:
        l = string
        
    for i in l:
        outstr += '$%X ' % i
    return outstr
    
_stat_mode_map = {'user':'USR', 'group':'GRP', 'all':'OTH'}
def _get_stat_mod_flag(who, value):
    s = 'S_I%s%s' % (value.upper(), _stat_mode_map[who])
    return getattr(stat, s)
    
def get_filemode(filename):
    if not os.path.exists(filename):
        return False
    m = os.stat(filename).st_mode
    oct_str = ''
    d = {}
    for key in ['user', 'group', 'all']:
        s = ''
        oct_val = 0
        for i, pm in enumerate('xwr'):
            flag = _get_stat_mod_flag(key, pm)
            if m & flag == flag:
                s += pm
                oct_val += 1 << i
        d[key] = s
        #oct_str += ('%03i' % (oct_val))[::-1]
        oct_str += str(oct_val)
    d['octal'] = int(oct_str)
    return d
    
def set_filemode(filename, **kwargs):
    '''
    :Parameters:
        octal : int or str using octal chmod format (overrides all other parameters)
        user : string containing combination of 'rwx'
        group :
        all : 
    '''
    if not os.path.exists(filename):
        return False
    m = 0
    oct_val = kwargs.get('octal')
    if oct_val is not None:
        oct_val = ('%03i' % (int(oct_val)))
        for keyint, key in enumerate(['user', 'group', 'all']):
            for i, pm in enumerate('xwr'):
                if int(oct_val[keyint]) & (1 << i) == 0:
                    continue
                flag = _get_stat_mod_flag(key, pm)
                m |= flag
    else:
        for key in _stat_mode_map.keys():
            val = kwargs.get(key)
            if val is None:
                continue
            for pm in 'rwx':
                if pm not in val:
                    continue
                flag = _get_stat_mod_flag(key, pm)
                m |= flag
    os.chmod(filename, m)
    
popen_kwargs = dict(shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, close_fds=True)
def get_processes(keyfield=None):
    p = subprocess.Popen('ps xa', **popen_kwargs)
    s = p.stdout.read()
    d = {}
    for lindex, line in enumerate(s.splitlines()):
        fields = line.split()
        if lindex == 0:
            keys = fields
            if keyfield and keyfield in fields:
                keyindex = fields.index(keyfield)
            else:
                keyfield = fields[0]
                keyindex = 0
        else:
            pkey = fields[keyindex]
            d[pkey] = {}
            for kindex, key in enumerate(keys):
                d[pkey][key] = fields[kindex]
    p.kill()
    return d
    
def search_for_process(name):
    ps = get_processes('COMMAND')
    for key, val in ps.iteritems():
        cmd = val['COMMAND']
        if '/' in cmd:
            cmd = os.path.basename(cmd)
        if name in cmd:
            return val['PID']
    return False
    
#    p = subprocess.Popen('ps xa', **popen_kwargs)
#    s = p.stdout.read()
#    for line in s.splitlines():
#        fields = line.split()
#        if len(fields) >= 5:
#            pid = fields[0]
#            pcmd = fields[4]
#            if '/' in pcmd:
#                pcmd = os.path.basename(pcmd)
#            if name in pcmd:
#                return pid
#    return False
    
class SyncThread(threading.Thread):
    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        self.timeout = kwargs.get('timeout', 3.0)
        self.waiting_thread = threading.currentThread()
        self.callback = kwargs.get('callback')
    def run(self):
        #print '%s waiting for %s' % (self.name, self.waiting_thread.name)
        self.waiting_thread.join(self.timeout)
        #if not self.waiting_thread.isAlive:
        #    print '%s done waiting for %s' % (self.name, self.waiting_thread.name)
        #else:
        #    print '%s timed out waiting for %s' % (self.name, self.waiting_thread.name)
        self.callback(self)
        
class GenericPoll(BaseObject):
    def __init__(self, **kwargs):
        super(GenericPoll, self).__init__(**kwargs)
        self.interval = kwargs.get('interval', 2.0)
        self.polling = False
        self.interval_call = kwargs.get('interval_call')
        self.timer = None
    def start_poll(self, **kwargs):
        self.stop_poll()
        self.timer = RepeatTimer(self.interval, self.on_interval)
        self.polling = True
        self.timer.start()
    def stop_poll(self, **kwargs):
        if self.polling:
            self.polling = False
            self.timer.cancel()
        self.timer = None
    def on_interval(self):
        if self.interval_call is not None:
            self.interval_call()
    


def parse_csv(filename):
    file = open(filename, 'r')
    d = {}
    for line_num, line in enumerate(file):
        if line_num == 0:
            keys = [col for col in line.strip().split(',')]
            for key in keys:
                d.update({key:[]})
        else:
            items = [float(item.strip('dB')) for item in line.strip().split(',')]
            for i, item in enumerate(items):
                d[keys[i]].append(item)
    file.close()
    return d

def find_nearest_items(iterable, value):
    if not len(iterable):
        return False
    if len(iterable) == 1:
        index = [0, 0]
        return (index, [iterable[x] for x in index])
    i = bisect.bisect_left(iterable, value)
    if i == 0:
        index = [i, i]
    elif i >= len(iterable):
        index = [i - 1, i - 1]
    else:
        index = [i - 1, i]
    return (index, [iterable[x] for x in index])

class Interpolator(object):
    def __init__(self, **kwargs):
        self.data = {}
        self.x_keys = []
        points = kwargs.get('points')
        if points is not None:
            for point in points:
                self.add_point(*point)
        
    def add_point(self, x, y):
        #x = self.datatype(x)
        #y = self.datatype(y)
        self.data[x] = y
        if x in self.x_keys:
            return
        self.x_keys = sorted(self.data.keys())
        
    def solve_y(self, x):
        keys = self.x_keys
        data = self.data
        if x in keys:
            return data[x]
#        if not len(keys):
#            return False
#        i = bisect.bisect_left(keys, x)
#        if i == 0:
#            return data[keys[0]]
#        if i >= len(keys):
#            return data[keys[i-1]]
        index, _x = find_nearest_items(keys, x)
        if _x is False:
            return False
        #_x = [keys[i-1], keys[i]]
        _y = [data[key] for key in _x]
        if _y[0] == _y[1]:
            return _y[0]
        return _y[0] + (_y[1] - _y[0]) * ((x - _x[0]) / (_x[1] - _x[0]))
        
