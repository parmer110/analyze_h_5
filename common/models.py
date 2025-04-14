from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission


class User(AbstractUser):
    id = models.BigAutoField(primary_key=True)
    groups = models.ManyToManyField(Group, related_name="custom_user", blank=True)
    user_permissions = models.ManyToManyField(Permission, related_name="custom_user", blank=True)
    