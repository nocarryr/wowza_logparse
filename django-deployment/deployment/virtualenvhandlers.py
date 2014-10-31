import os.path
import subprocess

def normalize_path(path):
    path = os.path.expanduser(path)
    path = os.path.abspath(path)
    return path
    
def check_env_exists(path):
    path = normalize_path(path)
    if not os.path.exists(path):
        return False
    if not os.path.exists(os.path.join(path, 'bin')):
        return False
    return True
    
def create_env(path):
    path = normalize_path(path)
    if check_env_exists(path):
        return
    err = subprocess.call('virtualenv %s' % (path), shell=True)
    return err == 0
    
class VirtualEnv(object):
    def __init__(self, **kwargs):
        self._path = None
        self.enable_creation = kwargs.get('enable_creation', True)
        self.path = kwargs.get('path')
    @property
    def path(self):
        return self._path
    @path.setter
    def path(self, value):
        if isinstance(value, basestring):
            value = normalize_path(value)
        if value == self._path:
            return
        self._path = value
        if value is not None and self.enable_creation:
            create_env(value)
    @property
    def exists(self):
        path = self.path
        if not path:
            return False
        return check_env_exists(path)
