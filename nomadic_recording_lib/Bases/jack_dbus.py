from BaseObject import BaseObject
import dbus

def _import_jack_control():
    import os.path
    import imp
    name = 'jack_control'
    path = '/usr/bin/'
    filename = os.path.join(path, name)
    desc = None
    for t in imp.get_suffixes():
        if t[0] == '.py':
            desc = t
            break
    if not desc:
        return
    try:
        file = open(filename, desc[1])
        m = imp.load_module(name, file, filename, desc)
        file.close()
        return m
    except:
        return
    
jack_control = _import_jack_control()

class JackDBus(BaseObject):
    def __init__(self, **kwargs):
        super(JackDBus, self).__init__(**kwargs)
        self.bus = dbus.SessionBus()
        self.controller = self.bus.get_object(jack_control.service_name, "/org/jackaudio/Controller")
        self.control_iface = dbus.Interface(self.controller, jack_control.control_interface_name)
        self.configure_iface = dbus.Interface(self.controller, jack_control.configure_interface_name)
        #print self.control_iface.IsStarted()
        
jdb = JackDBus()
