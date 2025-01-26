from django.contrib import admin
from .models import RequestLog

class RequestLogAdmin(admin.ModelAdmin):
    list_display=('id', 'username', 'request_type', 'request_data', 'timestamp', 'additional_info', 'response_data')

admin.site.register(RequestLog, RequestLogAdmin)
