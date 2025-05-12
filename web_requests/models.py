from django.db import models
from common.models import User, Companies
from django.core.exceptions import ValidationError
from .serializers import DynamicRequestSerializer


class Requests (models.Model):
    name = models.CharField(max_length=50)
    url = models.URLField()
    method = models.CharField(max_length=10)
    header = models.TextField()
    body = models.TextField()
    description = models.TextField(null=True)

class RequestsForeign(models.Model):
    allowed_methods = [("GET", "GET"), ("POST", "POST"), ("PUT", "PUT"), ("DELETE", "DELETE")]
    company = models.ForeignKey(Companies, on_delete=models.CASCADE, related_name="requests", db_index=True)
    name = models.CharField(max_length=50, db_index=True)
    endpoint = models.URLField()
    headers = models.JSONField(null=True, blank=True)
    method = models.CharField(max_length=10, choices=allowed_methods)
    body_parameters = models.JSONField(null=True, blank=True)
    query_parameters = models.JSONField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('company', 'name')

    def clean(self):
        # Iterate over query_parameters
        for key, value in self.query_parameters.items():
            # Check if the value is not in type_mapping
            if value not in DynamicRequestSerializer.type_mapping:
                # Raise a ValidationError with a helpful message
                raise ValidationError(f"Invalid data type for {key}: {value}")

        # Call the parent class's clean method
        super().clean()
        
    def get_query_parameters(self):
        return {key: value for key, value in self.query_parameters.items()}
    def get_body_parameters(self):
        return {key: value for key, value in self.body_parameters.items()}

    def __str__(self):
        return f"Company: {self.company.name}, {self.name}"


class RequestLog(models.Model):
    name = models.ForeignKey(Requests, null=True, on_delete=models.CASCADE, related_name="log")
    request_name = models.CharField(max_length=50, null=True)
    username = models.CharField(max_length=255)
    request_type = models.CharField(max_length=50)
    request_data = models.JSONField(null=True)
    response_data = models.JSONField(blank=True, null=True)
    file_path = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    additional_info = models.JSONField(null=True, blank=True)
    execution_time = models.DurationField(null=True)

class WebTokens(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=50)
    value = models.CharField(max_length=200, null=True)

    class Meta:
        unique_together = ('user', 'name')
