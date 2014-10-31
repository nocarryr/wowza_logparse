import os.path
import subprocess

class AcquireBase(object):
    def __init__(self, **kwargs):
        self.data = kwargs.get('data', {})
    @property
    def package(self):
        return self.data.get('package')
    def __call__(self, **kwargs):
        r = self.do_acquire(**kwargs)
        return r
    def do_acquire(self, **kwargs):
        return False
    
class AcquireSubprocess(AcquireBase):
    call_type = 'call'
    def subprocess_call(self, cmd_str):
        r = subprocess.call(cmd_str, shell=True)
        return r == 0
    def subprocess_check(self, cmd_str):
        s = None
        try:
            s = subprocess.check_output(cmd_str, shell=True)
        except subprocess.CalledProcessError:
            s = False
        if s:
            r = self.parse_subprocess_output(s)
        else:
            r = False
        return r
    call_type_map = {'call':'subprocess_call', 'check':'subprocess_check'}
    def parse_subprocess_output(self, s):
        '''To be overridden in subclasses
        '''
        return True
    def do_acquire(self, **kwargs):
        data = self.data
        vpath = data.get('virtualenv_path', kwargs.get('virtualenv_path'))
        dry_run = data.get('dry_run', kwargs.get('dry_run', False))
        cmd_bin = self.cmd_bin
        if vpath:
            if os.path.split(vpath)[1] != 'bin':
                vpath = os.path.join(vpath, 'bin')
            if getattr(self, 'virtualenv_capable', False):
                cmd_bin = os.path.join(vpath, cmd_bin)
        cmd_str = ' '.join([cmd_bin, self.cmd_opts % (data)])
        call_type = self.call_type
        m = getattr(self, self.call_type_map.get(call_type))
        if dry_run:
            print cmd_str
            return True
        return m(cmd_str)
        
class AcquirePIP(AcquireSubprocess):
    name = 'pip'
    cmd_bin = 'pip'
    cmd_opts = 'install -U %(package)s'
    virtualenv_capable = True
    
    
class AcquireEasyInstall(AcquireSubprocess):
    name = 'easy_install'
    cmd_bin = 'easy_install'
    cmd_opts = '-U %(package)s'
    virtualenv_capable = True
    
class AcquireApt(AcquireSubprocess):
    name = 'apt'
    cmd_bin = 'apt-get'
    cmd_opts = 'install %(package)s'
    
ACQUIRE_CLASSES = {}
def build_acquire_classes(*args):
    global ACQUIRE_CLASSES
    default_cls = [AcquirePIP, AcquireEasyInstall, AcquireApt]
    if not ACQUIRE_CLASSES:
        for cls in default_cls:
            ACQUIRE_CLASSES[cls.name] = cls
    for cls in args:
        ACQUIRE_CLASSES[cls.name] = cls
    
build_acquire_classes()

def build_acquirer(**kwargs):
    acq_type = kwargs.get('acquire_type')
    cls = ACQUIRE_CLASSES.get(acq_type)
    return cls(**kwargs)
    
def do_acquire(**kwargs):
    call_kwargs = kwargs.get('call_kwargs')
    obj = build_acquirer(**kwargs)
    if not call_kwargs:
        call_kwargs = kwargs
    return obj(**call_kwargs)
    
