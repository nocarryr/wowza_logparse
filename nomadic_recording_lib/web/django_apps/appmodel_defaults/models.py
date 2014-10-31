from django.db import models
from django.db.models.loading import AppCache

app_cache = AppCache()

class DefaultTracker(models.Model):
    built = models.BooleanField(default=False)
    needs_rebuild = models.BooleanField(default=False)
    class Meta:
        abstract = True
        
class AppDefaultTracker(DefaultTracker):
    app_name = models.CharField(max_length=100, unique=True)
    def get_or_create_model_tracker(self, model_name):
        created = False
        try:
            m = self.model_trackers.get(model_name=model_name)
        except ModelDefaultTracker.DoesNotExist:
            m = self.model_trackers.create(model_name=model_name)
        if created:
            self.built = False
            self.save()
        return m
    def check_models(self):
        built = self.built
        needs_rebuild = False
        need_save = False
        q = self.model_trackers.all()
        if not q.exists():
            return
        if q.filter(built=False).exists():
            if built:
                need_save = True
                needs_rebuild = True
        elif not built:
            built = True
            need_save = True
        if q.filter(needs_rebuild=True).exists():
            if built:
                need_save = True
                needs_rebuild = True
        elif not built:
            built = True
            need_save = True
        if need_save:
            self.built = built
            self.needs_rebuild = needs_rebuild
            self.save()
    def __unicode__(self):
        return self.app_name
    
class ModelDefaultTracker(DefaultTracker):
    app = models.ForeignKey(AppDefaultTracker)
    model_name = models.CharField(max_length=100, related_name='model_trackers')
    class Meta:
        unique_together = ('app', 'model_name')
    def set_built(self, value, run_app_check=True):
        if value == self.built:
            return
        self.needs_rebuild = False
        self.save()
        if value and run_app_check:
            self.app.check_models()
    def save(self, *args, **kwargs):
        def do_save():
            super(ModelDefaultTracker, self).save(*args, **kwargs)
        if self.pk is None:
            do_save()
        if self.needs_rebuild:
            if not self.app.needs_rebuild:
                self.app.needs_rebuild = True
                self.app.save()
        do_save()
    def __unicode__(self):
        return self.model_name
 
APP_BUILDERS = {} 
    
class AppBuilder(object):
    def __init__(self, **kwargs):
        self._app = None
        self._tracker = None
        self.app_label = kwargs.get('app_label')
        self.model_builders = {}
        self.build_functions = kwargs.get('build_functions', {})
        APP_BUILDERS[self.app_label] = self
        defaults = kwargs.get('defaults', [])
        for default in defaults:
            self.create_builder(**default)
    @property
    def app(self):
        a = self._app
        if a is not None:
            return a
        a = self._app = self.get_app()
        return a
    @property
    def tracker(self):
        t = self._tracker
        if t is not None:
            return t
        t = self._tracker = self.get_or_create_tracker()
        return t
    def get_app(self):
        try:
            a = app_cache.get_app(self.app_label)
        except:
            a = None
        return a
    def get_or_create_tracker(self):
        try:
            a_tracker, created = AppDefaultTracker.objects.get_or_create(app_name=self.app_name)
        except:
            return None
    def create_builder(self, **kwargs):
        kwargs.setdefault('app_label', self.app_label)
        kwargs.setdefault('app_builder', self)
        b = DefaultBuilder(**kwargs)
        if b.builder_function is None:
            f = self.build_functions.get(b.model_name)
            b.builder_function = f
        self.add_builder(b)
    def add_builder(self, builder):
        builder._app_builder = self
        if builder.model_name not in self.model_builders:
            self.model_builders[builder.model_name] = []
        self.model_builders[builder.model_name].append(builder)
    def check_all(self):
        t = self.tracker
        if t.built and not t.needs_rebuild:
            return True
        for mname, mlist in self.model_builders.iteritems():
            for m in mlist:
                if m.check_built():
                    continue
                r = m.do_build(run_app_check=False)
        t.check_models()
        
class DefaultBuilder(object):
    app_label = None
    model_name = None
    builder_function = None
    def __init__(self, **kwargs):
        if self.app_label is None:
            self.app_label = kwargs.get('app_label')
        if self.model_name is None:
            self.model_name = kwargs.get('model_name')
        if self.builder_function is None:
            self.builder_function = kwargs.get('builder_function')
        a = kwargs.get('app_builder')
        if a is not None:
            self._app_builder = a
    @property
    def app_builder(self):
        a = getattr(self, '_app_builder', None)
        if a is not None:
            return a
        a = APP_BUILDERS.get(self.app_label)
        if a is None:
            a = AppBuilder(app_label=self.app_label)
        self._app_builder = a
        a.add_builder(self)
        return a
    @property
    def model(self):
        m = getattr(self, '_model', None)
        if m is not None:
            return m
        m = self._model = self.get_model()
        return m
    @property
    def tracker(self):
        t = getattr(self, '_tracker', None)
        if t is not None:
            return t
        t = self._tracker = self.get_or_create_tracker()
        return t
    def validate(self):
        v = getattr(self, '_validated', False)
        if v:
            return
        for attr in ['app_label', 'model_name', 'builder_function']:
            if getattr(self, attr) is None:
                raise NotImplementedError('no %s is defined' % (attr))
        self._validated = True
    def get_model(self):
        self.validate()
        try:
            m = app_cache.get_model(self.app_label, self.model_name)
        except:
            m = None
        return m
    def get_or_create_tracker(self):
        a_tracker = self.app_builder.tracker
        if not a_tracker:
            return None
        try:
            m_tracker = a_tracker.get_or_create_model_tracker(self.model_name)
        except:
            m_tracker = None
        return m_tracker
    def check_built(self):
        t = self.tracker
        if t.built and not t.needs_rebuild:
            return True
        return False
    def do_build(self, run_app_check=True):
        self.validate()
        f = self.builder_function
        if isinstance(f, basestring):
            app = self.app_builder.app
            f = getattr(app, f)
        result = f()
        if result:
            self.tracker.set_built(True, run_app_check)
        return result
