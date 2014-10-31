import os.path
import base64
import zipfile
from xml.dom import minidom

def open_touchosc(filename):
    zip = zipfile.ZipFile(filename, 'r')
    xml_str = False
    if 'index.xml' in zip.namelist():
        file = zip.open('index.xml', 'r')
        xml_str = ''
        for line in file:
            xml_str += line
        file.close()
    zip.close()
    return xml_str
    
def get_name(element):
    return base64.decodestring(element.getAttribute('name'))

class Layout(object):
    _properties = ['version', 'mode', 'orientation']
    def __init__(self, **kwargs):
        filename = kwargs.get('filename')
        self.name = os.path.splitext(os.path.basename(filename))[0]
        xml_str = open_touchosc(filename)
        dom = minidom.parseString(xml_str)
        l_elem = dom.getElementsByTagName('layout')[0]
        self.attributes = {}
        for attr in self._properties:
            value = str(l_elem.getAttribute(attr))
            if attr == 'orientation':
                if value == 'horizontal':
                    value = 'vertical'
                elif value == 'vertical':
                    value = 'horizontal'
            self.attributes.update({attr:value})
            setattr(self, attr, value)
        self.Pages = {}
        self.AllControls = {}
        for p_elem in dom.getElementsByTagName('tabpage'):
            page = Page(element=p_elem, layout=self)
            self.Pages.update({page.name:page})
            self.AllControls.update(page.Controls)
        
class Page(object):
    def __init__(self, **kwargs):
        self.Layout = kwargs.get('layout')
        element = kwargs.get('element')
        self.name = get_name(element)
        self.Controls = {}
        for c_elem in element.getElementsByTagName('control'):
            control = Control(element=c_elem, page=self)
            self.Controls.update({control.name:control})
            
class Control(object):
    _type = None
    _properties = ['x', 'y', 'w', 'h', 'color', 
                   'scalef', 'scalet', 'osc_cs', 'type']
    def __new__(cls, **kwargs):
        if cls != Control:
            return super(Control, cls).__new__(cls, **kwargs)
        element = kwargs.get('element')
        c_type = element.getAttribute('type')
        for c_cls in controlClasses:
            if c_cls._type == c_type or c_cls._type == c_type[:-1]:
                return c_cls(**kwargs)
        return ControlFallback(**kwargs)
        
    def __init__(self, **kwargs):
        element = kwargs.get('element')
        self.name = get_name(element)
        self.Page = kwargs.get('page')
        self.Layout = self.Page.Layout
        self.type = str(element.getAttribute('type'))
        if self._type and self.type != self._type:
            self.orientation = {'h':'horizontal', 'v':'vertical'}.get(self.type[-1:])
        self.attributes = {}
        properties = set(Control._properties)
        properties |= set(self.__class__._properties)
        for attr in properties:
            if element.hasAttribute(attr):
                value = str(element.getAttribute(attr))
                self.attributes.update({attr:value})
                setattr(self, attr, value)
                
class ControlFallback(Control):
    pass
    
class LED(Control):
    _type = 'led'
class Label(Control):
    _type = 'label'
    _properties = ['outline', 'background', 'size']
class Button(Control):
    _type = 'push'
    _properties = ['local_off']
class Toggle(Control):
    _type = 'toggle'
    _properties = ['local_off']
class xyPad(Control):
    _type = 'xy'
    _properties = ['inverted_x', 'inverted_y']
class Fader(Control):
    _type = 'fader'
    _properties = ['inverted', 'centered', 'response']
class Rotary(Control):
    _type = 'rotary'
    _properties = ['inverted', 'centered', 'response']
class Battery(Control):
    _type = 'battery'
    _properties = ['outline', 'background', 'size']
class Time(Control):
    _type = 'time'
    _properties = ['outline', 'background', 'seconds', 'size']
class MultiToggle(Control):
    _type = 'multitoggle'
    _properties = ['number_x', 'number_y']
class MultiFader(Control):
    _type = 'multifader'
    _properties = ['inverted', 'centered', 'number']
    
controlClasses = (LED, Label, Button, Toggle, xyPad, Fader, Rotary, Battery, Time, MultiToggle, MultiFader)

if __name__ == '__main__':
    #s = open_touchosc('touchosctest1.touchosc')
    #print s
    #d = parse_xml(s)
    layout = Layout(filename='touchosctest1.touchosc')
    
    print 'layout:', layout.name, layout.attributes
    for pkey, pval in layout.Pages.iteritems():
        print 'page:', pkey
        for ckey, cval in pval.Controls.iteritems():
            print ckey, cval._type, cval.__class__.__name__, cval.attributes
    
    
