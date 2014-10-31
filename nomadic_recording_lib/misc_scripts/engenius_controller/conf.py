from UserDict import UserDict
import json
from cli_commands import BaseCommand

def iterbases(obj, lastclass='object'):
    if type(lastclass) == type:
        lastclass = lastclass.__name__
    if type(obj) == type:
        cls = obj
    else:
        cls = obj.__class__
    while cls.__name__ != lastclass:
        yield cls
        try:
            cls = cls.__bases__[0]
        except IndexError:
            break
        
class ConfVar(UserDict):
    def __init__(self, init_dict=None):
        if init_dict is None:
            init_dict = {}
        UserDict.__init__(self, init_dict)
        if 'default' not in self:
            self['default'] = None
        if 'value' not in self:
            self['value'] = None
    @property
    def name(self):
        return self.get('name')
    @name.setter
    def name(self, value):
        if self.name == value:
            return
        self['name'] = value
    @property
    def default(self):
        return self.get('default')
    @default.setter
    def default(self, value):
        if self.default == value:
            return
        self['default'] = value
    @property
    def value(self):
        return self.get('value', self.get('default'))
    @value.setter
    def value(self, value):
        if self.value == value:
            return
        self['value'] = value
    
class ConfBase(UserDict):
    child_class = None
    def __init__(self, init_dict=None, **kwargs):
        UserDict.__init__(self)
        self.child_classes = {}
        self.conf_vars = {}
        for cls in iterbases(self, ConfBase):
            if hasattr(cls, '_child_classes'):
                for key, val in cls._child_classes.iteritems():
                    self.child_classes[key] = val
            if hasattr(cls, '_conf_vars'):
                for conf_var in cls._conf_vars:
                    if isinstance(conf_var, basestring):
                        conf_var = {'name':conf_var}
                    conf_var = ConfVar(conf_var)
                    self.conf_vars[conf_var.name] = conf_var
        json_str = kwargs.get('json_str')
        if json_str is not None:
            del kwargs['json_str']
            init_dict = json.loads(json_str)
        if init_dict is None:
            init_dict = {}
        else:
            print init_dict
            print repr(init_dict)
        for key, val in init_dict.iteritems():
            self[key] = val
        for key, val in kwargs.iteritems():
            self[key] = val
        for key, val in self.child_classes.iteritems():
            if key not in self:
                self[key] = val()
        self.do_init(**kwargs)
    def do_init(self, **kwargs):
        pass
    def __setitem__(self, key, item):
        child_cls = self.child_classes.get(key)
        var_obj = self.conf_vars.get(key)
        if child_cls is not None:
            if not isinstance(item, child_cls):
                item = child_cls(item)
        elif self.child_class is not None:
            if not isinstance(item, self.child_class):
                item = self.child_class(item)
        elif var_obj is not None:
            var_obj.value = item
            return
        UserDict.__setitem__(self, key, item)
    def __getitem__(self, key):
        var_obj = self.conf_vars.get(key)
        if var_obj is not None:
            return var_obj.value
        return UserDict.__getitem__(self, key)
    def to_json(self):
        return json.dumps(self)
        
class CommandBase(ConfBase):
    def __init__(self, init_dict=None, **kwargs):
        self.command_map = []
        ConfBase.__init__(self, init_dict, **kwargs)
    def append(self, item):
        if isinstance(item, basestring):
            item = {'command':item}
        key = item['command']
        self[key] = item
        item = self[key]
        self.command_map.append(item)
        return item
class Commands(CommandBase):
    pass
class Command(ConfBase):
    _conf_vars = ['command', 'exit_command', 'prompt']
    #_child_classes = {'children':Commands}
    

Commands.child_class = Command
Command.child_class = Command

class Auth(ConfBase):
    _conf_vars = [
        {'name':'username', 'default':'admin'}, 
        {'name':'password', 'default':'admin'}, 
    ]

class TelnetConf(ConfBase):
    _conf_vars = ['host']
    
class APConf(ConfBase):
    _conf_vars = ['model']
    _child_classes = {'auth':Auth, 'telnet':TelnetConf, 'commands':Commands}
    
class RootConf(ConfBase):
    _conf_vars = {'name':'threaded', 'default':True}
    _child_classes = {'access_points':APConf}
    
class EAP350(APConf):
    def do_init(self, **kwargs):
        self['model'] = 'eap350'
class UptimeCommand(BaseCommand):
    command = 'sysuptime'
    def parse_response_data(self, msg):
        s = msg.split('up ')[1].split(' days')[0]
        return int(s)
#class EAP350GetStatBase(EAP350):
#    def do_init(self, **kwrags):
#        cmds = self['commands']
#        stat = cmds.append({'command':'stat'})
#        info = stat.append({'command':'info'})
class EAP350GetUptime(EAP350):
    def do_init(self, **kwrags):
        cmds = self['commands']
        stat = cmds.append({'command':'stat'})
        info = stat.append({'command':'info'})
        info.append({'cls':UptimeCommand, 
                     'response_data_callback':self.on_uptime_response})
#class EAP350GetRFInfo(EAP350):
#    def do_init(self, **kwargs):
#        cmds = self['commands']
#        
    
def parse_conf(filename):
    with open(filename, 'r') as f:
        s = f.read()
    c = RootConf(json_str=s)
    return c
