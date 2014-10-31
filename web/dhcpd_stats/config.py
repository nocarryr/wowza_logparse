
class Config(object):
    dhcpd_conf = '/etc/dhcp/dhcpd.conf'
    dhcpd_leases = '/var/lib/dhcp/dhcpd.leases'
    def __init__(self, **kwargs):
        for k, v in kwargs.iteritems():
            setattr(self, k, v)
    
