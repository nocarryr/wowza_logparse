from parser import LeaseConf

NETWORKS = []
LEASES = []

class IPAddress(object):
    def __init__(self, address_str):
        self.address_str = address_str
        self.quad = [int(q) for q in address_str.split('.')]
    def __cmp__(self, other):
        if isinstance(other, basestring):
            other = IPAddress(other)
        for i, q in enumerate(self.quad):
            otherq = other.quad[i]
            if q > otherq:
                return 1
            if q < otherq:
                return -1
            if i == 3:
                ## if one of the addresses ends with a "0", then it matches as a wildcard
                if 0 in [q, otherq]:
                    return 0
        return 0
    def __str__(self):
        return self.address_str
        
class NetworkBase(object):
    def __init__(self, **kwargs):
        self.parent = kwargs.get('parent')
        self.conf_object = kwargs.get('conf_object')
    def add_child_from_conf(self, cls, conf_obj, **kwargs):
        kwargs['conf_object'] = conf_obj
        kwargs['parent'] = self
        return cls(**kwargs)
        
class Network(NetworkBase):
    def __init__(self, **kwargs):
        super(Network, self).__init__(**kwargs)
        self.subnets = {}
        for k, v in self.conf_object.subnets.iteritems():
            subnet = self.add_child_from_conf(Subnet, v)
            self.subnets[subnet.address] = subnet
    @property
    def name(self):
        return self.conf_object.name
    def match_address(self, address):
        if isinstance(address, basestring):
            address = IPAddress(address)
        for subnet in self.subnets.itervalues():
            if subnet.match_address(address):
                return True
        return False
    def __repr__(self):
        return 'Network: %s' % (self)
    def __str__(self):
        return self.name
        
class Subnet(NetworkBase):
    def __init__(self, **kwargs):
        super(Subnet, self).__init__(**kwargs)
        self.address = IPAddress(self.conf_object.address)
        self.ranges = []
        for pool in self.conf_object.pools:
            for r in pool.ranges:
                robj = self.add_child_from_conf(Range, r)
                self.ranges.append(robj)
    def match_address(self, address):
        if isinstance(address, basestring):
            address = IPAddress(address)
        for r in self.ranges:
            if r.match_address(address):
                return True
        return False
    def __repr__(self):
        return 'Subnet %s' % (self)
    def __str__(self):
        return str(self.address)
        
class Range(NetworkBase):
    def __init__(self, **kwargs):
        super(Range, self).__init__(**kwargs)
        self.start = IPAddress(self.conf_object.start)
        self.end = IPAddress(self.conf_object.end)
    def match_address(self, address):
        if isinstance(address, basestring):
            address = IPAddress(address)
        if address < self.start:
            return False
        if address > self.end:
            return False
        return True
    def __repr__(self):
        return 'Range: %s' % (self)
    def __str__(self):
        return '%s - %s' % (self.start, self.end)
    
class Lease(LeaseConf):
    def __init__(self, **kwargs):
        super(Lease, self).__init__(**kwargs)
        self.address = IPAddress(self.address)
        self.network_obj = kwargs.get('network_obj')
        if self.network_obj is None:
            self.network_obj = self.find_network()
    @classmethod
    def from_conf(cls, conf_obj, **kwargs):
        new_kwargs = kwargs.copy()
        for attr in cls._conf_attrs:
            new_kwargs[attr] = getattr(conf_obj, attr)
        return cls(**new_kwargs)
    def find_network(self):
        global NETWORKS
        for n in NETWORKS:
            if n.match_address(self.address):
                return n
        
def build_networks(conf_networks):
    global NETWORKS
    for cnet in conf_networks:
        NETWORKS.append(Network(conf_object=cnet))
    return NETWORKS
def build_leases(conf_leases):
    global LEASES
    for clease in conf_leases:
        LEASES.append(Lease.from_conf(clease))
    return LEASES
