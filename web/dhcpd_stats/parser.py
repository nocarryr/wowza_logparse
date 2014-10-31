import datetime

PARSED_NETWORKS = []
PARSED_LEASES = []

class Text(str):
    @property
    def lines(self):
        v = getattr(self, '_lines', None)
        if v is None:
            v = self._lines = self.splitlines()
        return v
    def walk_brackets(self):
        level = 0
        for i, line in enumerate(self.lines):
            if '{' in line:
                level += 1
            if '}' in line:
                level -= 1
            yield level, i, line
            
class NestedBracket(object):
    def __init__(self, **kwargs):
        self.parent = kwargs.get('parent')
        start_line = kwargs.get('start_line')
        self.start_line_num = kwargs.get('start_line_num', 0)
        self.end_line_num = None
        self.recursion_level = kwargs.get('recursion_level', 0)
        self._parse_iter = kwargs.get('parse_iter')
        self._text = kwargs.get('text')
        self.children = []
        self.lines = []
        if start_line is not None:
            self.lines.append(start_line)
        self.do_parse()
    @property
    def parse_iter(self):
        i = self._parse_iter
        if i is None:
            if self.parent is None:
                i = self.text.walk_brackets()
            else:
                i = self.parent.parse_iter
            self._parse_iter = i
        return i
    @property
    def text(self):
        t = self._text
        if t is None:
            t = self.parent.text
        elif not isinstance(t, Text):
            t = self._text = Text(t)
        return t
    @property
    def contents(self):
        return '\n'.join(self.lines)
    def do_parse(self):
        parse_iter = self.parse_iter
        level_increased = False
        my_level = self.recursion_level
        while True:
            try:
                level, i, line = parse_iter.next()
            except StopIteration:
                self.end_line_num = i
                break
            if level > my_level:
                child = NestedBracket(parent=self, 
                                      start_line=line, 
                                      start_line_num=i, 
                                      recursion_level=level, 
                                      parse_iter = parse_iter)
                self.children.append(child)
                level_increased = True
            elif level < my_level:
                self.lines.append(line)
                self.end_line_num = i
                break
            else:
                self.lines.append(line)
    def __repr__(self):
        return 'RecursionBracket: %s' % (self)
    def __str__(self):
        return 'line %03d, level %03d' % (self.start_line_num, self.recursion_level)
        
class ParseBase(object):
    def __init__(self, **kwargs):
        self.parent = kwargs.get('parent')
        self.bracket = kwargs.get('bracket')
        from_parse = kwargs.get('from_parse')
        if from_parse:
            self.parse_start_line(self.start_line)
    @property
    def start_line(self):
        return self.bracket.lines[0].strip()
    def parse_children(self, cls):
        ckwargs = {'parent':self}
        def walk_children(bracket):
            is_first = True
            for schild in bracket.children:
                if is_first:
                    to_yield = schild
                    is_first = False
                elif len(schild.children):
                    for gchild in walk_children(schild):
                        to_yield = gchild
                else:
                    to_yield = None
                if to_yield is None:
                    break
                yield to_yield
        for pchild in walk_children(self.bracket):
            ckwargs['bracket'] = pchild
            chobj = cls._parse(**ckwargs)
            if chobj is False:
                continue
            yield chobj
    @classmethod
    def _parse(cls, **kwargs):
        bracket = kwargs.get('bracket')
        start_line = bracket.lines[0].strip()
        if cls.conf_keyword not in start_line:
            return False
        objkwargs = kwargs.copy()
        objkwargs['start_line'] = start_line
        objkwargs['from_parse'] = True
        return cls(**objkwargs)
    def parse_start_line(self, line):
        pass
        
class NetworkConf(ParseBase):
    conf_keyword = 'shared-network'
    def __init__(self, **kwargs):
        self.name = kwargs.get('name')   
        super(NetworkConf, self).__init__(**kwargs)
        self.subnets = {}
        if self.bracket is not None:
            for subnet in self.parse_children(SubnetConf):
                self.subnets[subnet.address] = subnet
    def parse_start_line(self, line):
        line = line.split(' ')
        self.name = line[1]
    def get_ranges(self):
        for subnet in self.subnets.itervalues():
            for r in subnet.get_ranges():
                yield r
    def serialize(self):
        d = {'name':self.name, 'subnets':{}}
        for k, v in self.subnets.iteritems():
            d['subnets'][k] = v.serialize()
        return d
    def __repr__(self):
        return 'NetworkConf: %s' % (self)
    def __str__(self):
        return self.name
    
class SubnetConf(ParseBase):
    conf_keyword = 'subnet'
    def __init__(self, **kwargs):
        self.address = kwargs.get('address')
        self.netmask = kwargs.get('netmask')
        super(SubnetConf, self).__init__(**kwargs)
        if self.parent is None:
            self.parent = NetworkConf(name='unknown')
            self.parent.subnets[self.address] = self
        self.pools = []
        for p in self.parse_children(PoolConf):
            self.pools.append(p)
    def parse_start_line(self, line):
        line = line.split(' ')
        self.address = line[1]
        self.netmask = line[3]
    def get_ranges(self):
        for p in self.pools:
            for r in p.ranges:
                yield r
    def serialize(self):
        d = {'address':self.address, 'netmask':self.netmask, 'pools':[]}
        for v in self.pools:
            d['pools'].append(v.serialize())
        return d
    def __repr__(self):
        return 'SubnetConf: %s' % (self)
    def __str__(self):
        return self.address
    
class PoolConf(ParseBase):
    conf_keyword = 'pool'
    def __init__(self, **kwargs):
        self.ranges = []
        super(PoolConf, self).__init__(**kwargs)
        if self.bracket is not None:
            for r in self.parse_children(RangeConf):
                self.ranges.append(r)
    def serialize(self):
        d = {'ranges':[]}
        for r in self.ranges:
            d['ranges'].append(r.serialize())
        return d
            
class RangeConf(ParseBase):
    conf_keyword = 'range'
    def __init__(self, **kwargs):
        self.start = kwargs.get('start')
        self.end = kwargs.get('end')
        self.id = str(self)
        super(RangeConf, self).__init__(**kwargs)
    def parse_start_line(self, line):
        line = line.strip().strip(';').split(' ')
        self.start = line[1]
        self.end = line[2]
    def serialize(self):
        return {'start':self.start, 'end':self.end}
    def __repr__(self):
        return 'RangeConf: %s' % (self)
    def __str__(self):
        return '%s - %s' % (self.start, self.end)
        
def parse_conf(**kwargs):
    global PARSED_NETWORKS
    to_parse = kwargs.get('to_parse')
    filename = kwargs.get('filename')
    return_parsed = kwargs.get('return_parsed')
    return_enclosures = kwargs.get('return_enclosures')
    if to_parse is None:
        with open(filename, 'r') as f:
            to_parse = f.read()
    
    root_bracket = NestedBracket(text=to_parse)
    for bracket in root_bracket.children:
        if 'shared-network' in bracket.lines[0]:
            nobj = NetworkConf._parse(bracket=bracket)
        elif 'subnet' in bracket.lines[0]:
            sobj = SubnetConf._parse(bracket=bracket)
            nobj = sobj.parent
        else:
            nobj = None
        if nobj is not None:
            PARSED_NETWORKS.append(nobj)
    if return_parsed:
        return PARSED_NETWORKS, root_bracket
    return PARSED_NETWORKS
    
def parse_dt(dtstr):
    fmt_str = '%w %Y/%m/%d %H:%M:%S'
    if dtstr == 'never':
        return None
    return datetime.datetime.strptime(dtstr, fmt_str)
    
class LeaseConf(object):
    _conf_attrs = ['address', 'start_time', 'end_time', 
                   'binding_state', 'mac_address', 'uid']
    def __init__(self, **kwargs):
        self.address = kwargs.get('address')
        self.start_time = kwargs.get('start_time')
        self.end_time = kwargs.get('end_time')
        self.binding_state = kwargs.get('binding_state')
        self.mac_address = kwargs.get('mac_address')
        self.uid = kwargs.get('uid')
    @classmethod
    def _parse(cls, to_parse, **kwargs):
        if isinstance(to_parse, basestring):
            to_parse = to_parse.splitlines();
        new_kwargs = kwargs.copy()
        parse_dict = dict(zip([line.strip().split(' ')[0] for line in to_parse], 
                              [line.strip().rstrip(';').split(' ')[1:] for line in to_parse]))
        new_kwargs['address'] = parse_dict['lease'][0]
        new_kwargs['start_time'] = parse_dt(' '.join(parse_dict['starts']))
        new_kwargs['end_time'] = parse_dt(' '.join(parse_dict['ends']))
        new_kwargs['binding_state'] = parse_dict['binding'][1]
        new_kwargs['mac_address'] = parse_dict.get('hardware', [None, None])[1]
        new_kwargs['uid'] = parse_dict.get('uid', [None])[0]
        return cls(**new_kwargs)
    def __repr__(self):
        return '%s: %s' % (self.__class__.__name__, self)
    def __str__(self):
        return str(self.address)
    
def parse_leases(**kwargs):
    global PARSED_LEASES
    to_parse = kwargs.get('to_parse')
    filename = kwargs.get('filename')
    if to_parse is None:
        with open(filename, 'r') as f:
            to_parse = f.read()
    if isinstance(to_parse, basestring):
        to_parse = to_parse.splitlines()
    def iter_lines(start):
        for i in range(start, len(to_parse)):
            yield i, to_parse[i]
    def find_lease_lines(start_line=None):
        if start_line is None:
            start_line = 0
        lease_lines = None
        for i, line in iter_lines(start_line):
            if 'lease' in line and '{' in line:
                lease_lines = []
                lease_lines.append(line)
            elif '}' in line:
                if lease_lines is not None:
                    yield lease_lines
                lease_lines = None
            elif lease_lines is not None:
                lease_lines.append(line)
    for lines in find_lease_lines():
        obj = LeaseConf._parse(lines)
        PARSED_LEASES.append(obj)
    return PARSED_LEASES
