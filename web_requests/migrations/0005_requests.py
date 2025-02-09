# Generated by Django 5.1.4 on 2025-02-08 13:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web_requests', '0004_requestlog_execution_time_requestlog_request_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='Requests',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('url', models.CharField(max_length=200)),
                ('method', models.CharField(max_length=10)),
                ('header', models.TextField()),
                ('body', models.TextField()),
            ],
        ),
    ]
