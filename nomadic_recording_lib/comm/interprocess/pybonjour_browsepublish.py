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
# pybonjour_browsepublish.py
# Copyright (c) 2011 Matthew Reid

import threading
import socket
import select
import pybonjour
from Bases import BaseObject, BaseThread

class Publisher(BaseObject):
    def __init__(self, **kwargs):
        self.register_sdRef = None
        self.published = False
        self.republish_timer = None
        super(Publisher, self).__init__(**kwargs)
        self._text = {}
        kwargs.setdefault('stype', '_http._tcp')
        kwargs.setdefault('domain', '')
        kwargs.setdefault('host', '')
        kwargs.setdefault('text', '')
        self.update(**kwargs)
        
    def update(self, **kwargs):
        self.name = kwargs.get('name')
        self.stype = kwargs.get('stype')
        self.regtype = self.stype
        self.domain = kwargs.get('domain', '.'.join([socket.gethostname(), 'local']))
        self.host = kwargs.get('host')
        self.port = kwargs.get('port')
        self.text = kwargs.get('text', {})
        if self.published:
            self.unpublish()
            if self.republish_timer is not None:
                self.republish_timer.cancel()
            self.republish_timer = threading.Timer(1., self.publish)
            self.republish_timer.start()
        
    @property
    def text(self):
        return pybonjour.TXTRecord(items=self._text)
    @text.setter
    def text(self, value):
        if type(value) == dict:
            self._text.update(value)
        
    def publish(self):
        #keys = ('name', 'regtype', 'port', 'text')
        d = dict(name='name', regtype='stype', port='port', txtRecord='text', callBack='on_register')
        kwargs = {}
        for key, val in d.iteritems():
            kwargs[key] = getattr(self, val)
        #kwargs = dict(zip(keys, [getattr(self, key) for key in keys]))
        #kwargs['callBack'] = self.on_register
        #print kwargs
        sdRef = pybonjour.DNSServiceRegister(**kwargs)
        self.register_sdRef = sdRef
        self.register_thread = ProcessThread(sdRef=sdRef, _name='register_%s' % (kwargs['name']))
        self.register_thread.start()

    def unpublish(self, blocking=False):
        if self.register_sdRef:
            self.register_sdRef.close()
            self.register_sdRef = None
        if self.register_thread._running:
            self.register_thread.stop(blocking=blocking)
        self.published = False
        
    def on_register(self, sdRef, flags, errorCode, name, regtype, domain):
        if errorCode == pybonjour.kDNSServiceErr_NoError:
            self.LOG.info('Registered service', 'name=%s, regtype=%s, domain=%s' % (name, regtype, domain))
            
            #self.register_thread.running = False
            self.register_thread.stop()
            self.published = True
            return
        #print 'on_register: ', args

class ProcessThread(BaseThread):
    def __init__(self, **kwargs):
        self._name = kwargs.get('_name')
        self.sdRef = kwargs.get('sdRef')
        self.close_when_finished = kwargs.get('close_when_finished', False)
        kwargs['thread_id'] = self._name
        kwargs['disable_threaded_call_waits'] = True
        super(ProcessThread, self).__init__(**kwargs)
        
    def _thread_loop_iteration(self):
        if self.sdRef is None:
            return
        if not self.sdRef._valid():
            return
        ready = select.select([self.sdRef], [], [], 1.0)
        if self.sdRef not in ready[0]:
            return
        try:
            pybonjour.DNSServiceProcessResult(self.sdRef)
        except:
            #print 'value error?'
            self.stop()
            
    def stop(self, **kwargs):
        if self.sdRef is not None:
            if self.close_when_finished:
                self.sdRef.close()
            self.sdRef = None
        super(ProcessThread, self).stop(**kwargs)
        
    def old_run(self):
        self.running = True
        #print 'process thread start'
        while self.running:
            ready = select.select([self.sdRef], [], [], 1.0)
            if self.sdRef in ready[0]:
                try:
                    pybonjour.DNSServiceProcessResult(self.sdRef)
                except:
                    #print 'value error?'
                    self.running = False
                    self.sdRef.close()
        if self.close_when_finished:
            self.sdRef.close()
        delattr(self, 'sdRef')

class Browser(BaseObject):
    def __init__(self, **kwargs):
        super(Browser, self).__init__(**kwargs)
        self.connected = False
        self.sdRefs = {}
        self.process_threads = {}
        self.services = {}
        self.register_signal('new_host', 'remove_host')
        self.stype = kwargs.get('stype')
        self.id = kwargs.get('id', self.stype)
        self.domain = kwargs.get('domain')
        self.serv_info_map = {2:'name', 3:'stype', 4:'domain', 5:'hostname', 7:'address', 8:'port', 9:'text'}
        
    def do_connect(self):
        self.start_browser()
        self.connected = True
        
    def do_disconnect(self, blocking=False):
        #self.browse_thread.running = False
        self.browse_thread.stop(blocking=blocking)
        for service in self.services.itervalues():
            service.stop(blocking=blocking)
            #if service.resolve_thread:
            #    service.resolve_thread.running = False
        self.connected = False
        
    def start_browser(self):
        self.browse_sdRef = pybonjour.DNSServiceBrowse(regtype=self.stype, callBack=self.on_browse_started)
        self.browse_thread = ProcessThread(sdRef=self.browse_sdRef, close_when_finished=True, _name='browse_%s' % (self.stype))
        self.browse_thread.start()
        
    def on_browse_started(self, sdRef, flags, interfaceIndex, 
                          errorCode, serviceName, regtype, replyDomain):
        if errorCode != pybonjour.kDNSServiceErr_NoError:
            return

        if not (flags & pybonjour.kDNSServiceFlagsAdd):
            service = self.services.get(serviceName)
            if service:
                self.emit('remove_host', data=service.hostdata)
                del self.services[serviceName]
            return
            
        if serviceName in self.services:
            return
        
        d = dict(name=str(serviceName), stype=str(regtype), domain=str(replyDomain), 
                 interfaceIndex=interfaceIndex)
        service = Service(**d)
        service.connect('resolved', self.on_service_resolved)
        self.services.update({service.name:service})
        service.resolve()
        
    def on_service_resolved(self, **kwargs):
        service = kwargs.get('service')
        self.emit('new_host', data=service.hostdata)

class Service(BaseObject):
    def __init__(self, **kwargs):
        self.resolve_thread = None
        super(Service, self).__init__(**kwargs)
        self.register_signal('resolved')
        self.resolved = False
        self.name = kwargs.get('name')
        self.stype = kwargs.get('stype')
        self.domain = kwargs.get('domain')
        self.hostname = None
        self.address = None
        self.port = None
        self.text = None
        self._interfaceIndex = kwargs.get('interfaceIndex')
        #self.resolve()
    @property
    def hostdata(self):
        keys = ['name', 'stype', 'hostname', 'address', 'port', 'text', 'domain']
        d = dict(zip(keys, [getattr(self, key) for key in keys]))
        for key in ['stype', 'hostname', 'domain']:
            if d[key] is not None:
                d[key] = d[key][:-1]
        return d
    def resolve(self):
        keys = ['_interfaceIndex', 'name', 'stype', 'domain']
        args = [0] + [getattr(self, key) for key in keys]
        args.append(self.on_resolve)
        self.resolve_sdRef = pybonjour.DNSServiceResolve(*args)
        self.resolve_thread = ProcessThread(sdRef=self.resolve_sdRef, close_when_finished=True, _name='resolve_%s' % (self.name))
        self.resolve_thread.start()
    def stop(self, blocking=False):
        if self.resolve_thread._running:
            self.resolve_thread.stop(blocking=blocking)
    def on_resolve(self, sdRef, flags, interfaceIndex, 
                   errorCode, fullname, hosttarget, port, txtRecord):
        if errorCode != pybonjour.kDNSServiceErr_NoError:
            return
        hosttarget = str(hosttarget)
        self.hostname = '.'.join(hosttarget.split('.'))
        self.address = socket.gethostbyname(self.hostname)
        self.port = port
        txt = pybonjour.TXTRecord.parse(txtRecord)
        self.text = {}
        for key, val in txt:
            self.text[key] = val
        
        #self.domain = hosttarget.split('.')
        #self.resolve_thread.running = False
        self.resolve_thread.stop()
        self.resolved = True
        self.emit('resolved', service=self)
        

def convert_hex_chrs(string):
    if '\\' in string:
        l = []
        for i, s in enumerate(string.split('\\')):
            if i == 0:
                l.append(s)
            else:
                c = chr(int(s[:3]))
                new_s = c + s[3:]
                l.append(new_s)
        string = ''.join(l)
    return string


