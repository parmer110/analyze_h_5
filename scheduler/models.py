from django.db import models

class RequestSchedulerLog (models.Model):
    name = models.CharField(max_length=50)
    url = models.CharField(max_length=200)
    method = models.CharField(max_length=10)
    header = models.TextField()
    body = models.TextField()
    request_time = models.DateTimeField()
    response = models.TextField()
    duration = models.DurationField()
    status = models.CharField(max_length=10)

