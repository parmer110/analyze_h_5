# Generated by Django 5.1.4 on 2025-01-25 17:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web_requests', '0002_requestlog_file_path'),
    ]

    operations = [
        migrations.AlterField(
            model_name='requestlog',
            name='response_data',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
