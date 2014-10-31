from misc import iterbases

class ByteBase(object):
    def __init__(self, value=None, base_value=None, standard='iec'):
        self._value = None
        self._base_value = None
        self.standard = standard
        if value is not None:
            self._value = float(value)
        elif base_value is not None:
            self.base_value = base_value
        else:
            self._value = 0.
    @property
    def value(self):
        return self._value
    @value.setter
    def value(self, value):
        value = float(value)
        if value == self._value:
            return
        self._value = value
        self._base_value = None
    @property
    def base_value(self):
        v = self._base_value
        if v is None:
            v = self._base_value = self.calc_to_base_value()
        return v
    @base_value.setter
    def base_value(self, value):
        value = float(value)
        if self._base_value == value:
            return
        v = self.calc_from_base_value(value)
        self._value = v
    def calc_to_base_value(self):
        v = self.value
        attr = '_'.join([self.standard, 'multiplier'])
        default_m = getattr(self, attr)
        for cls in iterbases(self, 'Byte'):
            m = getattr(cls, attr, default_m)
            v *= m
        return v
    def calc_from_base_value(self, value):
        attr = '_'.join([self.standard, 'multiplier'])
        default_m = getattr(self, attr)
        bases = []
        for cls in iterbases(self, 'Byte'):
            bases.append(cls)
        for cls in reversed(bases):
            m = getattr(cls, attr, default_m)
            value /= m
        return value
    def to_other(self, identifier):
        cls = BYTE_CLASSES.get(identifier)
        return cls(base_value=self.base_value)
    def __cmp__(self, other):
        return cmp(self.base_value, other.base_value)
    def __add__(self, other):
        base_v = self.base_value + other.base_value
        v = self.calc_from_base_value(base_v)
        return self.__class__(v, self.standard)
    def __sub__(self, other):
        base_v = self.base_value - other.base_value
        v = self.calc_from_base_value(base_v)
        return self.__class__(v, self.standard)
    def __mul__(self, other):
        base_v = self.base_value * other.base_value
        v = self.calc_from_base_value(base_v)
        return self.__class__(v, self.standard)
    def __div__(self, other):
        base_v = self.base_value / other.base_value
        v = self.calc_from_base_value(base_v)
        return self.__class__(v, self.standard)
    def __iadd__(self, other):
        base_v = self.base_value + other.base_value
        self.base_value = base_v
        return self
    def __isub__(self, other):
        base_v = self.base_value - other.base_value
        self.base_value = base_v
        return self
    def __imul__(self, other):
        base_v = self.base_value * other.base_value
        self.base_value = base_v
        return self
    def __idiv__(self, other):
        base_v = self.base_value / other.base_value
        self.base_value = base_v
        return self
    def __str__(self):
        return '%s %s' % (self.value, self.identifier)
class Byte(ByteBase):
    si_multiplier = 1
    iec_multiplier = 1
    identifier = 'B'
class KiloByte(Byte):
    si_multiplier = 1000
    iec_multiplier = 1024
    identifier = 'KB'
class MegaByte(KiloByte):
    identifier = 'MB'
class GigaByte(MegaByte):
    identifier = 'GB'
class TeraByte(GigaByte):
    identifier = 'TB'
class PetaByte(TeraByte):
    identifier = 'PB'
    
BYTE_CLASSES = {}
def build_class_dict():
    global BYTE_CLASSES
    default_cls = [Byte, KiloByte, MegaByte, GigaByte, TeraByte, PetaByte]
    for cls in default_cls:
        key = cls.identifier
        if key in BYTE_CLASSES:
            continue
        BYTE_CLASSES[key] = cls
build_class_dict()
    
def parse_str(s):
    if s.isdigit():
        parsed_cls = Byte
    else:
        parsed_cls = None
        for key, cls in BYTE_CLASSES.iteritems():
            if key == 'B':
                continue
            if key in s.upper():
                s = s.upper().split(key)[0]
                parsed_cls = cls
                break
        if parsed_cls is None and 'B' in s.upper():
            parsed_cls = Byte
    if parsed_cls is None:
        return False
    return parsed_cls(s)
