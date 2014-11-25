#! /usr/bin/env python

import os
import argparse

KNOWN_HOSTS_FILENAME = '~/.ssh/known_hosts'
class KnownHostsFile(object):
    def __init__(self, filename=None):
        if filename is None:
            filename = KNOWN_HOSTS_FILENAME
        self.filename = os.path.expanduser(filename)
        self.file = None
        self.hosts = []
        self.lines_by_host = {}
    def __enter__(self):
        self.file = open(self.filename, self.filemode)
    def __exit__(self, *args, **kwargs):
        if self.file is not None:
            self.file.close()
        self.file = None
    def read(self):
        self.filemode = 'r'
        with self:
            s = self.file.read()
        return s
    def write(self):
        lines = [self.lines_by_host[host] for host in self.hosts]
        self.filemode = 'w'
        with self:
            self.file.write('\n'.join(lines))
    def parse(self):
        s = self.read()
        for line in s.splitlines():
            line = line.strip('\n')
            parts = line.split(' ')
            if len(parts) < 2:
                continue
            host = parts[0]
            self.hosts.append(host)
            self.lines_by_host[host] = line
            
def remove_host(host, filename=None):
    f = KnownHostsFile(filename)
    f.parse()
    if host not in f.hosts:
        return False
    f.hosts.remove(host)
    f.write()
    return True
    
def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        '-f', 
        dest='filename', 
        help='known_hosts filename, default is %s' % (KNOWN_HOSTS_FILENAME)
    )
    p.add_argument('host', help='hostname to remove')
    args, remaining = p.parse_known_args()
    o = vars(args)
    r = remove_host(o['host'], o['filename'])
    if r:
        print '%s removed' % (o['host'])
    else:
        print '%s not found in known_hosts' % (o['host'])
    
if __name__ == '__main__':
    main()
    
