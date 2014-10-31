import traceback
if False:
    import smtplib
    import socket
    smtplib.SMTPBroken = smtplib.SMTP
    class SMTPFixed(smtplib.SMTPBroken):
        def _get_socket(self, host, port, timeout):
            if self.debuglevel > 0:
                print>>smtplib.stderr, 'connect:', (host, port)
            return socket.create_connection((host, port), timeout)
    smtplib.SMTP = SMTPFixed
from django.core.mail import get_connection, send_mail
from django.core.mail import EmailMessage as _DjangoEmailMessage
from .base import BaseEmailBackend

django_backend = 'django.core.mail.backends.smtp.EmailBackend'

class DjangoEmailMessage(_DjangoEmailMessage):
    def message(self):
        self._message = msg = super(DjangoEmailMessage, self).message()
        return msg

class SmtpBackend(BaseEmailBackend):
    def __init__(self, **kwargs):
        super(SmtpBackend, self).__init__(**kwargs)
        c = get_connection(django_backend, 
                           host=self.hostname, 
                           port=self.port, 
                           username=self.username, 
                           password=self.password, 
                           use_tls=self.use_ssl)
        self.smtp_connection = c
    def _build_message(self, **kwargs):
        msg = kwargs.get('_message')
        if isinstance(msg, DjangoEmailMessage):
            kwargs['message_id'] = msg._message['Message-ID']
            kwargs['datetime'] = msg._message['Date']
            kwargs['sender'] = msg.from_email
            kwargs['recipients'] = msg.to
            kwargs['subject'] = msg.subject
            kwargs['body'] = msg.body
        return super(SmtpBackend, self)._build_message(**kwargs)
    def send_message(self, **kwargs):
        c = self.smtp_connection
        sender = kwargs.get('sender')
        recipients = kwargs.get('recipients')
        subject = kwargs.get('subject')
        body = kwargs.get('body')
        if not sender:
            sender = self.email_address
        if isinstance(recipients, basestring):
            recipients = [recipients]
        msg = DjangoEmailMessage(subject=subject, 
                                 body=body, 
                                 from_email=sender, 
                                 to=recipients, 
                                 connection=c)
        c.open()
        try:
            msg.send()
        except:
            traceback.print_exc()
        finally:
            c.close()
        message = self._build_message(_message=msg)
        return message
