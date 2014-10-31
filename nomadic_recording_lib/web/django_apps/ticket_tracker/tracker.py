import json
from django.db import models
from models_default_builder.models import build_defaults

from ticket_tracker.staff_user import StaffGroup, StaffUser
    
class Tracker(models.Model):
    name = models.CharField(max_length=100)
    message_handler = models.ForeignKey('ticket_tracker.EmailHandler', 
                                        related_name='trackers', 
                                        blank=True, 
                                        null=True)
    hidden_data_delimiter = models.CharField(max_length=100, 
                                             default='\n_STAFF_ONLY_DATA_\n')
    def get_staff_users(self, permission_type=None):
        if not permission_type:
            q = self.permissions.all()
        else:
            q = self.permissions.filter(permission_item__name=permission_type)
        all_ids = set()
        for p in q:
            u_q = p.get_all_users()
            l = u_q.values('id')
            all_ids |= set([d['id'] for d in l])
        return StaffUser.objects.filter(id__in=all_ids)
    def parse_hidden_data(self, text):
        delim = self.hidden_data_delimiter
        d = {'body':None, 'data':None, 'extra':[]}
        if delim not in text:
            d['body'] = text
        d['body'], d['data'], extra = s.split(delim, 2)
        while delim in extra:
            s, data, extra = s.split(delim, 2)
            d['extra'].append({'text':s, 'data':data})
        return d
    def build_hidden_data(self, text, data):
        delim = self.hidden_data_delimiter
        if not isinstance(data, basestring):
            data = json.dumps(data)
        return delim.join([text, data, ''])
    def match_message(self, **kwargs):
        msg = kwargs.get('message')
        parsed_templates = kwargs.get('parsed_templates')
        q = self.tickets.all()
        for tname, tdata in parsed_templates.iteritems():
            for qstr, val in tdata['subject'].iteritems():
                if 'ticket' in qstr:
                    q = q.filter(**{qstr:val})
        count = q.count()
        if count == 1:
            ticket = q[0]
            return ticket.add_message_from_email(**kwargs)
        return False
    
class TrackerPermissionItem(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    inherited = models.ManyToManyField('self', blank=True, null=True)
    @classmethod
    def default_builder_create(cls, **kwargs):
        ckwargs = kwargs.copy()
        inherited = ckwargs.get('inherited')
        if inherited is not None:
            del ckwargs['inherited']
        obj = cls(**ckwargs)
        obj.save()
        if inherited is not None:
            for other in inherited:
                other_obj = cls.objects.get(name=other)
                obj.inherited.add(other_obj)
            obj.save()
    def default_builder_update(self, **kwargs):
        for fname, fval in kwargs.iteritems():
            if fname == 'inherited':
                for othername in fval:
                    self.inherited.add(TrackerPermissionItem.get(name=othername))
            else:
                setattr(self, fname, fval)
    def get_inherited(self):
        l = self.inherited.all().values('id')
        ids = set([d['id'] for d in l])
        ids.add(self.id)
        return TrackerPermissionItem.objects.filter(id__in=ids)
    def __unicode__(self):
        desc = self.description
        if desc:
            return desc
        return self.name
    
tracker_item_defaults = ({'name':'read', 'description':'Can Read Posts'}, 
                         {'name':'write', 'description':'Can Reply', 'inherited':['read']}, 
                         {'name':'modify', 'description':'Can Modify Posts', 'inherited':['write']}, 
                         {'name':'take', 'description':'Can Take Ticket as Assignment', 'inherited':['write']}, 
                         {'name':'assign', 'description':'Can Assign Tickets to Staff', 'inherited':['take']}, 
                         {'name':'status_change', 'description':'Can Change Ticket Status', 'inherited':['write']}, 
                         {'name':'all', 'description':'All Permissions (SuperUser)', 'inherited':['read', 
                                                                                                  'write', 
                                                                                                  'modify', 
                                                                                                  'take', 
                                                                                                  'assign', 
                                                                                                  'status_change']})

build_defaults({'model':TrackerPermissionItem, 'unique':'name', 'defaults':tracker_item_defaults})
    

    
class TrackerGlobalPermission(models.Model):
    permission_item = models.ForeignKey(TrackerPermissionItem, related_name='global_permissions')
    users = models.ManyToManyField(StaffUser, null=True, blank=True)
    groups = models.ManyToManyField(StaffGroup, null=True, blank=True)
    def get_inherited(self):
        q = self.permission_item.get_inherited()
        l = q.values('id')
        ids = set([d['id'] for d in l])
        ids.add(self.id)
        return TrackerGlobalPermission.objects.filter(id__in=ids)
    def __unicode__(self):
        return unicode(self.permission)
        
class TrackerPermission(models.Model):
    permission_item = models.ForeignKey(TrackerPermissionItem, related_name='permissions')
    users = models.ManyToManyField(StaffUser, null=True, blank=True)
    groups = models.ManyToManyField(StaffGroup, null=True, blank=True)
    tracker = models.ForeignKey(Tracker, related_name='permissions')
    def get_inherited(self):
        q = self.permission_item.get_inherited()
        l = q.values('id')
        ids = set([d['id'] for d in l])
        ids.add(self.id)
        return TrackerPermission.objects.filter(id__in=ids, tracker=self.tracker)
    def get_all_users(self):
        q = self.get_inherited()
        user_ids = set()
        for p in q:
            for user in p.users.all():
                user_ids.add(user.id)
            for group in p.groups.all():
                for user in group.users:
                    user_ids.add(user.id)
        return StaffUser.objects.filter(id__in=user_ids)
    def __unicode__(self):
        return unicode(self.permission_item)

MODELS = (Tracker, TrackerPermissionItem, TrackerGlobalPermission, TrackerPermission)
