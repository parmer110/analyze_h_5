from django.contrib import admin
from .models import RequestLog, ScheduledRequest

class ScheduledRequestAdmin(admin.ModelAdmin):
    list_display=('id', 'name', 'url', 'method', 'header', 'body')

admin.site.register(RequestLog)
admin.site.register(ScheduledRequest, ScheduledRequestAdmin)