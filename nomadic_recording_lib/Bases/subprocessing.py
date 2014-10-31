import multiprocessing
import multiprocessing.managers
    
from BaseObject import BaseObject
from osc_base import OSCBaseObject
import Properties
    
SUBPROCESSES = {}

def get_subprocesses():
    return SUBPROCESSES

def BuildSubProcess(cls, name, parent=None, **kwargs):
    assert name not in SUBPROCESSES, 'SubProcess %s already exists' % (name)
    sp = SubProcess(cls=cls, name=name, SubProcessParent=parent, kwargs=kwargs)
    SUBPROCESSES[sp.name] = sp
    sp.start()
    sp.obj_init.wait()
    obj = sp.out_queue.get()
    #print name, obj
    return obj
    
class SubProcess(multiprocessing.Process):
    def __init__(self, **kwargs):
        self.cls = kwargs.get('cls')
        self._obj = None
        pkwargs = {}
        for key in ['name', 'args', 'kwargs']:
            if key not in kwargs:
                continue
            pkwargs[key] = kwargs[key]
        super(SubProcess, self).__init__(**pkwargs)
        self.SubProcessParent = kwargs.get('SubProcessParent')
        self.running = multiprocessing.Event()
        self.obj_init = multiprocessing.Event()
        self.in_queue = multiprocessing.Queue()
        self.out_queue = multiprocessing.Queue()
    @property
    def obj(self):
        return self._obj
    def run(self):
        in_queue = self.in_queue
        running = self.running
        running.set()
        args = self._args
        kwargs = self._kwargs
        obj = self.cls(*args, **kwargs)
        obj.SubProcess = self
        self._obj = obj
        self.send_item(obj)
        self.obj_init.set()
        while running.is_set():
            item = in_queue.get()
            if isinstance(item, QueueTerminator):
                self.running.clear()
            else:
                self.process_item(item)
    def stop(self):
        self.in_queue.put(QueueTerminator())
    def send_item(self, item):
        self.out_queue.put(item)
    def process_item(self, item):
        pass
        
class QueueTerminator(object):
    pass
    
MANAGERS = {}

class Manager(multiprocessing.managers.SyncManager):
    def __init__(self, **kwargs):
        super(Manager, self).__init__()
        self.id = kwargs.get('id', id(self))
        MANAGERS[self.id] = self
        self.set_root_obj(**kwargs)
    def start(self):
        super(Manager, self).start()
        self.root_namespace = self.BaseObjNamespace()
        #self.root_namespace._set_obj(self.root_obj)
        _set_obj_namespace(self, self.root_obj, self.root_namespace)
    #def on_process_init(*args):
    #    self.root_namespace = self.BaseObjNamespace()
    def set_root_obj(self, **kwargs):
        self.root_obj = kwargs.get('root_obj')
        if self.root_obj is None:
            rocls = kwargs.get('root_obj_class')
            rokwargs = kwargs.get('root_obj_kwargs', {})
            self.root_obj = rocls(**rokwargs)
        self.root_obj.SubProcessManager = self
        #self.root_namespace._set_obj(self.root_obj)


class oldManager(multiprocessing.managers.SyncManager):
    def __init__(self, **kwargs):
        self.SubProcessParent = kwargs.get('SubProcessParent')
        self.SubProcessName = kwargs.get('SubProcessName')
        super(Manager, self).__init__(**kwargs)
        self.PropertyQueue = self.Queue()
        self.SignalQueue = self.Queue()
        self._Properties = {}
        self._Signals = set()
        for prop in self.SubProcessParent.Properties.itervalues():
            self.register_Property(prop)
        for sig in self.SubProcessParent._emitters.iterkeys():
            self.register_Signal(sig)
    def register_Property(self, prop):
        self._Properties[prop.name] = prop
    def register_Signal(self, sig):
        self._Signals.add(sig)
    def send_Property(self, **kwargs):
        prop = kwargs.get('Property')
        value = kwargs.get('value')
        if prop._type is not None:
            ptype = getattr(self, prop.type.__name__)
            value = ptype(value)
        d = self.dict()
        #d.update({'name':prop.name, 
        #self.PropertyQueue.put(
                
class PropertyProxy(multiprocessing.managers.BaseProxy):
    _exposed_ = ('_get_range', '_set_range', 
                 '_get_normalized', '_set_normalized', 
                 '_get_noramlized_and_offset', '_set_noramlized_and_offset', 
                 'set_value')
    def __init__(self, *args, **kwargs):
        super(PropertyProxy, self).__init__(*args)
        self._Property = kwargs.get('Property')
        

class PropertyConnectorProxy(multiprocessing.managers.BaseProxy, Properties.PropertyConnector):
    _exposed_ = ('set_Property_value', 'get_Property_value', 'on_Property_value_changed')
    def __init__(self, *args, **kwargs):
        super(PropertyProxy, self).__init__(*args)
        self.Property = kwargs.get('Property')
        
def _set_obj_namespace(manager, obj, namespace):
    attrdict = get_exposed_attributes(obj)
    for attr in attrdict['ExposedAttributes']:
        setattr(namespace, attr, getattr(obj, attr))
    for key, child in iter_children(obj):
        if isinstance(child, dict):
            cdict = manager.dict()
            setattr(namespace, key, cdict)
            for ckey, cval in child.iteritems():
                childNS = manager.BaseObjNamespace()
                cdict[ckey] = childNS
                _set_obj_namespace(manager, cval, childNS)
        else:
            childNS = manager.BaseObjNamespace()
            _set_obj_namespace(manager, child, childNS)
            setattr(namespace, key, childNS)
            
class BaseObjNamespace(multiprocessing.managers.Namespace):
    def _add_nested_child(self, child, manager=None):
        pass
        #_set_obj_namespace(manager, child, self)
    
#    def __init__(self, obj=None):
#        if obj is not None:
#            self._set_obj(obj)
#    
#    def __repr__(self):
#        s = super(BaseObjNamespace, self).__repr__()
#        s = ' '.join([repr(multiprocessing.current_process()), s])
#        return s
            
class BaseObjNamespaceProxy(multiprocessing.managers.NamespaceProxy):
    def _add_nested_child(self, child, manager=None):
        pass
    
    #def __getattr__(self, key):
    #    print self, ' getattr: ', multiprocessing.current_process()
    #    return super(BaseObjNamespaceProxy, self).__getattr__(key)
    def __repr__(self):
        items = self.__dict__.items()
        temp = []
        for name, value in items:
            if not name.startswith('_'):
                temp.append('%s=%r' % (name, value))
        temp.sort()
        return 'Namespace(%s)' % str.join(', ', temp)
    
class DictProxy(multiprocessing.managers.DictProxy):
    def __setitem__(self, key, value):
        if type(value) == dict:
            print 'making dictproxy: ', key, value
            value = manager.dict(value)
        super(DictProxy, self).__setitem__(key, value)
        
Manager.register('BaseObjNamespace', BaseObjNamespace, BaseObjNamespaceProxy)
Manager.register('dict', dict, DictProxy)


def iter_children(root_obj, path=None):
    #if path is None:
    #    path = []
    keys = set(getattr(root_obj, 'saved_child_objects', []))
    keys |= set(getattr(root_obj, 'ChildGroups', {}).keys())
    for key in keys:
        child = getattr(root_obj, key, None)
        if child is None:
            continue
        #path.append(key)
        yield key, child
        #for next_path, next_child in iter_children(child, path):
        #    yield next_path, next_child
        
def get_exposed_attributes(obj):
    attrs = ['Properties', '_emitters']
    d = {}
    d['ExposedAttributes'] = set()
    for attr in attrs:
        d[attr] = {}
        attrval = getattr(obj, attr, None)
        if attrval is None:
            continue
        for key, val in attrval.iteritems():
            d[attr][key] = val
            if attr != '_emitters':
                d['ExposedAttributes'].add(key)
    d['ExposedAttributes'] |= set(getattr(obj, 'ExposedAttributes', []))
    return d
    
def test():
    class TestObj(BaseObject):
        _Properties = {'name':dict(default=''), 'value':dict(default=0)}
        _saved_child_objects = ['test_children']
        ExposedAttributes = ['other_testobj']
        def __init__(self, **kwargs):
            super(TestObj, self).__init__(**kwargs)
            self.name = kwargs.get('name')
            self.value = kwargs.get('value')
            self.test_children = {}
            if 'root' in self.name:
                for i, key in enumerate(kwargs.get('childkeys')):
                    obj = TestObj(name=key, value=i)
                    self.test_children[key] = obj
        @property
        def other_testobj(self):
            if 'root' not in self.name:
                return ''
            if '1' in self.name:
                m_id = 'm2'
            else:
                m_id = 'm1'
            m = MANAGERS.get(m_id)
            if not m:
                return 'none'
            return '%r\n%r\n' % (multiprocessing.current_process(), m.root_namespace)
            
    #testobj1 = TestObj(name='root1', childkeys='abcdefg')
    #testobj2 = TestObj(name='root2', childkeys='hijklmn')
    m1 = Manager(id='m1', root_obj_class=TestObj, root_obj_kwargs=dict(name='root1', childkeys='abcdefg'))
    m1.start()
    #m1.set_root_obj(root_obj=testobj1)
    #print m1.root_namespace
    
    m2 = Manager(id='m2', root_obj_class=TestObj, root_obj_kwargs=dict(name='root2', childkeys='hijklmn'))
    m2.start()
    #m2.set_root_obj(root_obj=testobj2)
    #print m2.root_namespace
    
    print m1.root_namespace.other_testobj
    print m2.root_namespace.other_testobj
    print type(m2.root_namespace)
    
    print m1.root_namespace
    print m2.root_namespace
    
    #ns = BaseObjNamespace(testobj)
    #print ns
    #print ns.test_children
    
if __name__ == '__main__':
    test()
