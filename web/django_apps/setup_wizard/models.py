from django.db import models


def is_iterable(obj):
    if type(obj) in [list, tuple, set]:
        return True
    if isinstance(obj, models.query.QuerySet):
        return True
    return False
    


class HtmlAttributeDefinition(models.Model):
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=300, blank=True, null=True)
    @classmethod
    def _build_value(cls, *args):
        val_list = []
        def add_val(obj):
            if is_iterable(val):
                for subval in val:
                    add_val(val)
            else:
                s = unicode(val)
                if s in val_list:
                    return
                val_list.append(s)
        for arg in args:
            add_val(arg)
        return u' '.join(val_list)
    def get_value_list(self, value=None):
        if value is None:
            value = self.value
        if not value:
            return []
        return value.split(u' ')
    def add_value(self, *args, **kwargs):
        do_save = kwargs.get('do_save', True)
        val_list = self.get_value_list()
        val_list.extend(args)
        self.value = self._build_value(val_list)
        if do_save:
            self.save()
    @classmethod
    def create(cls, **kwargs):
        value = kwargs.get('value')
        if value is not None:
            value = cls._build_value(value)
            kwargs['value'] = value
        obj = cls(**kwargs)
        obj.save()
        return obj
    def get_html(self):
        s = self.name
        if self.value is not None:
            s = u'="%s"' % (self.value)
        return s
        
class HtmlObjectDefinition(models.Model):
    tag = models.CharField(max_length=100, blank=True, null=True)
    attributes = models.ManyToManyField(HtmlAttributeDefinition)
    class Meta:
        abstract = True
    @classmethod
    def create(cls, **kwargs):
        attributes = kwargs.get('attributes')
        if 'attributes' in kwargs:
            del kwargs['attributes']
        obj = cls(**kwargs)
        obj.save()
        if isinstance(attributes, dict):
            for k, v in attributes.iteritems():
                self.add_attribute(name=k, value=v, do_save=False)
        elif is_iterable(attributes):
            for akwargs in attributes:
                akwargs['do_save'] = False
                self.add_attribute(**akwargs)
        obj.save()
        return obj
    def add_attribute(self, **kwargs):
        name = kwargs.get('name')
        value = kwargs.get('value')
        do_save = kwargs.get('do_save', True)
        if 'do_save' in kwargs:
            del kwargs['do_save']
        q = self.attributes.filter(name__iexact=name)
        if len(q) == 1:
            attrib = q[0]
            if value is not None:
                attrib.add_value(value)
            return attrib
        attrib = HtmlAttributeDefinition.create(**kwargs)
        self.attributes.add(attrib)
        if do_save:
            self.save()
    def get_html(self, child_nodes=None):
        s = u'<%s' % (self.tag)
        if self.attributes.all().count():
            alist = []
            for a in self.attributes.all():
                alist.append(a.get_html())
            s = u'%s %s>' % (s, u' '.join([astr for astr in alist]))
        if not is_iterable(child_nodes):
            child_nodes = [child_nodes]
        child_html = []
        for child_node in child_nodes:
            if hasattr(child_node, 'get_html'):
                child_html.append(child_node.get_html())
            elif isinstance(child_node, basestring):
                child_html.append(unicode(child_node))
        if len(child_html):
            child_s = u'\n'.join(child_html)
            s = u'%s\n%s\n' % (s, child_s)
        s = u'%s</%s>\n' % (s, self.tag)
        return s
        
    
class WidgetDefinition(HtmlObjectDefinition):
    name = models.CharField(max_length=100, unique=True)
    parent_widget_definition = models.ForeignKey(self, 
                                                 blank=True, 
                                                 null=True, 
                                                 related_name='child_widget_definitions')
    _tag_default = 'input'
    input_type = None
    @classmethod
    def create(cls, **kwargs):
        tag = kwargs.get('tag')
        if tag is None:
            tag = getattr(cls, '_tag_default')
        kwargs['tag'] = tag
        input_type = kwargs.get('input_type', getattr(cls, 'input_type'))
        obj = super(WidgetDefinition, cls).create(**kwargs)
        if input_type is not None:
            obj.add_attribute(name='input_type', value=input_type)
        return obj
    def get_html(self):
        q = self.child_widget_definitions.all()
        if not q.exists():
            q = None
        return super(WidgetDefinition, self).get_html(child_nodes=q)

    
class WizardDefinition(models.Model):
    name = models.CharField(max_length=100)
    
class WizardPageDefinition(models.Model):
    title = models.CharField(max_length=100)
    page_number = models.IntegerField(default=0)
    wizard_definition = models.ForeignKey(WizardDefinition, 
                                          related_name='page_definitions')

class WizardFieldDefinition(models.Model):
    name = models.CharField(max_length=100)
    html_safe_name = models.SlugField()
    
    
    
