class TDefault(object):
    def __init__(self, **kwargs):
        self.data = {}
        for key, val in kwargs.iteritems():
            self.data[key] = val
    
defaults = [dict(name='auto_response', 
                 subject='Re: {{ ticket.description.subject }} - Auto-response', 
                 body='\n'.join(['This is an automated message to inform you that your request was received', 
                                 'and we will follow up with you shortly.', 
                                 '', 
                                 '', 
                                 'Please do not respond to this email as your response may not be received by our system.', 
                                 '', 
                                 '', 
                                 'Thank you.'])), 
            dict(name='staff_response', 
                 subject='{{ message.subject }} - [ {{ tracker.name }} Ticket ID: {{ ticket.id }} ]', 
                 body='{{ message.body }}'), 
            dict(name='contact_response', 
                 subject='{{ message.subject }} - [ {{ tracker.name }} Ticket ID: {{ ticket.id }} ]', 
                 body='{{ message.body }}')]
