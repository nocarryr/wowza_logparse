import datetime

from django.db import models
from django.utils import timezone

from ticket_tracker.messaging import Message

MESSAGE_DATE_INCREMENT = datetime.timedelta(microseconds=1)

class Contact(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=254, unique=True)
    class Meta:
        unique_together = (('first_name', 'last_name'), )
    
class TicketStatus(models.Model):
    name = models.CharField(max_length=30)
    ticket_active = models.BooleanField()
    
class Ticket(models.Model):
    tracker = models.ForeignKey('ticket_tracker.Tracker', related_name='tickets')
    contact = models.ForeignKey(Contact)
    initial_message = models.OneToOneField('ticket_tracker.ContactMessage', related_name='initial_message_parent_ticket')
    status = models.ForeignKey(TicketStatus, blank=True)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(default=timezone.now())
    modified = models.DateTimeField(blank=True)
    class Meta:
        get_latest_by = 'created'
        ordering = ['created']
    def get_message_queryset(self, msg_type='all'):
        if msg_type == 'all':
            mgr = self.message_base_set
        elif msg_type == 'contact':
            mgr = self.contact_messages
        elif msg_type == 'staff':
            mgr = self.staff_messages
        return mgr.all()
    def get_message_dict(self, **kwargs):
        mgrs = {'contact':self.contact_messages, 
                'staff':self.staff_messages}
        mgr_filters = {}
        all_filters = kwargs.get('all_filters')
        for mgr_name in mgrs.keys():
            key = '_'.join([mgr_name, 'filters'])
            if key not in kwargs:
                continue
            mgr_filters[mgr_name] = kwargs.get(key)
        d = {}
        for mgr_name, mgr in mgrs.iteritems():
            if mgr_filters.get(mgr_name) == 'None':
                continue
            q = mgr.all()
            if all_filters is not None:
                q = q.filter(**all_filters)
            for msg in q:
                d['all'][msg.date] = msg
                d[mgr_name][msg.date] = msg
        return d
    @classmethod
    def create(cls, **kwargs):
        ## TODO: 
        pass
    def add_message_from_email(self, **kwargs):
        msg = kwargs.get('message')
        parsed_templates = kwargs.get('parsed_templates')
        tracker = self.tracker
        users = tracker.get_staff_users('write')
        mkwargs = {}
        cls = None
        if self.contact.email.lower() == msg.sender.email.lower():
            cls = ContactMessage
            exists_query = cls.objects.all()
        if cls is None:
            try:
                user = users.get(user__email__iexact=msg.sender.email)
                mkwargs['user'] = user
                cls = StaffMessage
                exists_query = cls.objects.filter(user=user)
            except StaffUser.DoesNotExist:
                pass
        if cls is None:
            return False
        exists_query = exists_query.filter(date=msg.datetime, 
                                           email_message__subject=msg.subject)
        if exists_query.exists():
            return True
        mkwargs.update(dict(email_message=msg, ticket=self))
        msg = MessageBase.create_from_email(cls, **mkwargs)
        self.save()
        return True
    def save(self, *args, **kwargs):
        def do_save():
            super(Ticket, self).save(*args, **kwargs)
        self.modified = timezone.now()
        do_save()
    
class MessageBase(models.Model):
    date = models.DateTimeField(blank=True, null=True)
    email_message = models.OneToOneField(Message, 
                                         related_name='ticket_message_reference', 
                                         blank=True, null=True)
    subject = models.CharField(max_length=300, null=True, blank=True)
    text = models.TextField()
    hidden_data = models.TextField(blank=True, null=True)
    class Meta:
        get_latest_by = 'date'
        ordering = ['date']
    @staticmethod
    def create_from_email(cls, **kwargs):
        msg = kwargs.get('email_message')
        ticket = kwargs.get('ticket')
        d = ticket.tracker.parse_hidden_data(msg.body)
        kwargs.setdefault('text', d['body'])
        kwargs.setdefault('hidden_data', d['data'])
        kwargs.setdefault('subject', msg.subject)
        kwargs.setdefault('date', msg.datetime)
        obj = cls(**kwargs)
        obj.save()
        return obj
    def get_queryset_from_ticket(self):
        try:
            t = self.ticket
        except:
            return False
        return t.message_base_set.all()
    def check_date_unique(self):
        if self.pk is None:
            return
        dt = self.date
        if not dt:
            return
        q = self.get_queryset_from_ticket()
        if q is False:
            return
        q = q.exclude(id__exact=self.id)
        _q = q.filter(date=self.date)
        if not _q.exists():
            return
        new_date += MESSAGE_DATE_INCREMENT
        next_q = q.filter(date=new_date)
        self._do_save()
        for other in next_q:
            other.save()
    def _do_save(self):
        args = getattr(self, '_do_save_args', [])
        kwargs = getattr(self, '_do_save_kwargs', {})
        super(MessageBase, self).save(*args, **kwargs)
    def save(self, *args, **kwargs):
        self._do_save_args = args
        self._do_save_kwargs = kwargs
        if not self.date:
            if self.email_message:
                self.date = self.email_message.datetime
            else:
                self.date = timezone.now()
        if self.pk is None:
            self._do_save()
        self.check_date_unique()
        self._do_save()
    
class ContactMessage(MessageBase):
    ticket = models.ForeignKey(Ticket, related_name='contact_messages')
    @property
    def contact(self):
        return self.ticket.contact

    
class StaffMessage(MessageBase):
    ticket = models.ForeignKey(Ticket, related_name='staff_messages')
    user = models.ForeignKey('ticket_tracker.StaffUser')
    for_staff_only = models.BooleanField(default=False, 
                                         help_text='Visible by staff only.  Not sent via email.')

MODELS = (Contact, TicketStatus, Ticket, MessageBase,
          ContactMessage, StaffMessage)
