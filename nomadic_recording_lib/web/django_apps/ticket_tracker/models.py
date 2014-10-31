from django.db import models

if False:    
    from . import tracker, staff_user, messaging, ticket

    for key in ['tracker', 'staff_user', 'messaging', 'ticket']:
        md = globals()[key]
        md_models = getattr(md, 'MODELS')
        for md_model in md_models:
            mname = md_model.__class__.__name__
            mname = '.'.join(['ticket_tracker',key, mname])
            globals()[mname] = md_model

