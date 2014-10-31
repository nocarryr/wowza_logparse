from django.db import models
from django.contrib.auth.models import User, Group

class StaffGroup(models.Model):
    group = models.OneToOneField(Group)
    @property
    def users(self):
        ids = set()
        for u in User.groups.all():
            try:
                staff_u = StaffUser.objects.get(user=u)
            except StaffUser.DoesNotExist:
                staff_u = StaffUser(user=u)
                staff_u.save()
            ids.add(staff_u.id)
        return StaffUser.objects.filter(id__in=ids)
    def __unicode__(self):
        return unicode(self.group)
    
class StaffUser(models.Model):
    user = models.OneToOneField(User)
    @property
    def groups(self):
        ids = set()
        for g in self.user.groups.all():
            try:
                staff_g = StaffGroup.objects.get(group=g)
            except StaffGroup.DoesNotExist:
                staff_g = StaffGroup(group=g)
                staff_g.save()
            ids.add(staff_g.id)
        return StaffGroup.objects.filter(id__in=ids)
    def __unicode__(self):
        return unicode(self.user)
    
MODELS = (StaffGroup, StaffUser)
