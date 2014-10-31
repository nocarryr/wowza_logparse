import os.path
import json
from acquisition import do_acquire

def iterbases(obj, lastclass='object'):
    if type(lastclass) == type:
        lastclass = lastclass.__name__
    if type(obj) == type:
        cls = obj
    else:
        cls = obj.__class__
    while cls.__name__ != lastclass:
        yield cls
        cls = cls.__bases__[0]

class PackageAcquireError(Exception):
    def __init__(self, pkg):
        self.pkg = pkg
    def __str__(self):
        return repr(self.pkg)

class Manager(object):
    def __init__(self, **kwargs):
        self.Packages = {}
        self.pkg_classes = {}
    def run(self, **kwargs):
        for pkg in self.Packages.itervalues():
            pkg.acquire(**kwargs)
    def add_package_obj(self, pkg_obj):
        deps = getattr(pkg_obj, 'Dependencies', None)
        if not deps:
            self.Packages[pkg_obj.name] = pkg_obj
            return True
        def find_and_add_pkg(pkg):
            dep_pkg, dep_path = self.find_package_obj(pkg.name)
            if dep_pkg is not None:
                return True, False
            r = self.add_package_obj(dep_pkg)
            return False, r
        deps_not_added = set()
        dep_added = False
        for pkg in deps.itervalues():
            exists, added = find_and_add_pkg(pkg)
            if added:
                dep_added = True
            elif not exists:
                deps_not_added.add(pkg)
        if not dep_added:
            return False
        for pkg in deps_not_added.copy():
            exists, added = find_and_add_pkg(pkg)
            if exists or added:
                deps_not_added.discard(pkg)
        return len(deps_not_added) == 0
    def find_package_obj(self, pkg_name, include_path=True):
        def do_return(pkg, path):
            if include_path:
                return pkg, path
            return pkg
        obj = self.Packages.get(pkg_name)
        if obj is not None:
            return do_return(obj, '/%s' % (pkg_name))
        for pkg in self.Packages.itervalues():
            obj, path = pkg.find_dependant(pkg_name)
            if obj:
                return do_return(obj, path)
        return do_return(None, None)
        
MANAGER = Manager()
    
class DependencyPackage(object):
    name = None
    acquire_type = None
    dependencies = None
    def __init__(self, **kwargs):
        name = kwargs.get('name')
        if name is not None:
            self.name = name
        acq_type = kwargs.get('acquire_type', 'pip')
        self.acquire_type = acq_type
        mgr = kwargs.get('manager')
        if not mgr:
            mgr = MANAGER
        self.manager = mgr
        self.Dependencies = {}
        self.Dependants = {}
        flat_dep = self.FlatDependencies = set()
        for cls in iterbases(self):
            deps = getattr(cls, 'dependencies', [])
            if not deps:
                continue
            for dep in deps:
                if isinstance(dep, DependencyPackage):
                    depobj = dep
                else:
                    depobj = self.build_dependency_obj(dep, **kwargs)
                self.Dependencies[depobj.name] = depobj
        self.manager.add_package_obj(self)
    def run(self, **kwargs):
        self.manager.run(**kwargs)
    def build_dependency_obj(self, cls, **kwargs):
        if issubclass(cls, DependencyPackage):
            name = cls.name
        else:
            name = cls
            cls = DependencyPackage
        dkwargs = kwargs.get('%s_kwargs' % (name))
        if not dkwargs:
            dkwargs = kwargs
        dkwargs = dkwargs.copy()
        dkwargs.setdefault('name', name)
        dkwargs['manager'] = self.manager
        return cls(**dkwargs)
    def add_dependant(self, obj):
        self.Dependants[obj.name] = obj
    def find_dependant(self, pkg_name, path=None, include_path=True):
        def do_return(pkg, path):
            if include_path:
                return pkg, path
            return pkg
        if path is None:
            path = ''
        path = '/'.join([path, self.name])
        obj = self.Dependants.get(pkg_name)
        if obj:
            path = '/'.join([path, pkg_name])
            return do_return(obj, path)
        for pkg in self.Dependants.itervalues():
            obj, newpath = pkg.find_dependant(pkg_name, path)
            if obj:
                return do_return(obj, newpath)
        return do_return(None, None)
    def acquire(self, **kwargs):
        akwargs = kwargs.copy()
        data = kwargs.get('data', {})
        data = data.copy()
        data['package'] = self.name
        akwargs['data'] = data
        akwargs['acquire_type'] = self.acquire_type
        r = do_acquire(**akwargs)
        if not r:
            raise PackageAcquireError(self)
    def __repr__(self):
        return '<%s object (%s) at %s>' % (self.__class__.__name__, self.name, id(self))
    def __str__(self):
        return repr(self)

def build_from_list(*args, **kwargs):
    mgr = None
    for arg in args:
        if type(arg) == type and issubclass(arg, DependencyPackage):
            obj = arg(**kwargs)
        else:
            if isinstance(arg, basestring):
                arg = {'name':arg}
            pkwargs = arg.copy()
            pkwargs.update(kwargs)
            obj = DependencyPackage(**pkwargs)
        if mgr is None:
            mgr = obj.manager
    return mgr
   
def parse_csv(s):
    lines = [line.strip() for line in s.splitlines()]
    fields = []
    for line in lines:
        l = [v.strip() for v in line.split(',')]
        if not len(l):
            continue
        fields.extend(l)
    return [{'name':field} for field in fields]
def parse_json(s):
    return json.loads(s)
def parse_from_string(s, fmt='csv'):
    if fmt == 'csv':
        return parse_csv(s)
    elif fmt == 'json':
        return parse_json(s)
def parse_from_file(filename, fmt='csv'):
    filename = os.path.expanduser(filename)
    try:
        f = open(filename, 'r')
        s = f.read()
    except:
        s = None
    finally:
        f.close()
    if s is not None:
        return parse_from_string(s, fmt=fmt)
    

    
