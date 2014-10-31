import json
try:
    import logging
except:
    logging = None
import traceback
from django.db import models
    
class ModelDefault(models.Model):
    app_name = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    defaults_built = models.BooleanField(default=False)
    #class Meta:
    #    unique_together = ('app_name', 'model_name')
    def get_model_kwargs(self, get_all=False):
        mkwargs = {}
        q = self.default_data.all()
        if not get_all:
            q = q.filter(model_needs_update=True)
        for data in self.default_data.filter(model_needs_update=True):
            mkwargs[data.field_name] = data.get_field_value()
        return mkwargs
    def __unicode__(self):
        return u'.'.join([self.app_name, self.model_name])
    def save(self, *args, **kwargs):
        def do_save():
            super(ModelDefault, self).save(*args, **kwargs)
        if self.pk is None:
            do_save()
        if self.defaults_built:
            for data in self.default_data.filter(model_needs_update=True):
                data.model_needs_update = False
                data.save()
        do_save()
        
class ModelDefaultData(models.Model):
    field_name = models.CharField(max_length=100)
    field_value = models.CharField(max_length=600, null=True)
    model_needs_update = models.BooleanField(default=True)
    value_is_string = models.BooleanField(default=True)
    parent_obj = models.ForeignKey(ModelDefault, related_name='default_data')
    def get_field_value(self):
        if self.value_is_string:
            return self.field_value
        return json.loads(self.field_value)
    def set_field_value(self, value):
        if isinstance(value, basestring):
            self.value_is_string = True
            self.field_value = value
            return
        self.value_is_string = False
        self.field_value = json.dumps(value, ensure_ascii=False, separators=(',', ';'))
    def __unicode__(self):
        return u': '.join([self.field_name, self.field_value])
    
def build_defaults(*args):
    for arg in args:
        if not isinstance(arg, dict):
            continue
        model = arg.get('model')
        mgr = arg.get('manager')
        if not mgr:
            mgr = model.objects
        if not model:
            model = mgr.model
        unique_field = arg['unique']
        dlist = arg['defaults']
        mdefault_kwargs = {'app_name':model._meta.app_label, 
                           'model_name':model._meta.object_name}
        try:
            count = mgr.all().count()
        except:
#            exc_str = traceback.format_exc()
#            try:
#                logger = logging.getLogger()
#                logger.error(exc_str)
#            except:
#                print exc_str
            traceback.print_exc()
            return False
        for data in dlist:
            try:
                q = ModelDefault.objects.filter(**mdefault_kwargs)
                q = q.filter(default_data__field_name=unique_field)
                mdefault = q.get(default_data__field_value=data[unique_field])
            except ModelDefault.DoesNotExist:
                mdefault = ModelDefault(**mdefault_kwargs)
                mdefault.save()
            except:
    #            exc_str = traceback.format_exc()
    #            try:
    #                logger = logging.getLogger()
    #                logger.error(exc_str)
    #            except:
    #                print exc_str
                traceback.print_exc()
                return False
            try:
                obj = mgr.get(**{unique_field:data[unique_field]})
                needs_create = False
            except model.DoesNotExist:
                obj = None
                needs_create = True
            needs_update = False
            for fname, fval in data.iteritems():
                try:
                    default_data = mdefault.default_data.get(field_name=fname)
                    dfield_value = default_data.get_field_value()
                    if dfield_value != fval:
                        default_data.model_needs_update = True
                        default_data.save()
                except ModelDefaultData.DoesNotExist:
                    default_data = ModelDefaultData(parent_obj=mdefault, 
                                                    field_name=fname)
                    default_data.set_field_value(fval)
                    default_data.save()
                    needs_update = True
            if needs_create:
                mkwargs = mdefault.get_model_kwargs(get_all=True)
                if hasattr(model, 'default_builder_create'):
                    model.default_builder_create(**mkwargs)
                else:
                    obj = model(**mkwargs)
                    obj.save()
            elif needs_update:
                mkwargs = mdefault.get_model_kwargs()
                if hasattr(obj, 'default_builder_update'):
                    obj.default_builder_update(**mkwargs)
                else:
                    for fname, fval in mkwargs.iteritems():
                        setattr(obj, fname, fval)
                    obj.save()
            if needs_create or needs_update:
                mdefault.defaults_built = True
                mdefault.save()
