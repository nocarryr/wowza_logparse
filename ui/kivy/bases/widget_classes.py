import pkgutil

from kivy import uix

class Widgets(object):
    pass

iter = pkgutil.iter_modules(uix.__path__)
for imp, name, ispkg in iter:
    if name not in ['__init__', 'svg', 'rst']:
        #print 'importing ', name, ', path:', '.'.join([uix.__name__, name])
        mod = __import__('.'.join([uix.__name__, name]), fromlist='dummy')
        for key, val in mod.__dict__.iteritems():
            if key.lower() == name or 'FileChooser' in key:
                setattr(Widgets, key, val)
            
    

    
