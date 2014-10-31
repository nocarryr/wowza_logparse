import pkgutil

view_classes = {}

iter = pkgutil.iter_modules(__path__)
for imp, name, ispkg in iter:
    if name in ['__init__', ]:
        continue
    mod = __import__('.'.join([__name__, name]), fromlist='dummy')
    ui = mod.__dict__.get('UI_VIEW')
    if ui is not None:
        view_classes[ui.topwidget_name] = ui

