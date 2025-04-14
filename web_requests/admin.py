from django.contrib import admin
from .models import RequestLog, Requests, WebTokens

class RequestLogAdmin(admin.ModelAdmin):
    list_display=(
        'id', 'request_name', 'execution_time', 'username', 'request_type', 'request_data', 'timestamp', 'additional_info', 'response_data'
    )

class RequestsAdmin(admin.ModelAdmin):
    list_display=('id', 'name', 'url', 'method', 'header', 'body', 'description')
    list_editable=('name', 'url', 'method', 'header', 'body', 'description')

class WebTokensAdmin(admin.ModelAdmin):
    list_display=('id', 'user', 'name', 'value')

admin.site.register(RequestLog, RequestLogAdmin)
admin.site.register(Requests, RequestsAdmin)
admin.site.register(WebTokens,WebTokensAdmin)