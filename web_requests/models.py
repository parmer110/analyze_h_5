from django.db import models


class Requests (models.Model):
    name = models.CharField(max_length=50)
    url = models.CharField(max_length=200)
    method = models.CharField(max_length=10)
    header = models.TextField()
    body = models.TextField()
    description = models.TextField(null=True)

class RequestLog(models.Model):
    name = models.ForeignKey(Requests, null=True, on_delete=models.CASCADE, related_name="log")
    request_name = models.CharField(max_length=50, null=True)
    username = models.CharField(max_length=255)
    request_type = models.CharField(max_length=50)
    request_data = models.JSONField()
    response_data = models.JSONField(blank=True, null=True)
    file_path = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    additional_info = models.JSONField(null=True, blank=True)
    execution_time = models.DurationField(null=True)
