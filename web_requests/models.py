from django.db import models

class RequestLog(models.Model):
    username = models.CharField(max_length=255)
    request_type = models.CharField(max_length=50)
    request_data = models.JSONField()
    response_data = models.JSONField(blank=True, null=True)
    file_path = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    additional_info = models.JSONField(null=True, blank=True)
    