

import sys
import os.path

if __name__ == '__main__':
    dirname = os.path.dirname(__file__)
    if dirname == '':
        dirname = os.getcwd()
        sys.path.append(dirname)
    i = sys.path.index(dirname)
    sys.path[i] = os.path.split(os.path.split(sys.path[i])[0])[0]
    print sys.path[i]

from Bases import BaseObject
from comm.CommDispatcher import CommDispatcherBase

class CommDispatcher(CommDispatcherBase):
    def __init__(self, **kwargs):
        super(CommDispatcher, self).__init__(**kwargs)
        d = self.GLOBAL_CONFIG.get('arg_parse_dict')
        if d is None:
            d = {}
            self.GLOBAL_CONFIG['arg_parse_dict'] = d
        d['debug_osc'] = True
        self.osc_io = self.build_io_module('osc')
    def do_connect(self):
        self.osc_io.do_connect()
    def shutdown(self):
        self.osc_io.shutdown()
    
class Main(BaseObject):
    def __init__(self, **kwargs):
        super(Main, self).__init__(**kwargs)
        self.GLOBAL_CONFIG['app_name'] = 'osc_terminal'
        
