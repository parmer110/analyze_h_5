# Generated by Django 5.1.4 on 2025-02-08 15:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web_requests', '0006_requestlog_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='requests',
            name='description',
            field=models.TextField(null=True),
        ),
    ]
