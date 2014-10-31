import sys
import site
import os.path
import types
import imp


LINKED_PATHS = {}
LINKED_MODULES = {}
LOADERS = {}

system_prefixes = site.PREFIXES[:] + [site.USER_SITE]

def add_linked_package(vpath, pkg, submodule_names=None):
    def load_module(name, path):
        fullname = '.'.join([path, name])
        f = None
        try:
            f, p, d = imp.find_module(name, [path])
            mod = imp.load_module(fullname, f, p, d)
            return mod
        except ImportError:
            return None
        finally:
            if f is not None:
                f.close()
    pkgpath = pkg.__path__
    #print 'linking pkg vpath=%s, pkgpath=%s' % (vpath, pkgpath)
    if submodule_names is None:
        submodule_names = dir(pkg)
        attempt_load = False
    else:
        attempt_load = True
    for key in submodule_names:
        if key.startswith('_'):
            continue
        try:
            val = getattr(pkg, key)
        except AttributeError:
            if not attempt_load:
                continue
            val = load_module(key, pkgpath[0])
            #print 'attempted to load module %s in path %s. mod=%s' % (key, pkgpath, val)
            if val is not None:
                setattr(pkg, key, val)
        if type(val) != types.ModuleType:
            continue
        for pfx in system_prefixes:
            if pfx in val.__file__:
                continue
        if '__init__.py' in os.path.basename(val.__file__):
            subpkgpath = ['/'.join([vpath[0], key])]
            add_linked_package(subpkgpath, val)
        add_linked_module('.'.join(vpath[0].split('/')), val)
    
def add_linked_module(vpath, mod):
    modname = mod.__name__.rsplit('.', 1)[1]
    fullname = '.'.join([vpath, modname])
    LINKED_MODULES[fullname] = mod


class LinkedModuleFinder(object):
    def find_module(self, fullname, path=None):
        mod = LINKED_MODULES.get(fullname)
        if mod is not None:
            #print 'found linked module: fullname=%s, path=%s, modpath=%s, mod=%s' % (fullname, path, getattr(mod, '__path__', None), mod)
            return self
        return None
    def load_module(self, fullname):
        try:
            return LINKED_MODULES[fullname]
        except:
            raise ImportError('LinkedModule could not load %s' % (fullname))


sys.meta_path.append(LinkedModuleFinder())
