# Generated by Django 5.1.4 on 2025-01-19 16:28

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='RequestLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(max_length=255)),
                ('request_type', models.CharField(max_length=50)),
                ('request_data', models.JSONField()),
                ('response_data', models.JSONField()),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('additional_info', models.JSONField(blank=True, null=True)),
            ],
        ),
    ]
