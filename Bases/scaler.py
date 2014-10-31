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
# scaler.py
# Copyright (c) 2010 - 2011 Matthew Reid

import decimal
import math

from BaseObject import BaseObject

class Scaler(BaseObject):
    def __init__(self, **kwargs):
        super(Scaler, self).__init__(**kwargs)
        self.register_signal('value_update')
        self.scales = {}
        scales = kwargs.get('scales')
        for key, val in scales.iteritems():
            sc_kwargs = val.copy()
            sc_kwargs.update({'name':key})
            if False:#sc_kwargs.get('LOG', False) is True:
                sc = LogScale(**sc_kwargs)
            else:
                sc = FloatScale(**sc_kwargs)
            self.scales.update({key:sc})
            self.scales[key].connect('value_update', self.on_scale_value_update)
    def set_value(self, scale_name, value):
        self.scales[scale_name].set_value(value)
        f_value = self.scales[scale_name].scaled
        for key, val in self.scales.iteritems():
            if key != scale_name:
                val.set_float_value(f_value)
                #if val.scaled != f_value:
                #    bob
                
    def get_value(self, scale_name, decimal_places=None):
        if decimal_places is None:
            return self.scales[scale_name].value
        q = decimal.Decimal(10) ** -decimal_places
        d = decimal.Decimal(str(self.scales[scale_name].value))
        return d.quantize(q)
        #fstr = str(decimal_places).join(['%.', 'f'])
        #s = fstr % (self.scales[scale_name].value)
        #return float(s)
        
    #def get_scaled(self, scale_in, scale_out):
    #    val_in = self.scales[scale_in].scaled
    #    val_out = val_in * self.scales[scale_out].max
    #    return val_out
    
    def on_scale_value_update(self, **kwargs):
        obj = kwargs.get('obj')
        if obj.name in self.scales:
            self.emit('value_update', obj=obj, name=obj.name, value=obj.value)

class FloatScale(BaseObject):
    def __init__(self, **kwargs):
        super(FloatScale, self).__init__(**kwargs)
        self.register_signal('value_update')
        self.name = kwargs.get('name')
        self.max = kwargs.get('max')
        self.min = kwargs.get('min', 0.0)
        self.value = kwargs.get('value', 0.0)
        self.offset_max = float(self.max - self.min)
        self.scale_factor = 1.0 / float(self.offset_max)
        #self.scaled_offset = 1.0 / float(self.min)
        
        self.scaled = self.do_scale_to_float()
    def set_value(self, value):
        if value != self.value:
            self.value = float(value)
            self.scaled = self.do_scale_to_float()
            #self.emit('value_update', obj=self, value=self.value)
    def set_float_value(self, value):
        self.value = self.do_scale_from_float(value)
        self.scaled = self.do_scale_to_float()
        self.emit('value_update', obj=self, value=value)
    def do_scale_from_float(self, value):
        return (value * self.offset_max) + self.min
    def do_scale_to_float(self, value=None):
        if value is None:
            value = self.value
        return float(value - self.min) * self.scale_factor
        
class LogScale(FloatScale):
    def __init__(self, **kwargs):
        max = kwargs.get('max')
        min = kwargs.get('min')
        if min < 0:
            self.log_max = float(-min)#float(max - min)
            self.log_offset = -min
        elif min == 0:
            self.log_max = float(max)
            self.log_offset = 0.0
        else:
            self.log_max = float(max - min)
            self.log_offset = min
        #self.log_max_amplitude = 10 ** (self.log_max / 20.0)
        #self.log_inverted = False
        super(LogScale, self).__init__(**kwargs)
        
    def set_value(self, value):
        value = float(value)
        if value != self.value:
            self.value = value
            #l = self._set_inv_log_value(value)
            #self.scaled = self.do_scale_to_float(l)
            self.scaled = self._log_to_float(value)
            
    def set_float_value(self, value):
        #scaled = self.do_scale_from_float(value)
        #self.value = self._set_log_value(scaled)
        #self.scaled = self.do_scale_to_float(self.value)
        self.value = self._float_to_log(value)
        self.scaled = value
        self.emit('value_update', obj=self, value=self.value)
            
#    def _set_log_value(self, value):
#        offset = value + self.log_offset
#        if offset <= 0.0:
#            l = 0.0
#            print 'zero'
#        else:
#            #l = self.log_max * math.log(offset, self.log_max)
#            l = self.log_max * math.log10(offset/10.0)
#        return l - self.log_offset
#        
#    def _set_inv_log_value(self, value):
#        offset = float(value) + self.log_offset
#        #f = self.log_max ** (offset / self.log_max)
#        f = 10.0 * (10 ** (offset / self.log_max))
#        return f - self.log_offset
    
    def _log_to_float(self, value):
        offset = value - self.max
        return 60. ** (offset / 120.)
    def _float_to_log(self, value):
        if value <= 0.0:
            return self.min
        #l = 60 * math.log10(float(value))
        l = 120. * math.log(value, 60.)
        offset = l + self.max
        if offset < self.min:
            return self.min
        return offset
