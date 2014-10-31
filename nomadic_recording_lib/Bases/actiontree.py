from BaseObject import BaseObject
from threadbases import BaseThread
from misc import iterbases
import time

class TimeoutChecker(BaseThread):
    def __init__(self, **kwargs):
        super(TimeoutChecker, self).__init__(**kwargs)
        self.handler = kwargs.get('handler')
        self._threaded_call_ready.wait_timeout = 1.
    def _thread_loop_iteration(self):
        r = False
        h = self.handler
        now = time.time()
        if h.start_timestamp is None:
            h.start_timestamp = now
        h.elapsed_time = now - h.start_timestamp
        for obj in self.handler.action_obj.itervalues():
            if obj.is_past_due:
                r = True
                break
        if r:
            self.handler.cancel()
            
class ActionHandler(BaseObject):
    _Properties = {'completed':dict(default=False), 
                   'working':dict(default=False), 
                   'cancelled':dict(default=False)}
    def __init__(self, **kwargs):
        super(ActionHandler, self).__init__(**kwargs)
        self.action_checker = None
        self.iterating_actions = False
        self._cancelling = False
        self.start_timestamp = None
        self.elapsed_time = 0
        self.parent_obj = kwargs.get('parent_obj')
        self.LOG.info('handler (%r) init. kwargs=%r' % (self, kwargs))
        self.action_cls = {}
        self.action_obj = {}
        self.root_actions = []
        self._run_kwargs = {}
        actions = kwargs.get('actions', getattr(self.__class__, 'actions', []))
        self.bind(working=self.on_own_working_set, 
                  completed=self.on_own_completed_set)
        for action in actions:
            if isinstance(action, dict):
                add_kwargs = action
            elif isinstance(action, Action):
                add_kwargs = {'name':action.name, 'obj':action}
            else:
                add_kwargs = {'cls':action}
            obj = self.add_action_obj(**add_kwargs)
            self.root_actions.append(obj)
            obj.bind(completed=self.on_root_action_completed_set, 
                     working=self.on_root_action_working_set)
    def unlink(self):
        for a in self.root_actions:
            a.unbind(self)
            a.unlink()
        super(ActionHandler, self).unlink()
    def __call__(self, **kwargs):
        self.working = True
        self._run_kwargs = kwargs
        self.run(**kwargs)
    def run(self, **kwargs):
        self.iterating_actions = True
        for action in self.root_actions:
            action(**kwargs)
        self.iterating_actions = False
        self.check_actions_working()
    def cancel(self, blocking=True):
        self._cancelling = True
        for action in self.root_actions:
            action._cancel(blocking)
    def start_action_checker(self):
        if self.action_checker is not None:
            return
        t = self.action_checker = TimeoutChecker(handler=self)
        t.start()
    def stop_action_checker(self):
        t = self.action_checker
        if t is None:
            return
        t.stop(blocking=True)
        self.action_checker = None
    def add_action_cls(self, cls, name=None):
        if name is None:
            name = cls.__name__
        self.action_cls[name] = cls
    def find_action_cls(self, **kwargs):
        name = kwargs.get('name')
        cls = kwargs.get('cls')
        d = {'name':name, 'cls':cls}
        if name is not None:
            d['cls'] = self.action_cls.get(name)
        elif cls is not None:
            for key, val in self.action_cls.iteritems():
                if val == cls:
                    d['name'] = key
        return d
    def find_action_obj(self, **kwargs):
        name = kwargs.get('name')
        cls = kwargs.get('cls')
        d = self.find_action_cls(name=name, cls=cls)
        obj = self.action_obj.get(d['name'])
        if obj is None:
            obj = self.add_action_obj(**kwargs)
        return obj
    def add_action_obj(self, **kwargs):
        cls = kwargs.get('cls')
        name = kwargs.get('name')
        obj = kwargs.get('obj')
        objkwargs = kwargs.get('kwargs', {})
        if name is not None and cls is None:
            if name in self.action_cls:
                cls = self.action_cls[name]
        if cls is not None and obj is None:
            if cls not in self.action_cls.values():
                add_kwargs = {'cls':cls}
                if name is not None:
                    add_kwargs['name'] = name
                self.add_action_cls(**add_kwargs)
            name = self.find_action_cls(cls=cls)['name']
            objkwargs.setdefault('name', name)
            objkwargs['handler'] = self
            obj = cls(**objkwargs)
        self.action_obj[name] = obj
        obj.handler = self
        return obj
    def check_actions_working(self):
        if self.iterating_actions:
            return True
        for action in self.root_actions:
            if action.working:
                return True
        if self._cancelling:
            self.cancelled = True
        self.working = False
        self.completed = True
        return False
    def on_root_action_completed_set(self, **kwargs):
        pass
    def on_root_action_working_set(self, **kwargs):
        if kwargs.get('value'):
            if self.start_timestamp is None:
                self.start_timestamp = time.time()
            return
        self.check_actions_working()
    def on_own_working_set(self, **kwargs):
        if not kwargs.get('value'):
            return
        self.start_action_checker()
    def on_own_completed_set(self, **kwargs):
        if not kwargs.get('value'):
            return
        self.stop_action_checker()
class Action(BaseObject):
    _Properties = {'completed':dict(default=False), 
                   'working':dict(default=False), 
                   'cancelled':dict(default=False)}
    _max_run_time = None
    _max_working_time = None
    def __init__(self, **kwargs):
        self._handler = None
        self._cancelling = False
        self.start_timestamp = None
        super(Action, self).__init__(**kwargs)
        self.register_signal('all_complete')
        self.bind(completed=self.on_own_completed_set)
        self.name = kwargs.get('name', self.__class__.__name__)
        self._dependencies = []
        self._dependants = []
        handler = kwargs.get('handler')
        if handler is None:
            hkwargs = kwargs.copy()
            if 'actions' not in hkwargs:
                hkwargs['actions'] = [self]
            handler = ActionHandler(**hkwargs)
        else:
            self.handler = handler
    def unlink(self):
        is_root = self.is_root_action
        for a in self._dependencies:
            a.unbind(self)
            if is_root:
                a.unlink()
        for a in self._dependants:
            a.unbind(self)
            if is_root:
                a.unlink()
        super(Action, self).unlink()
    @property
    def handler(self):
        return self._handler
    @handler.setter
    def handler(self, value):
        if self._handler is not None:
            return
        if value is None:
            return
        self._handler = value
        value.bind(completed=self.on_handler_completed)
        self.build_dependencies()
    @property
    def run_kwargs(self):
        h = self.handler
        if not h:
            return {}
        return h._run_kwargs
    @run_kwargs.setter
    def run_kwargs(self, value):
        if not isinstance(value, dict):
            return
        h = self.handler
        if not h:
            return
        h._run_kwargs.update(value)
    @property
    def is_root_action(self):
        h = self.handler
        if h is None:
            return
        return self in h.root_actions
    @property
    def parent_obj(self):
        h = self.handler
        if not h:
            return
        return h.parent_obj
    @property
    def current_runtime(self):
        if not self.working:
            return
        if self.completed:
            return
        ts = self.start_timestamp
        if not ts:
            return
        return time.time() - ts
    @property
    def is_past_due(self):
        return self.check_action_runtime() or self.check_action_worktime()
    def check_action_runtime(self):
        max_rt = self._max_run_time
        if not max_rt:
            return False
        rt = self.current_runtime
        if rt is None:
            return False
        return rt > max_rt
    def check_action_worktime(self):
        max_wt = self._max_working_time
        if not max_wt:
            return False
        return self.handler.elapsed_time > max_wt
    def __call__(self, **kwargs):
        wait = kwargs.get('action_wait', False)
        if self.working:
            return
        if self._cancelling or self.cancelled:
            return
        self.working = True
        h = self.handler
        if self.is_root_action and not self.run_kwargs:
            self.run_kwargs = kwargs
        if not len(self._dependencies):
            if not self.check_completed():
                self._run(**kwargs)
        else:
            for dep in self._dependencies:
                if dep.working:
                    continue
                dep(**kwargs)
        if wait:
            del kwargs['action_wait']
            wkwargs = {}
            for key in ['timeout', 'interval']:
                wkwargs[key] = kwargs.get('_'.join(['action', 'wait', key]))
            self.wait(**wkwargs)
    def _run(self, **kwargs):
        self.start_timestamp = time.time()
        self.run(**kwargs)
    def run(self, **kwargs):
        '''Subclasses will override this method to do their work.
        When complete, set "self.completed" to True.
        '''
        self.completed = True
    def cancel(self, blocking=True):
        self.handler.cancel(blocking)
    def _cancel(self, blocking=True):
        if self._cancelling:
            return
        self._cancelling = True
        for dep in self._dependencies:
            dep._cancel(blocking)
        self.cancelled = True
        self.completed = True
        self.working = False
        if self.is_root_action:
            self.unlink()
        self._cancelling = False
    def wait(self, timeout=None, interval=None):
        start = time.time()
        if interval is None:
            interval = 1.
        while True:
            self._wait_loop_iteration()
            h = self.handler
            if h is not None:
                if h.completed:
                    break
            else:
                if not self.working and self.completed:
                    break
            if timeout is not None:
                now = time.time()
                if now - start >= timeout:
                    break
            time.sleep(interval)
    def _wait_loop_iteration(self):
        pass
    def check_completed(self, *args, **kwargs):
        return self.completed
    def build_dependencies(self):
        h = self.handler
        dep_cls = []
        for act_cls in iterbases(self, Action):
            if not hasattr(act_cls, 'dependencies'):
                continue
            dep_cls.extend(getattr(act_cls, 'dependencies', []))
        for cls in dep_cls:
            if isinstance(cls, Action):
                fkwargs = {'obj':cls}
            elif issubclass(cls, Action):
                fkwargs = {'cls':cls}
            else:
                fkwargs = {'name':cls}
            obj = h.find_action_obj(**fkwargs)
            self.add_dependancy(obj)
    def add_dependancy(self, obj):
        if obj in self._dependencies:
            return
        self._dependencies.append(obj)
        obj.add_dependant(self)
        obj.bind(completed=self.on_dependancy_completed_set)
    def add_dependant(self, obj):
        if obj in self._dependants:
            return
        self._dependants.append(obj)
        obj.bind(working=self.on_dependant_working_set)
    def check_dependants_working(self):
        deps = self._dependants
        if not len(deps):
            return False
        for obj in deps:
            if obj.working:
                return True
        return False
    def on_dependancy_completed_set(self, **kwargs):
        if not kwargs.get('value'):
            return
        cancelled = False
        for obj in self._dependencies:
            if obj.cancelled:
                cancelled = True
            if not obj.completed:
                return
        if cancelled:
            if not self.cancelled and not self._cancelling:
                self.cancel(blocking=True)
            return
        if not self.check_completed():
            self._run(**self.handler._run_kwargs)
    def on_dependant_working_set(self, **kwargs):
        if kwargs.get('value'):
            return
        if self.check_dependants_working():
            return
        self.working = False
    def on_own_completed_set(self, **kwargs):
        if not kwargs.get('value'):
            return
        if self.check_dependants_working():
            return
        self.working = False
    def on_handler_completed(self, **kwargs):
        if not kwargs.get('value'):
            return
        self.emit('all_complete', action=self)
    def __str__(self):
        return '%s Action (working=%s, completed=%s, cancelled=%s)' % (self.name, self.working, self.completed, self.cancelled)
    
def do_test():
    import threading
    import time
    class TestActionBase(Action):
        def __init__(self, **kwargs):
            super(TestActionBase, self).__init__(**kwargs)
            self.bind(working=self.on_own_working_set)
        def run(self):
            self.LOG.info('%s running' % (self))
            timeout = self.parent_obj.timers[self.name]
            self.timer = threading.Timer(timeout, self.on_timer)
            self.timer.start()
        def on_timer(self, *args, **kwargs):
            self.LOG.info('%s timer done' % (self))
            self.completed = True
        def on_own_completed_set(self, **kwargs):
            if kwargs.get('value'):
                self.LOG.info('%s completed' % (self))
            super(TestActionBase, self).on_own_completed_set(**kwargs)
        def on_own_working_set(self, **kwargs):
            self.LOG.info('%s working=%s' % (self, kwargs.get('value')))
    class TestActionA(TestActionBase):
        pass
    class TestActionB(TestActionBase):
        dependencies = [TestActionA]
    class TestActionC(TestActionBase):
        dependencies = [TestActionB]
    class TestObj(BaseObject):
        def __init__(self):
            super(TestObj, self).__init__()
            self.timers = {'TestActionA':1., 'TestActionB':2., 'TestActionC':3.}
            self.current_action = None
        def run(self, cls=None):
            if cls is None:
                cls = TestActionC
            a = self.current_action = cls(parent_obj=self)
            a.bind(all_complete=self.on_current_action_all_complete)
            a()
            self.wait()
        def wait(self):
            self.LOG.info('waiting')
            while self.current_action is not None:
                time.sleep(1.)
            self.LOG.info('wait complete')
        def on_current_action_all_complete(self, **kwargs):
            action = kwargs.get('action')
            self.LOG.info('all_complete, action=%s' % (action))
            self.current_action.unbind(self)
            self.current_action.unlink()
            self.current_action = None
    testobj = TestObj()
    testobj.run()
    
if __name__ == '__main__':
    do_test()
