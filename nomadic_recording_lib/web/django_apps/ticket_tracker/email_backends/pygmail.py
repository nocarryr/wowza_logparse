import gmail
from .smtp import DjangoEmailMessage, SmtpBackend

class PyGMailError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)
        
class PyGMailBackend(SmtpBackend):
    def _do_login(self):
        c = self.connection
        if c is None:
            c = gmail.login(self.username, self.password)
            self.connection = c
        return True
    def _do_logout(self):
        c = self.connection
        if c is None:
            return True
        c.logout()
    def _check_logged_in(self):
        c = self.connection
        if c is None:
            return False
        return c.logged_in
    def _build_message(self, **kwargs):
        msg = kwargs.get('_message')
        if isinstance(msg, gmail.Message):
            kwargs.update(dict(sender=msg.fr, 
                               recipients=msg.to.split(', '), 
                               datetime=msg.sent_at))
        elif isinstance(msg, DjangoEmailMessage):
            msgs = [m for m in self.get_sent_messages(header=('Message-ID', msg._message['Message-ID']))]
            if len(msgs) != 1:
                raise PyGMailError('could not retreive the message we just sent: %r' % ([msg, msgs]))
            msgs[0].fetch()
            return self._build_message(_message=msgs[0])
        return super(PyGMailBackend, self)._build_message(**kwargs)
    def get_new_messages(self, **kwargs):
        mark_as_read = kwargs.get('mark_as_read')
        if mark_as_read:
            del kwargs['mark_as_read']
        if not self.logged_in:
            self.login()
        c = self.connection
        kwargs.setdefault('unread', True)
        msgs = c.inbox().mail(**kwargs)
        for msg in msgs:
            msg.fetch()
            message = self._build_message(_message=msg)
            if mark_as_read:
                msg.read()
            yield message
    def get_sent_messages(self, **kwargs):
        if not self.logged_in:
            self.login()
        c = self.connection
        msgs = c.sent_mail().mail(**kwargs)
        for msg in msgs:
            msg.fetch()
            yield self._build_message(_message=msg)
