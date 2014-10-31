import SocketServer
import socket
import traceback
import code
import os.path
import sys
import tempfile

if __name__ == '__main__':
    dirname = os.path.dirname(__file__)
    if dirname == '':
        dirname = os.getcwd()
        sys.path.append(dirname)
    i = sys.path.index(dirname)
    sys.path[i] = os.path.split(os.path.split(sys.path[i])[0])[0]
    print sys.path[i]

from Bases import BaseObject, BaseThread
from comm.BaseIO import BaseIO



PORT = 54321

PID = os.getpid()

h, TMP_FILENAME = tempfile.mkstemp(suffix='-%s' % (PID), prefix='RemoteConsoleConf-')

def update_tempfile():
    lines = ['']
    lines.append('PORT = %s' % (PORT))
    lines.append('')
    s = '\n'.join(lines)
    f = open(TMP_FILENAME, 'w')
    f.write(s)
    f.close()
    
def delete_tempfile():
    if not os.path.exists(TMP_FILENAME):
        return
    os.remove(TMP_FILENAME)
    
def update_port(port):
    global PORT
    PORT = port
    update_tempfile()

class RemoteServer(BaseIO):
    def __init__(self, **kwargs):
        super(RemoteServer, self).__init__(**kwargs)
        self.locals = kwargs.get('locals')
        #self.interpreter = Interpreter(locals=self.locals, 
        #                               write_cb=self.on_interpreter_write)
        self.serve_thread = None
    def do_connect(self, **kwargs):
        self.do_disconnect()
        t = self.serve_thread = ServerThread(locals=self.locals)
        t.start()
        update_port(t.hostport)
        self.connected = True
    def do_disconnect(self, **kwargs):
        t = self.serve_thread
        if t is not None:
            t.stop(blocking=True)
            self.serve_thread = None
            delete_tempfile()
        self.connected = False
#    def on_interpreter_write(self, data):
#        t = self.serve_thread
#        if t is None:
#            return
#        s = t._server
#        if s is None:
#            return
#        h = s.current_handler
#        if h is None:
#            return
#        h.wfile.write(data)
class StdOut(object):
    def __init__(self, cb):
        self.callback = cb
    def open(self):
        sys.stdout = self
    def close(self):
        sys.stdout = sys.__stdout__
    def __enter__(self, *args):
        self.open()
    def __exit__(self, *args):
        self.close()
    def write(self, data):
        self.callback(data)
        
class Interpreter(code.InteractiveInterpreter):
    def __init__(self, **kwargs):
        _locals = kwargs.get('locals')
        self.write_cb = kwargs.get('write_cb')
        code.InteractiveInterpreter.__init__(self, _locals)
    def runsource(self, *args, **kwargs):
        stdout = StdOut(self.write)
        with stdout:
            code.InteractiveInterpreter.runsource(self, *args, **kwargs)
    def write(self, data):
        #print 'interpreter write: ', data
        cb = self.write_cb
        if cb is not None:
            cb(data)
        
class ServerListener(BaseThread):
    def __init__(self, **kwargs):
        super(ServerListener, self).__init__(**kwargs)
    
class RemoteHandler(SocketServer.BaseRequestHandler):
    def setup(self):
        self.interpreter = Interpreter(locals=self.server.locals, 
                                       write_cb=self.on_interpreter_write)
        #SocketServer.StreamRequestHandler.setup(self)
    def handle(self):
        print 'handling..'
        #data = self.rfile.read()
        data = self.request.recv(4096)
        #print 'received: ', data
        self.process_line(data)
    def old_handle(self):
        def get_line():
            return self.rfile.readline().strip()
        #self.server.current_handler = self
        line = get_line()
        while len(line):
            self.process_line(line)
            line = get_line()
    def process_line(self, line):
#        cobj = None
#        try:
#            cobj = code.compile_source(line)
#        except SyntaxError:
#            pass
#        if cobj is None:
#            return
#        #try:
#        #    exec cobj in self.server.locals
        print 'running source: ', line
        self.interpreter.runsource(line)
    def on_interpreter_write(self, data):
        #if self.wfile.closed:
        #    return
        #print 'sending response: ', data
        #self.wfile.write(data)
        self.request.sendall(data)
    
class Server(SocketServer.TCPServer):
    def __init__(self, **kwargs):
        keys = ['server_address', 'RequestHandlerClass', 'bind_and_activate']
        skwargs = dict(zip(keys, [kwargs.get(key) for key in keys]))
        SocketServer.TCPServer.__init__(self, **skwargs)
        self.locals = kwargs.get('locals')
        
class ServerThread(BaseThread):
    _server_conf_defaults = dict(server_address=('127.0.0.1', PORT), 
                                 RequestHandlerClass=RemoteHandler, 
                                 bind_and_activate=True)
    def __init__(self, **kwargs):
        super(ServerThread, self).__init__(**kwargs)
        self.server_config = kwargs.get('server_config', {})
        self.locals = kwargs.get('locals')
        self._server = None
    @property
    def server_address(self):
        return self.build_server_kwargs()['server_address']
    @server_address.setter
    def server_address(self, value):
        self.server_config['server_address'] = value
    @property
    def hostaddr(self):
        return self.server_address[0]
    @hostaddr.setter
    def hostaddr(self, value):
        port = self.hostport
        self.server_address = (value, port)
    @property
    def hostport(self):
        return self.server_address[1]
    @hostport.setter
    def hostport(self, value):
        addr = self.hostaddr
        self.server_address = (addr, value)
    def build_server_kwargs(self, **kwargs):
        skwargs = self.server_config.copy()
        for key, default in self._server_conf_defaults.iteritems():
            val = kwargs.get(key, skwargs.get(key, default))
            skwargs[key] = val
        return skwargs
    def build_server(self, **kwargs):
        skwargs = self.build_server_kwargs(**kwargs)
        skwargs['locals'] = self.locals
        return Server(**skwargs)
    def run(self):
        self._running = True
        
        #s.interpreter = self.interpreter
        #s.current_handler = None
        count = 0
        maxtries = 100
        while count <= maxtries:
            try:
                s = self._server = self.build_server()
                s.serve_forever()
                break
            except socket.error:
                self.hostport = self.hostport + 1
            count += 1
        self._running = False
        self._stopped = True
    def stop(self, **kwargs):
        s = self._server
        if s is not None:
            s.shutdown()
        super(ServerThread, self).stop(**kwargs)

def test():
    class A(BaseObject):
        _Properties = {'name':dict(default=''), 
                       'state':dict(default=False)}
        _ChildGroups = {'children':{}}
    a = A()
    print a
    serv = RemoteServer(locals=locals())
    print serv
    serv.do_connect()
    print serv, 'connected'
    
if __name__ == '__main__':
    import sys, time
    print 'test start'
    test()
    while True:
        try:
            time.sleep(1.)
        except KeyboardInterrupt:
            sys.exit(0)
        
