from django.contrib.auth.models import User, Group

from ticket_tracker.tracker import (
    Tracker, TrackerPermissionItem, 
    TrackerGlobalPermission, TrackerPermission)
    
from ticket_tracker.staff_user import StaffGroup, StaffUser

from ticket_tracker.ticket import (
    Contact, TicketStatus, Ticket, 
    MessageBase,
    ContactMessage, StaffMessage)
    
from ticket_tracker.messaging import (
    MessageContact, Message, 
    MailUserConf, IncomingMailConfig, 
    OutgoingMailConfig, EmailHandler, 
    DefaultEmailMessageTemplate, EmailMessageTemplate)
    
from django.contrib import admin

#class GroupInline(admin.StackedInline):
#    model = Group
#    
#class StaffGroupAdmin(admin.ModelAdmin):
#    inlines = [GroupInline]
#    
#class UserInline(admin.StackedInline):
#    model = User
#    
#class StaffUserAdmin(admin.ModelAdmin):
#    inlines = [UserInline]
    
#class TrackerPermissionItemInline(admin.StackedInline):
#    model = TrackerPermissionItem
#    
#class TrackerGlobalPermissionAdmin(admin.ModelAdmin):
#    inlines = [TrackerPermissionItemInline]
#    
#class TrackerPermissionAdmin(admin.ModelAdmin):
#    inlines = [TrackerPermissionItemInline]
#    
#class TrackerAdmin(admin.ModelAdmin):
#    pass
    
admin.site.register(StaffGroup)#, StaffGroupAdmin)
admin.site.register(StaffUser)#, StaffUserAdmin)
admin.site.register(TrackerPermissionItem)
admin.site.register(TrackerGlobalPermission)#, TrackerGlobalPermissionAdmin)
admin.site.register(TrackerPermission)#, TrackerPermissionAdmin)
admin.site.register(Tracker)#, TrackerAdmin)
admin.site.register(EmailHandler)
admin.site.register(IncomingMailConfig)
admin.site.register(OutgoingMailConfig)
admin.site.register(MailUserConf)
admin.site.register(DefaultEmailMessageTemplate)
admin.site.register(EmailMessageTemplate)
admin.site.register(MessageContact)
admin.site.register(Message)
