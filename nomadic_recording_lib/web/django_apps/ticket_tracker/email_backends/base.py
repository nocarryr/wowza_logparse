import email
import datetime
import pytz

class EmailMessage(object):
    attr_list = ['message_id', 'thread_id', 'sender', 'recipients', 
                 'subject', 'body', 'datetime_utc']
    def __init__(self, **kwargs):
        self.backend = kwargs.get('backend')
        self._message = kwargs.get('_message')
        for attr in self.attr_list:
            if attr not in kwargs:
                continue
            val = kwargs.get(attr)
            if attr == 'datetime_utc':
                if not isinstance(val, datetime.datetime) or getattr(val, 'tzinfo', None) is None:
                    val = self.build_datetime_utc(val, is_utc=True)
            setattr(self, attr, val)
        if not getattr(self, 'datetime_utc', None):
            dt = kwargs.get('datetime')
            self.datetime_utc = self.build_datetime_utc(dt, is_utc=False)
    def __getattr__(self, attr):
        return self._get_message_attr(attr)
    def _get_message_attr(self, attr):
        return getattr(self._message, attr)
    def build_datetime_utc(self, value, is_utc=True):
        tz = self.backend.inbox_timezone
        dt = None
        dt_u = None
        if type(value) in [int, float]:
            if is_utc:
                dt_u = datetime.datetime.fromtimestamp(value, pytz.utc)
            else:
                dt = datetime.datetime.fromtimestamp(value, tz)
        elif isinstance(value, datetime.datetime):
            if value.tzinfo is not None:
                dt_u = value.tzinfo.normalize(value)
            elif is_utc:
                dt_u = pytz.utc.localize(value)
            else:
                dt = tz.localize(value)
        elif isinstance(value, basestring):
            tt = email.utils.parsedate_tz(value)
            ts = email.utils.mktime_tz(tt)
            dt_u = datetime.datetime.fromtimestamp(ts).replace(tzinfo=pytz.utc)
        if dt and not dt_u:
            dt_u = pytz.utc.normalize(dt)
        return dt_u
    def get_data(self):
        attrs = self.attr_list
        d = {}
        for attr in attrs:
            d[attr] = getattr(self, attr)
        return d
        
class BaseEmailBackend(object):
    def __init__(self, **kwargs):
        if not hasattr(self, '_connection'):
            self._connection = None
        self.username = kwargs.get('username')
        self.password = kwargs.get('password')
        self.hostname = kwargs.get('hostname')
        tz = kwargs.get('inbox_timezone')
        if isinstance(tz, basestring):
            tz = pytz.timezone(tz)
        self.inbox_timezone = tz
        self.port = kwargs.get('port')
        self.use_ssl = kwargs.get('use_ssl')
        self.email_address = kwargs.get('email_address')
    @property
    def connection(self):
        return self._connection
    @connection.setter
    def connection(self, value):
        if value == self._connection:
            return
        self._connection = value
        self._on_connection_set(value)
    @property
    def logged_in(self):
        return self._check_logged_in()
    def _on_connection_set(self, c):
        pass
    def _build_message(self, **kwargs):
        kwargs['backend'] = self
        return EmailMessage(**kwargs)
    def login(self):
        if self.logged_in:
            return True
        self._do_login()
        return self.logged_in
    def logout(self):
        if not self.logged_in:
            return True
        self._do_logout()
        return not self.logged_in
    def get_new_messages(self, **kwargs):
        raise NotImplementedError()
    def send_message(self, **kwargs):
        '''
        params:
            sender:
            recipients: 
            subject:
            body: 
        '''
        raise NotImplementedError()
    def _do_login(self):
        raise NotImplementedError()
    def _do_logout(self):
        raise NotImplementedError()
    def _check_logged_in(self):
        raise NotImplementedError()
