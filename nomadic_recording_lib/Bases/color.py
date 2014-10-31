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
# color.py
# Copyright (c) 2010 - 2011 Matthew Reid

import array
import bisect
import colorsys
from BaseObject import BaseObject

rgb_keys = ['red', 'green', 'blue']
hsv_keys = ['hue', 'sat', 'val']
colorprops = dict(zip(rgb_keys + hsv_keys, [{'default':0., 'min':0., 'max':1.}]*6))
colorprops.update(dict(zip(['rgb', 'hsv'], [dict(default=dict(zip(keys, [0.]*3)), 
                                            min=dict(zip(keys, [0.]*3)), 
                                            max=dict(zip(keys, [1.]*3)), 
                                            quiet=True) for keys in [rgb_keys, hsv_keys]])))
#for key, val in colorprops.iteritems():
#    val.update({'fget':'_'.join([key, 'getter'])})

class Color(BaseObject):
    _Properties = colorprops
    def __init__(self, **kwargs):
        super(Color, self).__init__(**kwargs)
        self._rgb_set_local = False
        self._hsv_set_local = False
        self._rgb_props_set_local = False
        self._hsv_props_set_local = False
        self.bind(rgb=self._on_rgb_set, 
                  hsv=self._on_hsv_set, 
                  property_changed=self.on_own_property_changed)
        
    @property
    def rgb_seq(self):
        rgb = self.rgb
        return list((rgb[key] for key in rgb_keys))
    @property
    def hsv_seq(self):
        hsv = self.hsv
        return list((hsv[key] for key in hsv_keys))
        
    def _on_rgb_set(self, **kwargs):
        self._rgb_props_set_local = True
        for key, val in self.rgb.iteritems():
            setattr(self, key, val)
        self._rgb_props_set_local = False
        if self._rgb_set_local:
            return
        self._hsv_set_local = True
        self.hsv = dict(zip(hsv_keys, colorsys.rgb_to_hsv(*self.rgb_seq)))
        self._hsv_set_local = False
        
    def _on_hsv_set(self, **kwargs):
        self._hsv_props_set_local = True
        for key, val in self.hsv.iteritems():
            setattr(self, key, val)
        self._hsv_props_set_local = False
        if self._hsv_set_local:
            return
        self._rgb_set_local = True
        self.rgb = dict(zip(rgb_keys, colorsys.hsv_to_rgb(*self.hsv_seq)))
        self._rgb_set_local = False
        
    def on_own_property_changed(self, **kwargs):
        prop = kwargs.get('Property')
        value = kwargs.get('value')
        if prop.name in rgb_keys and not self._rgb_props_set_local:
            self.rgb[prop.name] = value
        elif prop.name in hsv_keys and not self._hsv_props_set_local:
            self.hsv[prop.name] = value
            

arraytype_map = {'c':chr}

class PixelGrid(BaseObject):
    hsv_keys = ['hue', 'sat', 'val']
    def __init__(self, **kwargs):
        super(PixelGrid, self).__init__(**kwargs)
        self.pixels_by_hsv = {}
        self.size = kwargs.get('size', (64, 64))
        self.pixels = []
        self.build_grid()
        
    def resize(self, **kwargs):
        self.clear_grid()
        self.size = kwargs.get('size')
        self.build_grid()
        
    def build_grid(self):
        for row in range(self.num_rows):
            line = []
            for col in range(self.num_cols):
                pixel = Color()
                pixel.grid_location = {'row':row, 'col':col}
                self.add_pixel_to_hsv_dict(pixel)
                line.append(pixel)
                pixel.bind(property_changed=self.on_pixel_changed)
            self.pixels.append(line)
        
    def add_pixel_to_hsv_dict(self, pixel):
        h, s, v = pixel.hsv_seq
        if h not in self.pixels_by_hsv:
            self.pixels_by_hsv[h] = {}
        if s not in self.pixels_by_hsv[h]:
            self.pixels_by_hsv[h][s] = {}
        if v not in self.pixels_by_hsv[h][s]:
            self.pixels_by_hsv[h][s][v] = []
        self.pixels_by_hsv[h][s][v].append(pixel)
    
    def setattr_all_pixels(self, **kwargs):
        for row in self.pixels:
            for pixel in row:
                for key, val in kwargs.iteritems():
                    setattr(pixel, key, val)
    
    def clear_grid(self):
        for row in self.pixels:
            for pixel in row:
                pixel.unbind(self.on_pixel_changed)
        self.pixels_by_hsv.clear()
        self.pixels = []
                
    @property
    def num_rows(self):
        return self.size[0]
    @property
    def num_cols(self):
        return self.size[1]
        
    def iterrows(self):
        return range(self.num_rows)
    def itercols(self):
        return range(self.num_cols)
        
    def find_pixels_from_hsv(self, hsv):
        if isinstance(hsv, dict):
            hsv = [hsv[key] for key in self.hsv_keys]
        d = self.pixels_by_hsv
        for i, value in enumerate(hsv):
            l = sorted(d.keys())
            index = bisect.bisect_left(l, value)
            if index == len(l):
                key = l[index-1]
            else:
                key = l[index]
            if index != 0:
                last = l[index-1]
                if value - last < key - value:
                    key = last
            d = d[key]
        return d
        
    def get_ogl_pixel_data(self, **kwargs):
        color_format = kwargs.get('color_format', 'rgb')
        arraytype = kwargs.get('arraytype', 'c')
        a = array.array(arraytype)
        for y in self.iterrows():
            for x in self.itercols():
                pixel = self.pixels[y][x]
                keys = ['red', 'green', 'blue']
                for key in keys:
                    a.append(arraytype_map[arraytype](int(getattr(pixel, key))))
        return a
    
    def on_pixel_changed(self, **kwargs):
        def remove_old_location(pixel, old):
            h = self.pixels_by_hsv.get(old['hue'])
            if not h:
                return
            s = h.get(old['sat'])
            if not s:
                return
            v = s.get(old['val'])
            if not v:
                return
            if pixel in v:
                del v[v.index(pixel)]
            if not len(v):
                del s[old['val']]
            if not len(s):
                del h[old['sat']]
            if not len(h):
                del self.pixels_by_hsv[old['hue']]
        prop = kwargs.get('Property')
        if prop.name in self.hsv_keys:
            pixel = kwargs.get('obj')
            old = kwargs.get('old')
            oldhsv = pixel.hsv
            oldhsv[prop.name] = old
            remove_old_location(pixel, oldhsv)
            self.add_pixel_to_hsv_dict(pixel)
            
        
if __name__ == '__main__':
    grid = PixelGrid(size=(16, 16))
    for y, row in enumerate(grid.pixels):
        for x, pixel in enumerate(row):
            pixel.red = y * 255. / grid.num_rows
            pixel.green = (y * -255. / grid.num_rows) + 255
            pixel.blue = x * 255. / grid.num_cols
    d = {}
    for hkey, hval in grid.pixels_by_hsv.iteritems():
        d[hkey] = {}
        for skey, sval in hval.iteritems():
            d[hkey][skey] = {}
            for vkey, vval in sval.iteritems():
                d[hkey][skey][vkey] = [p.hsv_seq for p in vval]
    p = grid.find_pixels_from_hsv([1., 1., 1.])
    #print p[0].hsv
    
