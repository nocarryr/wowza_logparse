import threading


class CLICommandError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)
class CLICommandNoResponseError(CLICommandError):
    pass
class CLICommandInvalidResponseError(CLICommandError):
    pass
    
class CommandContext(object):
    def __init__(self, cmd_obj):
        self.command_obj = cmd_obj
        self.event = threading.Event()
        self.complete = False
    @property
    def active(self):
        return self.event.is_set()
    def __enter__(self):
        self.event.set()
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.complete = True
        self.event.clear()

class BaseCommand(object):
    _command_classes = {}
    def __init__(self, **kwargs):
        '''
            command: (str) command to transmit
            prompt: (str) required for the root command (model string ending with ">")
        '''
        command = kwargs.get('command', getattr(self, 'command', None))
        self.command = command
        exit_command = kwargs.get('exit_command', getattr(self, 'exit_command', None))
        self.exit_command = exit_command
        self._response_data = None
        self._prompt = kwargs.get('prompt')
        self.parent = kwargs.get('parent')
        self.response_data_callback = kwargs.get('response_data_callback')
        self.context = CommandContext(self)
        self._message_io = kwargs.get('message_io')
        self.is_root = self.parent is None
        if self.is_root and self.exit_command is None:
            self.exit_command = 'logout'
        self.children = []
        self.children_by_cmd = {}
        for ckwargs in kwargs.get('children', []):
            self.add_child(**ckwargs)
    @classmethod
    def build_cmd(cls, **kwargs):
        _cls = kwargs.get('cls')
        if _cls is not None:
            if isinstance(_cls, basestring):
                _cls = BaseCommand._command_classes.get(_cls)
            cls = _cls
        else:
            cls = BaseCommand
        return cls(**kwargs)
    def add_child(self, **kwargs):
        kwargs['parent'] = self
        child = self.build_cmd(**kwargs)
        self.children.append(child)
        self.children_by_cmd[child.command] = child
        return child
    @property
    def path(self):
        p = getattr(self, '_path', None)
        if p is not None:
            return p
        l = [self.command]
        parent = self.parent
        while parent is not None:
            l.append(parent.command)
            parent = parent.parent
        l.reverse()
        p = self._path = '/'.join(l)
        return p
    @property
    def root(self):
        if self.is_root:
            return self
        return self.parent.root
    @property
    def message_io(self):
        m_io = self._message_io
        if m_io is not None:
            return m_io
        return self.parent.message_io
    @property
    def prompt(self):
        prompt = self._prompt
        if prompt is not None:
            return prompt
        prompt = self._prompt = self.get_prompt()
        return prompt
    @property
    def response_data(self):
        return self._response_data
    @response_data.setter
    def response_data(self, value):
        if value == self._response_data:
            return
        if value is None:
            return
        self._response_data = value
        r = self.root
        if r.response_data_callback is not None:
            r.response_data_callback(obj=self, response_data=value)
    def get_prompt(self):
        return self.parent.prompt
    def find_by_path(self, path):
        if path == self.path:
            return self
        return self.root._find_by_path(path)
    def _find_by_path(self, path):
        if path == self.path:
            return self
        for child in self.children:
            r = child._find_by_path(path)
            if r is not None:
                return r
        return None
    def __call__(self):
        with self.context:
            if self.command is not None:
                msg = self.message_io.build_tx(content=self.command + '\n', read_until=self.prompt)
                self.validate_response(msg)
            elif self.prompt is not None:
                msg = self.message_io.rx_fn(self.prompt)
                self.validate_response(msg)
            else:
                msg = None
            for child in self.children:
                child()
            if self.exit_command is not None:
                if self.parent is not None:
                    read_until = self.parent.prompt
                else:
                    read_until = None
                exit_msg = self.message_io.build_tx(content=self.exit_command + '\n', read_until=read_until)
                if read_until is not None:
                    self.parent.validate_response(exit_msg)
            else:
                exit_msg = None
            self.response_message = msg
            self.response_data = self.parse_response_data(msg)
            self.exit_message = exit_msg
    def parse_response_data(self, msg):
        return False
    def validate_response(self, msg):
        if msg is None:
            raise CLICommandNoResponseError(self)
        last_line = msg.content.splitlines()[-1]
        if self.prompt not in last_line:
            raise CLICommandInvalidResponseError(self)
        return True
    def __str__(self):
        return 'path: %s, active: %s, complete: %s, response: %s, exit: %s' % (self.path, 
                                                                               self.context.active, 
                                                                               self.context.complete, 
                                                                               self.response_message, 
                                                                               self.exit_message)
        
class AuthCommand(BaseCommand):
    def __init__(self, **kwargs):
        self.username = kwargs.get('username', 'admin')
        self.password = kwargs.get('password', 'admin')
        super(AuthCommand, self).__init__(**kwargs)
        self.exit_command = None
        self.add_child(cls=LoginCommand)
    def get_prompt(self):
        return 'login as: '
class LoginCommand(BaseCommand):
    def __init__(self, **kwargs):
        super(LoginCommand, self).__init__(**kwargs)
        self.command = self.parent.username
        self.add_child(cls=PasswordCommand)
    def get_prompt(self):
        return 'password: '
class PasswordCommand(BaseCommand):
    def __init__(self, **kwargs):
        super(PasswordCommand, self).__init__(**kwargs)
        self.command = self.root.password
    def get_prompt(self):
        return None
    
class MenuCommand(BaseCommand):
    exit_command = 'exit'
    def __init__(self, **kwargs):
        super(MenuCommand, self).__init__(**kwargs)
    def get_prompt(self):
        prompt = self.parent.prompt.rstrip('>')
        prompt = '/'.join([prompt, self.command])
        return prompt + '>'
    
def build_tree(**kwargs):
    response_data = {}
    def _response_data_callback(**kwargs):
        response_data[kwargs.get('obj').path] = kwargs.get('response_data')
    auth = kwargs.get('auth')
    model = kwargs.get('model')
    commands = kwargs.get('commands')
    message_io = kwargs.get('message_io')
    response_data_callback = kwargs.get('response_data_callback')
    if response_data_callback is None:
        response_data_callback = _response_data_callback
    auth_command = AuthCommand(username=auth['username'], 
                               password=auth['password'], 
                               message_io=message_io)
    root_command = BaseCommand(prompt=model + '>', 
                               message_io=message_io, 
                               children=commands, 
                               response_data_callback=response_data_callback)
    if kwargs.get('threaded'):
        return {'auth':auth_command, 'root':root_command}
    else:
        auth_command()
        if auth_command.context.active:
            root_command()
            if not root_command.context.complete:
                root_command.context.wait()
    return response_data
