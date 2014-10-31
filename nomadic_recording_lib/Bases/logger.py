from __future__ import print_function
import sys
import os, os.path
import datetime
import logging
from logging.handlers import TimedRotatingFileHandler

from BaseObject import BaseObject
from config import Config

LEVELS = ('debug', 'info', 'warning', 'error', 'critical')

class Logger(BaseObject, Config):
    _confsection = 'LOGGING'
    _Properties = {'log_mode':dict(default='stdout', entries=['basicConfig', 
                                                              'DailyRotatingFile', 
                                                              'null', 
                                                              'stdout']), 
                   'log_filename':dict(type=str), 
                   'log_level':dict(default='info', fformat='_format_log_level'), 
                   'log_format':dict(default='%(asctime)-15s %(levelname)-10s %(message)s')}
    _confkeys = ['log_mode', 'log_filename', 'log_level', 'log_format']
    def __init__(self, **kwargs):
        BaseObject.__init__(self, **kwargs)
        Config.__init__(self, **kwargs)
        logger_setup = kwargs.get('logger_setup', self.GLOBAL_CONFIG.get('logger_setup'))
        if logger_setup is not None:
            kwargs = logger_setup
        if not kwargs.get('log_filename'):
            appname = self.GLOBAL_CONFIG.get('app_name')
            if appname is not None:
                kwargs.setdefault('log_filename', os.path.expanduser('~/%s.log' % (appname)))
        self._logger = None
        use_conf = kwargs.get('use_conf', True)
        if use_conf:
            d = self.get_conf()
        else:
            d = {}
        for key in self._confkeys:
            val = d.get(key)
            if val is None:
                val = kwargs.get(key)
            if val is None:
                continue
            setattr(self, key, val)
        self.logger_kwargs = kwargs.get('logger_kwargs', {})
        self.set_logger()
        self.bind(property_changed=self._on_own_property_changed)
    def __call__(self, *args, **kwargs):
        m = getattr(self, 'info', None)
        if callable(m):
            m(*args, **kwargs)
    def _format_log_level(self, value):
        if type(value) == str and value.isdigit():
            value = int(value)
        if type(value) == int:
            value = LEVELS[value]
        return value
    def set_logger(self, name=None):
        if name is None:
            name = self.log_mode
        cls = LOGGERS[name]
        keys = ['filename', 'level', 'format']
        lkwargs = dict(zip(keys, [getattr(self, '_'.join(['log', key])) for key in keys]))
        if type(lkwargs['level']) == str:
            lkwargs['level'] = lkwargs['level'].upper()
        lkwargs.update(self.logger_kwargs)
        self._logger = cls(**lkwargs)
        for key in ['log', 'debug', 'info', 'warning', 'error', 'critical', 'exception']:
            m = getattr(self._logger, key)
            setattr(self, key, m)
    def close(self):
        self._logger.close()
    def _on_own_property_changed(self, **kwargs):
        prop = kwargs.get('Property')
        value = kwargs.get('value')
        if prop.name == 'log_level':
            self._logger.level = value
    
def format_msg(*args):
    if len(args) <= 1:
        return str(args[0])
    return ', '.join([str(arg) for arg in args])
    
class StdoutLogger(object):
    dt_fmt_str = '%Y-%m-%d %H:%M:%S,%f'
    def __init__(self, **kwargs):
        pass
    def log(self, level, *args, **kwargs):
        now = datetime.datetime.now()
        msg = format_msg(*args)
        tstr = now.strftime(self.dt_fmt_str)
        print ('%s %s: %s' % (tstr, level, msg), file=sys.stdout)
        sys.stdout.flush()
    def debug(self, *args, **kwargs):
        self.log('debug', *args, **kwargs)
    def info(self, *args, **kwargs):
        self.log('info', *args, **kwargs)
    def warning(self, *args, **kwargs):
        self.log('warning', *args, **kwargs)
    def error(self, *args, **kwargs):
        self.log('error', *args, **kwargs)
    def critical(self, *args, **kwargs):
        self.log('critical', *args, **kwargs)
    def exception(self, *args, **kwargs):
        self.log('exception', *args, **kwargs)
    def close(self):
        pass
        
class BuiltinLoggingLogger(object):
    def log(self, level, *args, **kwargs):
        msg = format_msg(*args)
        logging.log(level, msg, **kwargs)
    def debug(self, *args, **kwargs):
        msg = format_msg(*args)
        logging.debug(msg, **kwargs)
    def info(self, *args, **kwargs):
        msg = format_msg(*args)
        logging.info(msg, **kwargs)
    def warning(self, *args, **kwargs):
        msg = format_msg(*args)
        logging.warning(msg, **kwargs)
    def error(self, *args, **kwargs):
        msg = format_msg(*args)
        logging.error(msg, **kwargs)
    def critical(self, *args, **kwargs):
        msg = format_msg(*args)
        logging.critical(msg, **kwargs)
    def exception(self, *args, **kwargs):
        msg = format_msg(*args)
        logging.exception(msg, **kwargs)
    def close(self):
        logging.shutdown()
        
class BasicConfigLogger(BuiltinLoggingLogger):
    def __init__(self, **kwargs):
        logging.basicConfig(**kwargs)
        
class DailyRotatingFileLogger(BuiltinLoggingLogger):
    def __init__(self, **kwargs):
        fn = kwargs.get('filename')
        lvl = getattr(logging, kwargs.get('level').upper())
        fmt = kwargs.get('format')
        logH = TimedRotatingFileHandler(fn, when='midnight')
        logF = logging.Formatter(fmt)
        logH.setFormatter(logF)
        logger = logging.getLogger()
        logger.addHandler(logH)
        logger.setLevel(lvl)
        
class NullLogger(BuiltinLoggingLogger):
    def __init__(self, **kwargs):
        logging._acquireLock()
        try:
            root = logging.getLogger()
            if len(root.handlers):
                for hdlr in root.handlers[:]:
                    root.removeHandler(hdlr)
            hdlr = logging.NullHandler()
            root.addHandler(hdlr)
        finally:
            logging._releaseLock()
    
LOGGERS = {'stdout':StdoutLogger, 
           'basicConfig':BasicConfigLogger, 
           'DailyRotatingFile':DailyRotatingFileLogger, 
           'null':NullLogger}
