from base import BaseEmailBackend
from smtp import SmtpBackend
from pygmail import PyGMailBackend

BACKENDS = {'smtp':SmtpBackend, 'gmail':PyGMailBackend}

def build_backend(name, **kwargs):
    cls = BACKENDS[name]
    return cls(**kwargs)
