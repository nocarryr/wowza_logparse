from models_default_builder.models import ModelDefault, ModelDefaultData

from django.contrib import admin

class ModelDefaultDataInline(admin.StackedInline):
    model = ModelDefaultData
    
class ModelDefaultAdmin(admin.ModelAdmin):
    inlines = [ModelDefaultDataInline]
admin.site.register(ModelDefault, ModelDefaultAdmin)
#admin.site.register(ModelDefaultData)
