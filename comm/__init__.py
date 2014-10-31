import pkgutil

IO_CLASSES = {}

iter = pkgutil.iter_modules(__path__)
for imp, name, ispkg in iter:
    mod = __import__('.'.join([__name__, name]), fromlist='dummy')
    loader = mod.__dict__.get('IO_LOADER')
    if not loader:
        continue
    if type(loader) in [list, tuple]:
        for l in loader:
            IO_CLASSES['.'.join([name, l.__name__])] = l
    elif type(loader) == dict:
        for lkey, lval in loader.iteritems():
            IO_CLASSES['.'.join([name, lkey])] = lval
    else:
        IO_CLASSES[name] = loader

