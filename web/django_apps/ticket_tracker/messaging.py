import traceback
import email.utils

from django.core.mail import get_connection, EmailMessage
from django.db import models

from models_default_builder.models import build_defaults
from utils import template_parser

import email_template_defaults

from email_backends import build_backend

class MessagingError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class MessageContact(models.Model):
    real_name = models.CharField(max_length=200, blank=True, null=True)
    email = models.EmailField(max_length=254, unique=True)
    @classmethod
    def create(cls, email_str):
        email_str = unicode(email_str)
        name, addr = email.utils.parseaddr(email_str)
        if not name:
            name = None
        q = cls.objects.filter(email__iexact=addr)
        if q.exists():
            obj = q[0]
            if name and name != obj.real_name:
                obj.real_name = name
                obj.save()
        else:
            obj = cls(real_name=name, email=addr)
            obj.save()
        return obj
    def __unicode__(self):
        name = self.real_name
        if name is None:
            name = u''
        return email.utils.formataddr((name, self.email))
    
class Message(models.Model):
    message_id = models.CharField(max_length=100, unique=True)
    thread_id = models.CharField(max_length=100, blank=True, null=True)
    datetime = models.DateTimeField()
    sender = models.ForeignKey(MessageContact, 
                               related_name='message_as_sender')
    recipients = models.ManyToManyField(MessageContact, 
                                        related_name='message_as_recipient', 
                                        null=True)
    subject = models.CharField(max_length=300)
    body = models.TextField()
    @classmethod
    def create_from_backend(cls, msg):
        sender = MessageContact.create(msg.sender)
        recipients = []
        for recipient in msg.recipients:
            recipients.append(MessageContact.create(recipient))
        obj = cls(message_id=unicode(msg.message_id), 
                  thread_id=unicode(msg.thread_id), 
                  datetime=msg.datetime_utc, 
                  sender=sender, 
                  subject=unicode(msg.subject), 
                  body=msg.body.decode('cp1252'))
        obj.save()
        for r in recipients:
            obj.recipients.add(r)
        obj.save()
        return obj
        
class MailUserConf(models.Model):
    username = models.CharField(max_length=200)
    password = models.CharField(max_length=200)
    def __unicode__(self):
        return self.username
    
class MailConfigBase(models.Model):
    login = models.ForeignKey(MailUserConf, blank=True, null=True)
    hostname = models.CharField(max_length=200, blank=True, null=True)
    port = models.IntegerField(blank=True, null=True)
    use_ssl = models.BooleanField(default=False)
    class Meta:
        abstract = True
    def save(self, *args, **kwargs):
        def do_save():
            super(MailConfigBase, self).save(*args, **kwargs)
        self.build_defaults()
        do_save()
        
class IncomingMailConfig(MailConfigBase):
    protocol = models.CharField(max_length=10, 
                                choices=(('pop3', 'POP 3'), 
                                         ('imap', 'IMAP'), 
                                         ('gmail', 'GMail')), 
                                default='gmail')
    check_interval = models.IntegerField(default=5, 
                                         help_text='Interval in minutes to check for new messages')
    last_check = models.DateTimeField(blank=True, null=True, editable=False)
    def build_defaults(self):
        if self.protocol == 'gmail':
            if not self.hostname:
                self.hostname = 'imap.gmail.com'
            if not self.port:
                self.port = 993
            if not self.use_ssl:
                self.use_ssl = True
    
class OutgoingMailConfig(MailConfigBase):
    protocol = models.CharField(max_length=10, 
                                choices=(('smtp', 'SMTP'), 
                                         ('gmail', 'GMail')), 
                                default='gmail')
    def build_defaults(self):
        if self.protocol == 'gmail':
            if not self.hostname:
                self.hostname = 'smtp.gmail.com'
            if not self.port:
                self.port = 587
            if not self.use_ssl:
                self.use_ssl = True
    
class EmailHandler(models.Model):
    email_address = models.EmailField(help_text='All outgoing emails will use this address')
    incoming_mail_configuration = models.ForeignKey(IncomingMailConfig, blank=True, null=True)
    outgoing_mail_configuration = models.ForeignKey(OutgoingMailConfig, blank=True, null=True)
    timezone_name = models.CharField(max_length=100)
    all_messages = models.ManyToManyField(Message, blank=True, null=True)
    def parse_message_templates(self, msg):
        d = {}
        for tmpl in self.email_message_templates.exclude(name='auto_response'):
            d[tmpl.name] = tmpl.parse_message(msg)
        return d
    def add_message(self, message):
        q = Message.objects.filter(message_id=message.message_id)
        if q.exists():
            return
        dbmsg = Message.create_from_backend(message)
        self.all_messages.add(dbmsg)
        self.save()
        matched = False
        parsed_templates = self.parse_message_templates(message)
        q = self.trackers.all()
        for tname, tdata in parsed_templates.iteritems():
            for qstr, val in tdata['subject'].iteritems():
                if 'tracker' in qstr:
                    q = q.filter(**{qstr:val})
        for tracker in q:
            r = tracker.match_message(message=dbmsg, parsed_templates=parsed_templates)
            if r:
                matched = True
        if not_matched:
            pass
    def send_message(self, **kwargs):
        conf = self.outgoing_mail_configuration
        bkwargs = dict(username=conf.login.username, 
                       password=conf.login.password, 
                       hostname=conf.hostname, 
                       port=conf.port, 
                       use_ssl=conf.use_ssl, 
                       inbox_timezone=self.timezone_name, 
                       email_address=self.email_address)
        for key in bkwargs.keys():
            if type(bkwargs[key]) == unicode:
                bkwargs[key] = str(bkwargs[key])
        b = build_backend(conf.protocol, **bkwargs)
        msg = b.send_message(**kwargs)
        return msg
    def save(self, *args, **kwargs):
        def do_save():
            super(EmailHandler, self).save(*args, **kwargs)
        if self.pk is None:
            do_save()
        if not self.email_message_templates.count():
            for dtmp in DefaultEmailMessageTemplate.objects.all():
                tmpl = EmailMessageTemplate.objects.create(name=dtmp.name, 
                                                           subject=dtmp.subject, 
                                                           body=dtmp.body, 
                                                           handler=self)
        do_save()
        
class EmailMessageTemplateBase(models.Model):
    subject = models.CharField(max_length=300, blank=True, null=True, 
                               help_text='Message subject contents (can contain template tags)')
    body = models.TextField(blank=True, null=True, 
                            help_text='Message body contents (can contain template tags)')
    class Meta:
        abstract = True
    def __unicode__(self):
        if hasattr(self, 'name'):
            return self.name
        return super(EmailMessageTemplateBase, self).__unicode__()
        
class DefaultEmailMessageTemplate(EmailMessageTemplateBase):
    name = models.CharField(max_length=100, unique=True, 
                            help_text='Template name (not used as part of the generated message)')
class EmailMessageTemplate(EmailMessageTemplateBase):
    name = models.CharField(max_length=100, 
                            help_text='Template name (not used as part of the generated message)')
    handler = models.ForeignKey(EmailHandler, related_name='email_message_templates')
    def parse_message(self, msg):
        d = {}
        for msgattr in ['subject', 'body']:
            parser = template_parser.TemplatedStringParser(template=getattr(self, msgattr))
            parser.string_to_parse = getattr(msg, msgattr)
            d[msgattr] = parser.get_parsed_values()
        return d
    

build_defaults({'model':DefaultEmailMessageTemplate, 
                'unique':'name', 
                'defaults':email_template_defaults.defaults})

    

def get_messages(handler_id=None, msg_type='unread', **kwargs):
    q = EmailHandler.objects.all()
    if type(handler_id) in [list, tuple, set]:
        q = q.filter(id__in=handler_id)
    elif handler_id is not None:
        q = q.filter(id__exact=handler_id)
    d = {}
    kwargs.setdefault('mark_as_read', True)
    for h in q:
        d[h.id] = []
        conf = h.incoming_mail_configuration
        if conf.protocol == 'gmail':
            bkwargs = dict(username=conf.login.username, 
                           password=conf.login.password, 
                           inbox_timezone=h.timezone_name)
            b = build_backend('gmail', **bkwargs)
            if msg_type == 'unread':
                msg_iter = b.get_new_messages
            elif msg_type == 'sent':
                msg_iter = b.get_sent_messages
            else:
                raise MessagingError('invalid message type: %r' % (msg_type))
            for msg in msg_iter(**kwargs):
                try:
                    h.add_message(msg)
                except:
                    traceback.print_exc()
                    return msg
                d[h.id].append(msg)
    return d

MODELS = (MessageContact, Message, MailUserConf, MailConfigBase, 
          IncomingMailConfig, OutgoingMailConfig, EmailHandler,
          EmailMessageTemplateBase, DefaultEmailMessageTemplate,
          EmailMessageTemplate)
