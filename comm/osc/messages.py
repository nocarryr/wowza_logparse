import struct
import types
import math
import datetime

OSC_EPOCH = datetime.datetime(1900, 1, 1, 0, 0, 0)

class OSCStreamException(Exception):
    def __init__(self, value):
        self._value = value
    def __str__(self):
        return 'OSC Stream Size Error: ' + str(self._value)

class Message(object):
    def __init__(self, *args, **kwargs):
        self.client = kwargs.get('client')
        self.timestamp = kwargs.get('timestamp')
        data = kwargs.get('data')
        if data is not None:
            kwargs = self.parse_data(data)
        if 'args' in kwargs:
            args = kwargs['args']
        self.address = kwargs.get('address')
        self.arguments = []
        for arg in args:
            self.add_argument(arg)
            
    @property
    def address(self):
        return self._address
    @address.setter
    def address(self, value):
        if value[0] != '/':
            value = '/' + value
        self._address = Address(value)
    @property
    def client(self):
        return self._client
    @client.setter
    def client(self, value):
        self._client = value
    @property
    def type_tags(self):
        return StringArgument(',' + ''.join([arg._type_tag for arg in self.arguments]))
        
    def add_argument(self, arg):
        if not getattr(arg, '_OSC_ARGUMENT_INSTANCE', False):
            arg = build_argument(obj=arg)
        self.arguments.append(arg)
        
    def get_arguments(self):
        return [arg.real_value for arg in self.arguments]
        
    def parse_data(self, data):
        address, data = _strip_padding(data)
        tags, data = _strip_padding(data)
        args = []
        if len(tags) == 1:
            tags = []
        else:
            tags = tags[1:]
        for tag in tags:
            arg, data = build_argument(type_tag=tag, data=data)
            args.append(arg)
        return dict(address=address, args=args)
        
    def build_string(self):
        args = [self.address, self.type_tags]
        args.extend(self.arguments)
        s = ''.join([arg.build_string() for arg in args])
        if len(s) % 4 != 0:
            raise OSCStreamException(len(s))
        return s
        
    def __str__(self):
        s = self.address.build_string() + self.type_tags.build_string()
        s = s.replace('\0', ' ')
        s += ' '.join([str(arg) for arg in self.arguments])
        return s
    
    
class Bundle(object):
    def __init__(self, *args, **kwargs):
        self.elements = []
        self.client = kwargs.get('client')
        self.timestamp = kwargs.get('timestamp')
        data = kwargs.get('data')
        if data is not None:
            kwargs = self.parse_data(data)
        timetag = kwargs.get('timetag', -1)
        if not isinstance(timetag, TimetagArgument):
            timetag = TimetagArgument(timetag)
        self.timetag = timetag
        if 'elements' in kwargs:
            args = kwargs['elements']
        for element in args:
            self.add_element(element)
    @property
    def client(self):
        return self._client
    @client.setter
    def client(self, value):
        self._client = value
        for e in self.elements:
            e.client = value
    def parse_data(self, data):
        #print 'bundle parse: ', len(data), [data]
        bundlestr, data = _strip_padding(data)
        #print 'bundlestr: ', [bundlestr], ', data: ', len(data), [data]
        timetag, data = TimetagArgument.from_binary(TimetagArgument, data)
        #print 'parse timetag: ', timetag
        #print 'dataremain: ', len(data), [data]
        elements = []
        while len(data):
            size, data = IntArgument.from_binary(IntArgument, data)
            elemdata = data[:size]
            #print 'elem size: ', size
            elements.append(elemdata)
            data = data[size:]
        return dict(timetag=timetag, elements=elements)
    def add_element(self, element):
        if element.__class__ in [Bundle, Message]:
            element.client = self.client
            element.timestamp = self.timestamp
            self.elements.append(element)
            return
        #size, data = element
        realelement = parse_message(element, client=self.client, timestamp=self.timestamp)
        if realelement.__class__ in [Bundle, Message]:
            self.elements.append(realelement)
        return realelement
        
    def get_flat_messages(self):
        messages = []
        for e in self.elements:
            if isinstance(e, Bundle):
                messages.extend(e.get_flat_messages())
            else:
                messages.append(e)
        return messages
        
    def split_bundles(self):
        bundles = {}
        timetag = self.timetag
        bundles[timetag] = self
        to_remove = set()
        to_add = []
        for i, e in enumerate(self.elements):
            if not isinstance(e, Bundle):
                continue
            ebundles = e.split_bundles()
            if timetag in ebundles:
                if ebundles[timetag] not in self.elements:
                    to_add.append(ebundles[timetag])
                del ebundles[timetag]
            if e.timetag != timetag:
                to_remove.add(e)
            bundles.update(ebundles)
        for b in to_remove:
            self.elements.remove(b)
        for b in to_add:
            self.elements.append(b)
        return bundles
        
    def build_string(self):
        #data = ''.join([StringArgument('#bundle').build_string(), self.timetag.build_string()])
        bundlestr = StringArgument('#bundle').build_string()
        ttstr = self.timetag.build_string()
        #print 'bundle: ', len(bundlestr), [bundlestr]
        #print 'ttstr: ', len(ttstr), [ttstr]
        data = bundlestr + ttstr
        #print 'header: ', len(data), [data]
        for elem in self.elements:
            elemdata = elem.build_string()
            elemstr = IntArgument(len(elemdata)).build_string() + elemdata
            #print 'elem: ', len(elemdata), [elemstr]
            data += elemstr
        #print 'bundledata: ', len(data), [data]
        return data
        
    def __str__(self):
        s = 'bundle %s: ' % (self.timetag)
        l = []
        for elem in self.elements:
            elemdata = elem.build_string()
            l.append('len=%s: %s' % (len(elemdata), str(elem)))
            #l.append(str(elem))
        s += ', '.join([e for e in l])
        return s

class Argument(object):
    _OSC_ARGUMENT_INSTANCE = True
    @staticmethod
    def from_binary(cls, data, **kwargs):
        value, data = cls.parse_binary(cls, data, **kwargs)
        return cls(value), data
    @staticmethod
    def parse_binary(cls, data, **kwargs):
        struct_fmt = getattr(cls, '_struct_fmt', None)
        if struct_fmt is None:
            return None, data
        length = struct.calcsize(struct_fmt)
        value = struct.unpack(struct_fmt, data[:length])[0]
        return value, data[length:]
    def build_string(self):
        cls = getattr(self, '_pytype', self.__class__.__bases__[0])
        stuct_fmt = getattr(self, '_struct_fmt', None)
        if stuct_fmt is not None:
            s = struct.pack(stuct_fmt, cls(self))
            #print type(self), s
            return s
        return ''
    @property
    def real_value(self):
        return self
    
class IntArgument(int, Argument):
    _type_tag = 'i'
    #_pytype = int
    _struct_fmt = '>i'
    
class FloatArgument(float, Argument):
    _type_tag = 'f'
    #_pytype = float
    _struct_fmt = '>f'
    
class DoubleFloatArgument(float, Argument):
    _type_tag = 'd'
    _struct_fmt = '>d'
    
class StringArgument(str, Argument):
    _type_tag = 's'
    #_pytype = str
    #_struct_fmt = 's'
    @property
    def _struct_fmt(self):
        length = math.ceil((len(self)+1) / 4.0) * 4
        return '>%ds' % (length)
    @staticmethod
    def parse_binary(cls, data, **kwargs):
        return _strip_padding(data)
    def blahbuild_string(self):
        length = math.ceil((len(self)+1) / 4.0) * 4
        s = struct.pack('>%ds' % (length), self)
        print self, length
        return s
    
class BlobArgument(list, Argument):
    _type_tag = 'b'
    
class BoolArgument(Argument):
    _pytype = bool
    def __new__(cls, value):
        if cls == BoolArgument:
            if value:
                cls = TrueArgument
            else:
                cls = FalseArgument
            return cls.__new__(cls, value)
        #return Argument.__new__(cls, value)
        return object.__new__(cls)
    def __init__(self, value):
        self._value = value
    def __nonzero__(self):
        return self._value
    def __eq__(self, other):
        return other == self._value
    def __hash__(self):
        return id(self._value)
    @property
    def real_value(self):
        return self._value
    @staticmethod
    def from_binary(cls, data, **kwargs):
        if cls == TrueArgument:
            value = True
        elif cls == FalseArgument:
            value = False
        return cls(value), data
    
class TrueArgument(BoolArgument):
    _type_tag = 'T'
    
class FalseArgument(BoolArgument):
    _type_tag = 'F'
    
class NoneArgument(Argument):
    _type_tag = 'N'
    _pytype = types.NoneType
    def __new__(cls, *args):
        if cls == types.NoneType:
            cls = NoneArgument
        return super(NoneArgument, cls).__new__(cls)
    @property
    def real_value(self):
        return None
    def __hash__(self):
        return id(None)
    def __nonzero__(self):
        return False
    def __eq__(self, other):
        return other is None
    
class TimetagPyType(float):
    pass
    
class TimetagArgument(TimetagPyType, Argument):
    _type_tag = 't'
    _struct_fmt = '>qq'
    
    def build_string(self):
        if self < 0:
            return struct.pack('>qq', 0, 1)
        fr, sec = math.modf(self)
        return struct.pack('>qq', long(sec), long(fr * 1e9))
        
    @staticmethod
    def parse_binary(cls, data, **kwargs):
        msb, lsb = struct.unpack('>qq', data[:16])
        if msb == 1:
            value = -1
            data = data[8:]
        elif lsb == 1:
            value = -1
            data = data[16:]
        else:
            value = msb + float('.%i' % (lsb))
            data = data[16:]
        return value, data
        
    @property
    def datetime(self):
        if self < 0:
            return datetime.datetime.now()
        td = datetime.timedelta(seconds=self)
        dt = OSC_EPOCH + td
        #print dt
        return dt
        
    def __str__(self):
        return self.__repr__()

ARG_CLASSES = (IntArgument, FloatArgument, DoubleFloatArgument, StringArgument, 
               BlobArgument, BoolArgument, TrueArgument, FalseArgument, NoneArgument)
ARG_CLS_BY_PYTYPE = {}
ARG_CLS_BY_TYPE_TAG = {}
for argcls in ARG_CLASSES:
    if hasattr(argcls, '_pytype'):
        pytype = argcls._pytype
    else:
        pytype = argcls.__bases__[0]
    if pytype not in ARG_CLS_BY_PYTYPE:
        ARG_CLS_BY_PYTYPE[pytype] = argcls
    if hasattr(argcls, '_type_tag'):
        ARG_CLS_BY_TYPE_TAG[argcls._type_tag] = argcls
#ARG_CLS_BY_PYTYPE[True] = TrueArgument
#ARG_CLS_BY_PYTYPE[False] = FalseArgument
ARG_CLS_BY_PYTYPE[None] = NoneArgument

class Address(StringArgument):
    def __new__(cls, value):
        if isinstance(value, list) or isinstance(value, tuple):
            value = '/'.join([v for v in value])
        return str.__new__(cls, value)
    @property
    def head(self):
        return self.split()[0]
    @property
    def tail(self):
        return self.split()[-1:][0]
    def split(self):
        l = super(Address, self).split('/')
        if len(l) and l[0] == '':
            l = l[1:]
        return l
    def as_root(self):
        return Address('/' + self)
    def append(self, other):
        if not isinstance(other, Address):
            other = Address(other)
        l = self.split() + other.split()
        if len(self) and self[0] == '/':
            l[0] = '/' + l[0]
        return Address(l)
    def append_right(self, other):
        if not isinstance(other, Address):
            other = Address(other)
        l = other.split() + self.split()
        return Address(l)
    def pop(self):
        sp = self.split()
        if not len(sp):
            return '', ''
        if len(sp) == 1:
            return sp[0], ''
        return sp[0], Address(sp[1:])

def build_argument(**kwargs):
    type_tag = kwargs.get('type_tag')
    data = kwargs.get('data')
    obj = kwargs.get('obj')
    cls = None
    if 'type_tag' in kwargs:
        cls = ARG_CLS_BY_TYPE_TAG[type_tag]
    elif 'obj' in kwargs:
        if cls is None:
            cls = ARG_CLS_BY_PYTYPE.get(type(obj))
        if cls is None:
            return False
        return cls(obj)
    else:
        return False
    arg, data = cls.from_binary(cls, data, type_tag=type_tag)
    return (arg, data)
    

def _find_pad_length(i):
    return i + (4 - (i % 4))
    
def _strip_padding(data):
    first_null = data.find('\0')
    padlen = _find_pad_length(first_null)
    return data[0:first_null], data[padlen:]
    
def parse_message(data, **kwargs):
    if not len(data):
        print 'NO DATA'
        return False
    client = kwargs.get('client')
    timestamp = kwargs.get('timestamp')
    if data[0] == '/':
        return Message(data=data, client=client, timestamp=timestamp)
    if len(data) > 7 and data[:7] == '#bundle':
        return Bundle(data=data, client=client, timestamp=timestamp)
    
if __name__ == '__main__':
#    msg1 = Message('a', 1, True, address='/blah/stuff/1')
#    msg2 = Message('b', 2, False, address='/blah/stuff/2')
#    #print msg1
#    #print msg2
#    
#    bundle = Bundle(msg1, msg2, timetag=2000.)
#    print bundle
#    bundle2 = parse_message(bundle.build_string())
#    print bundle2
#    print [m.get_arguments() for m in bundle2.get_messages()]
##    for obj in [True, False, None]:
##        arg = build_argument(obj=obj)
##        print arg
##        print arg == obj
##        print arg is obj
##        #print arg._pytype(arg)
    msg1 = Message(1, address='/blah')
    msg2 = Message('a', address='/stuff')
    bun1 = Bundle(msg1, timetag=10)
    bun2 = Bundle(msg2, bun1, timetag=20)
    bun3 = Bundle(bun2, timetag=10)
    bundles = bun3.split_bundles()
    print bundles
    print [str(b) for b in bundles.values()]
    
